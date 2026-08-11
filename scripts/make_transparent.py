#!/usr/bin/env python3
"""Convert outer white/off-white background of PNG/JPEG illustrations to transparent alpha.

Uses a border flood-fill algorithm to preserve internal white fills (e.g. eyes,
clothing, paper props) while making outer canvas background transparent.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import deque
from pathlib import Path

try:
    from PIL import Image
except ImportError:
    Image = None


IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg"}


def make_transparent(input_path: Path, output_path: Path | None = None, threshold: int = 240) -> Path:
    """Convert outer background of an image to transparent PNG."""

    if Image is None:
        raise RuntimeError(f"Pillow is required: {sys.executable} -m pip install Pillow")

    input_path = input_path.expanduser().resolve()
    if not input_path.is_file():
        raise FileNotFoundError(f"image not found: {input_path}")

    target_path = (output_path or input_path).expanduser().resolve()
    target_path.parent.mkdir(parents=True, exist_ok=True)

    img = Image.open(input_path).convert("RGBA")
    width, height = img.size
    pixels = img.load()

    visited = set()
    queue = deque()

    def is_bg(x: int, y: int) -> bool:
        r, g, b, _ = pixels[x, y]
        return r >= threshold and g >= threshold and b >= threshold

    # Seed all border pixels that match background threshold
    for x in range(width):
        for y in (0, height - 1):
            if (x, y) not in visited and is_bg(x, y):
                visited.add((x, y))
                queue.append((x, y))

    for y in range(height):
        for x in (0, width - 1):
            if (x, y) not in visited and is_bg(x, y):
                visited.add((x, y))
                queue.append((x, y))

    # Flood fill connected background pixels
    while queue:
        cx, cy = queue.popleft()
        for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            nx, ny = cx + dx, cy + dy
            if 0 <= nx < width and 0 <= ny < height:
                if (nx, ny) not in visited and is_bg(nx, ny):
                    visited.add((nx, ny))
                    queue.append((nx, ny))

    # Apply transparency to connected outer background pixels
    for x, y in visited:
        r, g, b, _ = pixels[x, y]
        pixels[x, y] = (r, g, b, 0)

    img.save(target_path, "PNG", optimize=True)
    return target_path


def deck_image_paths(deck_path: Path) -> list[Path]:
    """Return only the scene images referenced by a deck."""

    data = json.loads(deck_path.read_text(encoding="utf-8"))
    base = deck_path.parent.resolve()
    paths: set[Path] = set()
    for slide in data.get("slides", []):
        image = slide.get("image") if isinstance(slide, dict) else None
        if not image:
            continue
        path = (base / str(image)).resolve()
        if not path.is_file():
            raise FileNotFoundError(f"image not found: {image}")
        if not path.is_relative_to(base):
            raise ValueError(f"image must stay under the deck directory: {image}")
        if path.suffix.lower() in IMAGE_SUFFIXES:
            paths.add(path)
    return sorted(paths)


def directory_image_paths(directory: Path, deck_path: Path | None = None) -> list[Path]:
    """Find safe scene assets without touching anchors or stale screenshots."""

    if deck_path is not None:
        return deck_image_paths(deck_path)
    scene_dir = directory / "illustrations" if (directory / "illustrations").is_dir() else directory
    return sorted(
        path for path in scene_dir.iterdir()
        if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES and not path.name.startswith(".")
    )


def process_directory(
    directory: Path,
    threshold: int = 240,
    *,
    deck_path: Path | None = None,
    output_directory: Path | None = None,
) -> list[Path]:
    """Process referenced scene images, optionally into a separate directory."""

    directory = directory.expanduser().resolve()
    output_root = output_directory.expanduser().resolve() if output_directory else None
    processed: list[Path] = []
    for path in directory_image_paths(directory, deck_path):
        target = path
        if output_root is not None:
            target = output_root / path.relative_to(directory)
        make_transparent(path, target, threshold=threshold)
        processed.append(target)
    return processed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("target", type=Path, help="image file, deck.json, or output directory")
    parser.add_argument("-o", "--output", type=Path, help="output PNG path for a single image")
    parser.add_argument("--output-dir", type=Path, help="separate output directory for a deck/output directory")
    parser.add_argument("--in-place", action="store_true", help="replace referenced scene images in place")
    parser.add_argument("--threshold", type=int, default=240, help="white background RGB threshold (default: 240)")
    args = parser.parse_args()

    target = args.target.expanduser().resolve()
    if target.is_file():
        if target.suffix.lower() == ".json":
            try:
                results = process_directory(
                    target.parent,
                    threshold=args.threshold,
                    deck_path=target,
                    output_directory=None if args.in_place else args.output_dir or target.parent.with_name(f"{target.parent.name}-transparent"),
                )
            except (FileNotFoundError, ValueError, RuntimeError, json.JSONDecodeError) as exc:
                print(str(exc), file=sys.stderr)
                return 2
            print(f"processed {len(results)} referenced scene images")
            return 0
        output = args.output
        if output is None and not args.in_place:
            output = target.with_name(f"{target.stem}.transparent.png")
        result = make_transparent(target, output, threshold=args.threshold)
        print(f"transparent PNG saved: {result}")
    elif target.is_dir():
        deck_path = target / "deck.json"
        if not deck_path.is_file():
            deck_path = None
        output_directory = None
        if not args.in_place:
            output_directory = args.output_dir or target.with_name(f"{target.name}-transparent")
        try:
            results = process_directory(
                target,
                threshold=args.threshold,
                deck_path=deck_path,
                output_directory=output_directory,
            )
        except (FileNotFoundError, ValueError, RuntimeError, json.JSONDecodeError) as exc:
            print(str(exc), file=sys.stderr)
            return 2
        destination = "in place" if output_directory is None else str(output_directory)
        print(f"processed {len(results)} referenced scene images -> {destination}")
    else:
        print(f"target not found: {target}", file=sys.stderr)
        return 2

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
