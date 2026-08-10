#!/usr/bin/env python3
"""Build HTML/PDF outputs from a reviewed deck.json.

HTML is the primary target.  The existing PPTX renderer remains available as
an explicit compatibility target for projects that still need an editable
PowerPoint file.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

from validate_outline import validate


TARGETS = {"html", "pdf", "pptx"}


def run(command: list[str]) -> None:
    print("$ " + " ".join(str(part) for part in command))
    subprocess.run(command, check=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("deck", type=Path)
    parser.add_argument("-o", "--output", required=True, type=Path, help="output basename without extension")
    parser.add_argument(
        "--targets",
        default="html,pdf",
        help="comma-separated targets: html, pdf, pptx (default: html,pdf)",
    )
    parser.add_argument("--allow-overwrite", action="store_true", help="allow replacing outputs at the target basename")
    args = parser.parse_args()

    deck = args.deck.expanduser().resolve()
    if not deck.is_file():
        print(f"deck not found: {deck}", file=sys.stderr)
        return 2
    errors = validate(deck)
    if errors:
        print("outline validation failed:", file=sys.stderr)
        print("\n".join(f"- {error}" for error in errors), file=sys.stderr)
        return 2

    targets = {part.strip().lower() for part in args.targets.split(",") if part.strip()}
    unknown = targets - TARGETS
    if unknown:
        print(f"unknown target(s): {', '.join(sorted(unknown))}", file=sys.stderr)
        return 2
    if not targets:
        print("at least one target is required", file=sys.stderr)
        return 2
    if "pdf" in targets:
        targets.add("html")

    output = args.output.expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    extensions = {"html": ".html", "pdf": ".pdf", "pptx": ".pptx"}
    existing = [output.with_suffix(extensions[target]) for target in targets if output.with_suffix(extensions[target]).exists()]
    if existing and not args.allow_overwrite:
        print("refusing to overwrite existing outputs; choose a new basename or pass --allow-overwrite:", file=sys.stderr)
        print("\n".join(f"- {path}" for path in existing), file=sys.stderr)
        return 2

    html_path = output.with_suffix(".html")
    try:
        if "html" in targets:
            run([sys.executable, str(Path(__file__).with_name("render_html.py")), str(deck), "-o", str(html_path)])
        if "pdf" in targets:
            node = "node"
            run([node, str(Path(__file__).with_name("render_pdf.mjs")), str(html_path), "-o", str(output.with_suffix(".pdf"))])
        if "pptx" in targets:
            pptx_python = os.environ.get("HANDDRAWN_PPTX_PYTHON", sys.executable)
            run([pptx_python, str(Path(__file__).with_name("render_pptx.py")), str(deck), "-o", str(output.with_suffix(".pptx"))])
    except subprocess.CalledProcessError as exc:
        print(f"build failed with exit code {exc.returncode}: {' '.join(str(part) for part in exc.cmd)}", file=sys.stderr)
        return exc.returncode or 1

    print("build complete:")
    for target in sorted(targets):
        print(f"- {output.with_suffix(extensions[target])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
