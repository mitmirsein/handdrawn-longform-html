#!/usr/bin/env python3
"""Create a clean, self-contained share bundle for one reviewed deck run."""

from __future__ import annotations

import argparse
import json
import shutil
import tempfile
from pathlib import Path

from audit_project import check_html_assets, check_portable_text
from validate_outline import validate


REQUIRED_DOCS = {"source-analysis.md", "argument-map.md", "claim-ledger.json", "slide-outline.md"}


def copy_file(source: Path, root: Path, destination_root: Path, copied: set[str]) -> None:
    try:
        relative = source.resolve().relative_to(root.resolve())
    except ValueError as exc:
        raise ValueError(f"share asset escapes the run directory: {source}") from exc
    target = destination_root / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    copied.add(relative.as_posix())


def package_directory(run_dir: Path, destination: Path, *, require_pdf: bool) -> Path:
    run_dir = run_dir.expanduser().resolve()
    deck_path = run_dir / "deck.json"
    if not deck_path.is_file():
        raise FileNotFoundError(f"canonical deck.json not found: {deck_path}")
    errors = validate(deck_path)
    if errors:
        raise ValueError("outline validation failed:\n" + "\n".join(f"- {error}" for error in errors))

    html_files = sorted(run_dir.glob("*.html"))
    if len(html_files) != 1:
        raise ValueError(f"expected exactly one canonical HTML in {run_dir}, found {len(html_files)}")
    html_path = html_files[0]
    pdf_path = html_path.with_suffix(".pdf")
    if require_pdf and not pdf_path.is_file():
        raise FileNotFoundError(f"canonical PDF not found: {pdf_path}")

    data = json.loads(deck_path.read_text(encoding="utf-8"))
    references = {"deck.json", html_path.name}
    if pdf_path.is_file():
        references.add(pdf_path.name)
        preflight = Path(f"{pdf_path}.preflight.json")
        if preflight.is_file():
            references.add(preflight.name)
    references.update(REQUIRED_DOCS)
    if (run_dir / "asset-manifest.json").is_file():
        references.add("asset-manifest.json")

    anchor = data.get("character_anchor")
    if anchor:
        references.add(str(anchor))
    for slide in data["slides"]:
        if slide.get("image"):
            references.add(str(slide["image"]))
    for relative in (data.get("font_files") or {}).values():
        references.add(str(relative))

    if destination.exists():
        raise FileExistsError(f"destination already exists: {destination}; choose another path")
    destination.mkdir(parents=True)
    copied: set[str] = set()
    for relative in sorted(references):
        source = (run_dir / relative).resolve()
        if not source.is_file():
            raise FileNotFoundError(f"share file not found: {relative}")
        copy_file(source, run_dir, destination, copied)

    manifest = {
        "deck": "deck.json",
        "html": html_path.name,
        "pdf": pdf_path.name if pdf_path.is_file() else None,
        "files": sorted(copied),
        "paths": "all paths are relative to this share directory",
    }
    (destination / "share-manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (destination / "README.txt").write_text(
        f"Open {html_path.name} in a browser.\n"
        + (f"Print/share {pdf_path.name} for the PDF version.\n" if pdf_path.is_file() else "")
        + "All referenced assets are included with relative paths.\n",
        encoding="utf-8",
    )
    errors = check_portable_text(destination)
    errors.extend(check_html_assets(destination / html_path.name))
    if errors:
        shutil.rmtree(destination)
        raise ValueError("share bundle failed portability checks:\n" + "\n".join(f"- {error}" for error in errors))
    return destination


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_dir", type=Path, help="one reviewed output/<slug> directory")
    parser.add_argument("-o", "--output", required=True, type=Path, help="share directory or .zip path")
    parser.add_argument("--html-only", action="store_true", help="allow a bundle without a PDF")
    args = parser.parse_args()

    run_dir = args.run_dir.expanduser().resolve()
    destination = args.output.expanduser().resolve()
    try:
        if destination.suffix.lower() == ".zip":
            destination.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryDirectory(prefix="handdrawn-share-") as temporary:
                staging = Path(temporary) / run_dir.name
                package_directory(run_dir, staging, require_pdf=not args.html_only)
                shutil.make_archive(str(destination.with_suffix("")), "zip", root_dir=staging.parent, base_dir=staging.name)
            print(f"share bundle created: {destination}")
        else:
            package_directory(run_dir, destination, require_pdf=not args.html_only)
            print(f"share bundle created: {destination}")
    except (FileNotFoundError, FileExistsError, ValueError, OSError) as exc:
        print(f"share packaging failed: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
