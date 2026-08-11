#!/usr/bin/env python3
"""Convert outer white/off-white background of PNG/JPEG illustrations to transparent alpha.

Uses a border flood-fill algorithm to preserve internal white fills (e.g. eyes,
clothing, paper props) while making outer canvas background transparent.
"""

from __future__ import annotations

import argparse
import sys
from collections import deque
from pathlib import Path

try:
    from PIL import Image
except ImportError:
    Image = None


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


def process_directory(directory: Path, threshold: int = 240) -> list[Path]:
    """Recursively process all PNG/JPG images in a directory."""

    processed = []
    for ext in ("*.png", "*.jpg", "*.jpeg", "*.PNG", "*.JPG", "*.JPEG"):
        for path in directory.rglob(ext):
            make_transparent(path, path, threshold=threshold)
            processed.append(path)
    return processed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("target", type=Path, help="image file or directory to process")
    parser.add_argument("-o", "--output", type=Path, help="output PNG path (for single file)")
    parser.add_argument("--threshold", type=int, default=240, help="white background RGB threshold (default: 240)")
    args = parser.parse_args()

    target = args.target.expanduser().resolve()
    if target.is_file():
        result = make_transparent(target, args.output, threshold=args.threshold)
        print(f"transparent PNG saved: {result}")
    elif target.is_dir():
        results = process_directory(target, threshold=args.threshold)
        print(f"processed {len(results)} images in {target}")
    else:
        print(f"target not found: {target}", file=sys.stderr)
        return 2

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
