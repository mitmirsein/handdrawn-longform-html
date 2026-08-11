#!/usr/bin/env python3
"""Run the repository-wide portability, artifact, and preflight audit."""

from __future__ import annotations

import argparse
import json
import re
from html.parser import HTMLParser
from pathlib import Path

from validate_outline import validate


ROOT = Path(__file__).resolve().parents[1]
_slash = chr(47)
_host_markers = (
    _slash + "Users/",
    _slash + "private/",
    _slash + "var/",
    _slash + "tmp/",
    "file:" + _slash + _slash,
    "msn" + "-imac",
    "local" + "host",
    "127" + ".0.0.1",
)
ABSOLUTE_MARKERS = re.compile("|".join(re.escape(marker) for marker in _host_markers))
STALE_SCREENSHOT = re.compile(r"-html-\d+_\d+\.png$", re.IGNORECASE)
TEXT_SUFFIXES = {".html", ".json", ".md", ".py", ".mjs", ".yaml", ".yml", ".txt", ".css"}
REQUIRED_DOCS = {"source-analysis.md", "argument-map.md", "claim-ledger.json", "slide-outline.md"}
ASSET_PLAN_SCHEMA = "handdrawn-assets/v1"


class AssetReferenceParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.references: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        for key, value in attrs:
            if key in {"src", "href"} and value:
                self.references.append(value)


def is_ignored(path: Path) -> bool:
    return any(part in {".git", ".venv", "node_modules", "__pycache__", ".pytest_cache"} for part in path.parts)


def check_portable_text(root: Path) -> list[str]:
    errors: list[str] = []
    for path in root.rglob("*"):
        if not path.is_file() or is_ignored(path) or path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        if path.name == "audit_project.py":
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if ABSOLUTE_MARKERS.search(text):
            errors.append(f"absolute or host-specific path: {path.relative_to(root)}")
    return errors


def check_html_assets(path: Path) -> list[str]:
    errors: list[str] = []
    parser = AssetReferenceParser()
    parser.feed(path.read_text(encoding="utf-8"))
    try:
        display_path = path.relative_to(ROOT)
    except ValueError:
        display_path = path
    for reference in parser.references:
        if reference.startswith(("#", "data:", "http://", "https://", "mailto:")):
            continue
        candidate = (path.parent / reference.split("#", 1)[0].split("?", 1)[0]).resolve()
        if not candidate.is_file():
            errors.append(f"missing HTML asset: {display_path} -> {reference}")
    return errors


def check_preflight(path: Path) -> list[str]:
    errors: list[str] = []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [f"invalid preflight {path.relative_to(ROOT)}: {exc}"]
    for field in ("input", "output"):
        value = data.get(field)
        if not isinstance(value, str) or Path(value).is_absolute() or ABSOLUTE_MARKERS.search(value):
            errors.append(f"preflight {path.relative_to(ROOT)} has non-portable {field}")
    if not isinstance(data.get("chrome"), str) or "/" in str(data.get("chrome")):
        errors.append(f"preflight {path.relative_to(ROOT)} has a non-portable chrome path")
    check = data.get("check")
    if not isinstance(check, dict):
        errors.append(f"preflight {path.relative_to(ROOT)} is missing check")
    else:
        if "layoutIssues" not in check:
            errors.append(f"preflight {path.relative_to(ROOT)} is stale: missing layoutIssues")
        elif check["layoutIssues"]:
            errors.append(f"preflight {path.relative_to(ROOT)} contains layoutIssues")
        for field in ("brokenImages", "overflow"):
            if check.get(field) != 0:
                errors.append(f"preflight {path.relative_to(ROOT)} has {field}={check.get(field)!r}")
    return errors


def check_asset_plan(path: Path) -> list[str]:
    """Check optional generation plans without requiring generated assets."""

    errors: list[str] = []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [f"invalid asset plan {path.relative_to(ROOT)}: {exc}"]
    if data.get("schema_version") != ASSET_PLAN_SCHEMA:
        errors.append(f"unsupported asset plan schema: {path.relative_to(ROOT)}")
    deck = data.get("deck")
    if not isinstance(deck, str) or Path(deck).is_absolute() or ".." in Path(deck).parts:
        errors.append(f"asset plan {path.relative_to(ROOT)} has a non-portable deck path")
    character = data.get("character")
    if not isinstance(character, dict):
        errors.append(f"asset plan {path.relative_to(ROOT)} is missing character")
    else:
        anchor = character.get("path")
        if not isinstance(anchor, str) or Path(anchor).is_absolute() or ".." in Path(anchor).parts:
            errors.append(f"asset plan {path.relative_to(ROOT)} has a non-portable character path")
        elif not anchor.startswith("character/"):
            errors.append(f"asset plan {path.relative_to(ROOT)} character path is outside character/")
    jobs = data.get("jobs")
    if not isinstance(jobs, list):
        return errors + [f"asset plan {path.relative_to(ROOT)} is missing jobs"]
    seen: set[str] = set()
    for job in jobs:
        if not isinstance(job, dict):
            errors.append(f"asset plan {path.relative_to(ROOT)} contains a non-object job")
            continue
        job_id = job.get("job_id")
        if not isinstance(job_id, str) or not job_id:
            errors.append(f"asset plan {path.relative_to(ROOT)} contains a job without an id")
        elif job_id in seen:
            errors.append(f"asset plan {path.relative_to(ROOT)} contains duplicate job {job_id}")
        seen.add(str(job_id))
        target = job.get("target")
        if not isinstance(target, str) or Path(target).is_absolute() or ".." in Path(target).parts:
            errors.append(f"asset plan {path.relative_to(ROOT)} has a non-portable target")
        references = job.get("references", [])
        if not isinstance(references, list):
            errors.append(f"asset plan {path.relative_to(ROOT)} has invalid references for {job_id}")
        else:
            for reference in references:
                if not isinstance(reference, str) or Path(reference).is_absolute() or ".." in Path(reference).parts:
                    errors.append(f"asset plan {path.relative_to(ROOT)} has a non-portable reference for {job_id}")
            if job.get("kind") == "scene_illustration" and references != ["character/anchor.png"]:
                errors.append(f"asset plan {path.relative_to(ROOT)} does not lock scenes to the anchor: {job_id}")
    return errors


def check_output(output_root: Path) -> list[str]:
    errors: list[str] = []
    if not output_root.exists():
        return errors
    deck_paths = sorted(output_root.glob("*/deck.json"))
    for directory in sorted(path for path in output_root.iterdir() if path.is_dir()):
        files = list(directory.iterdir())
        if any(path.name == ".DS_Store" or path.name.startswith("~$") for path in files):
            errors.append(f"temporary metadata in output: {directory.relative_to(ROOT)}")
        if any(path.is_file() and STALE_SCREENSHOT.search(path.name) for path in files):
            errors.append(f"stale screenshot artifacts in output: {directory.relative_to(ROOT)}")
        deck_files = sorted(directory.glob("deck*.json"))
        if len(deck_files) > 1:
            errors.append(f"multiple deck manifests in one run directory: {directory.relative_to(ROOT)}")
        if not (directory / "deck.json").is_file():
            continue
        asset_plan = directory / "asset-plan.json"
        if asset_plan.is_file():
            errors.extend(check_asset_plan(asset_plan))
        missing_docs = sorted(REQUIRED_DOCS - {path.name for path in files})
        errors.extend(f"{directory.relative_to(ROOT)} missing {name}" for name in missing_docs)
        html_files = sorted(directory.glob("*.html"))
        if len(html_files) != 1:
            errors.append(f"expected one canonical HTML in {directory.relative_to(ROOT)}, found {len(html_files)}")
        for html in html_files:
            errors.extend(check_html_assets(html))
        pdf_files = sorted(directory.glob("*.pdf"))
        for pdf in pdf_files:
            if not Path(f"{pdf}.preflight.json").is_file():
                errors.append(f"missing PDF preflight: {pdf.relative_to(ROOT)}")
    for deck in deck_paths:
        errors.extend(f"{deck.relative_to(ROOT)}: {error}" for error in validate(deck))
    for preflight in sorted(output_root.glob("*/*.preflight.json")):
        errors.extend(check_preflight(preflight))
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--output-root", type=Path, default=None)
    parser.add_argument("--require-output", action="store_true")
    args = parser.parse_args()

    root = args.root.expanduser().resolve()
    output_root = (args.output_root or root / "output").expanduser().resolve()
    errors = check_portable_text(root)
    errors.extend(check_output(output_root))
    if args.require_output and not list(output_root.glob("*/deck.json")):
        errors.append(f"no output decks found under {output_root}")

    if errors:
        print("project audit failed:")
        print("\n".join(f"- {error}" for error in errors))
        return 1
    deck_count = len(list(output_root.glob("*/deck.json"))) if output_root.is_dir() else 0
    print(f"project audit passed: {deck_count} output deck(s), portable paths, HTML assets, and preflights checked")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
