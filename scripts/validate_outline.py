#!/usr/bin/env python3
"""Validate the reviewed deck.json contract for the HTML-first deck pipeline."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


LAYOUTS = {"title", "content", "full", "quote", "comparison", "timeline", "flow", "table"}
THEMES = {"clean", "rough-diary"}
EXEMPT_SOURCE_ROLES = {"cover", "transition"}
REQUIRED = {"id", "headline", "one_sentence_takeaway", "role"}


def validate_character_anchor(data: dict, base: Path, slides: list[object]) -> list[str]:
    """Require a portable, run-local anchor whenever the deck has scene images."""

    has_scene_images = any(isinstance(slide, dict) and slide.get("image") for slide in slides)
    value = data.get("character_anchor")
    if value is None:
        return ["character_anchor required when slides include images"] if has_scene_images else []
    if not isinstance(value, str) or not value:
        return ["character_anchor must be a relative path"]

    relative = Path(value)
    if relative.is_absolute() or ".." in relative.parts:
        return ["character_anchor must be a relative path under character/"]
    if relative.parts[:1] != ("character",):
        return ["character_anchor must be under character/"]
    if not (base / relative).is_file():
        return [f"character_anchor not found: {value}"]
    return []


def validate_local_file(value: object, base: Path, label: str, *, allow_parent: bool = True) -> list[str]:
    """Validate a relative file reference and resolve it from the deck directory."""

    if not isinstance(value, str) or not value:
        return [f"{label} must be a relative path"]
    relative = Path(value)
    if relative.is_absolute():
        return [f"{label} must be a relative path"]
    if not allow_parent and ".." in relative.parts:
        return [f"{label} must stay under the deck directory"]
    resolved = (base / relative).resolve()
    if not resolved.is_file():
        return [f"{label} not found: {value}"]
    return []


def validate(path: Path) -> list[str]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return [f"deck not found: {path}"]
    except json.JSONDecodeError as exc:
        return [f"invalid JSON at {exc.lineno}:{exc.colno}: {exc.msg}"]

    errors: list[str] = []
    if not isinstance(data, dict):
        return ["deck must be a JSON object"]
    slides = data.get("slides")
    if not isinstance(slides, list) or not slides:
        return ["slides must be a non-empty array"]
    base = path.parent
    errors.extend(validate_character_anchor(data, base, slides))
    theme = data.get("theme")
    if theme is not None and theme not in THEMES:
        errors.append(f"unsupported theme {theme!r}")
    font_files = data.get("font_files")
    if font_files is not None:
        if not isinstance(font_files, dict):
            errors.append("font_files must be an object")
        else:
            for key in ("display", "body"):
                value = font_files.get(key)
                errors.extend(validate_local_file(value, base, f"font_files.{key}"))
    asset_generation = data.get("asset_generation")
    generated_assets = isinstance(asset_generation, dict)
    seen: set[str] = set()
    for index, slide in enumerate(slides, 1):
        prefix = f"slide {index}"
        if not isinstance(slide, dict):
            errors.append(f"{prefix}: must be an object")
            continue
        missing = REQUIRED - slide.keys()
        errors.extend(f"{prefix}: missing {field}" for field in sorted(missing))
        slide_id = slide.get("id")
        if slide_id in seen:
            errors.append(f"{prefix}: duplicate id {slide_id!r}")
        if isinstance(slide_id, str):
            seen.add(slide_id)
        for field in ("headline", "one_sentence_takeaway", "role"):
            if field in slide and not isinstance(slide[field], str):
                errors.append(f"{prefix}: {field} must be a string")
        layout = slide.get("layout", "content")
        if layout not in LAYOUTS:
            errors.append(f"{prefix}: unsupported layout {layout!r}")
        role = slide.get("role", "")
        if role not in EXEMPT_SOURCE_ROLES and not slide.get("source_lines") and not slide.get("primary_references"):
            errors.append(f"{prefix}: source_lines or primary_references required")
        source_lines = slide.get("source_lines")
        if source_lines is not None:
            if not isinstance(source_lines, list) or not all(isinstance(n, int) and n > 0 for n in source_lines):
                errors.append(f"{prefix}: source_lines must be positive integers")
        image = slide.get("image")
        if generated_assets and str(slide.get("asset_mode") or "illustration").lower() != "none" and not image:
            errors.append(f"{prefix}: image required after asset generation")
        if image is not None:
            image_errors = validate_local_file(image, base, f"{prefix}: image", allow_parent=False)
            errors.extend(image_errors)
        if len(str(slide.get("headline", ""))) > 72:
            errors.append(f"{prefix}: headline is too long for a slide")
        source_text = str(slide.get("source", ""))
        refs = slide.get("primary_references") or []
        ref_text = " ".join(str(r) for r in refs) if isinstance(refs, list) else ""
        if any(flag in source_text or flag in ref_text for flag in ("검토 필요", "검증 필요", "NEEDS-REVIEW", "확인 필요")):
            errors.append(f"{prefix}: public source or primary_references contains internal review flag; review notes belong in speaker_notes or claim-ledger.json")
        body_text = str(slide.get("body", "")).strip()
        visible_text = str(slide.get("visible_text", "")).strip()
        if body_text and visible_text and re.sub(r"[\s·→↔\+,\.\:\?!=]+", "", body_text) == re.sub(r"[\s·→↔\+,\.\:\?!=]+", "", visible_text):
            errors.append(f"{prefix}: visible_text is identical to body ({body_text!r}); use body for prose and visible_text for distinct token tags to prevent duplicate rendering")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("deck", type=Path)
    args = parser.parse_args()
    errors = validate(args.deck.expanduser().resolve())
    if errors:
        print("outline validation failed:")
        print("\n".join(f"- {error}" for error in errors))
        return 1
    data = json.loads(args.deck.read_text(encoding="utf-8"))
    print(f"outline valid: {args.deck} ({len(data['slides'])} slides)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
