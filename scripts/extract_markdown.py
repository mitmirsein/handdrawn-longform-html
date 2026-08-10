#!/usr/bin/env python3
"""Extract deterministic structure from a Markdown source without editing it."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
LINK = re.compile(r"!?\[[^]]*\]\(([^)]+)\)|!\[([^]]*)\]\(([^)]+)\)")
WIKILINK = re.compile(r"!?(\[\[[^]]+\]\])")


def _frontmatter(lines: list[str]) -> tuple[dict[str, str], int]:
    if not lines or lines[0].strip() != "---":
        return {}, 0
    end = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
    if end is None:
        return {}, 0
    values: dict[str, str] = {}
    for line in lines[1:end]:
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        values[key.strip()] = value.strip().strip('"\'')
    return values, end + 1


def _classify(text: str) -> list[str]:
    labels: list[str] = []
    lowered = text.lower()
    if text.startswith(">"):
        labels.append("QUOTE")
    if re.search(r"^[-*+]\s|^\d+[.)]\s", text, re.MULTILINE):
        labels.append("LIST")
    if "?" in text or "？" in text or re.search(r"무엇|왜|어떻게|기억", text):
        labels.append("QUESTION")
    if re.search(r"성경|복음|예수|하나님|설교|sermon|gospel", lowered):
        labels.append("DOMAIN")
    if re.search(r"결론|따라서|그러므로|마지막|정리", text):
        labels.append("TRANSITION")
    return labels or ["PARAGRAPH"]


def extract(path: Path) -> dict:
    lines = path.read_text(encoding="utf-8").splitlines()
    frontmatter, body_start = _frontmatter(lines)
    headings = []
    for number, line in enumerate(lines, 1):
        match = HEADING.match(line)
        if match:
            headings.append({"line": number, "level": len(match.group(1)), "text": match.group(2)})

    blocks = []
    start: int | None = None
    buffer: list[str] = []

    def flush(end_line: int) -> None:
        nonlocal start, buffer
        if start is None:
            return
        text = "\n".join(buffer).strip()
        if text:
            blocks.append({
                "start_line": start,
                "end_line": end_line,
                "text": text,
                "labels": _classify(text),
            })
        start = None
        buffer = []

    for number, line in enumerate(lines[body_start:], body_start + 1):
        if not line.strip():
            flush(number - 1)
            continue
        if start is None:
            start = number
        buffer.append(line)
    flush(len(lines))

    links = []
    for number, line in enumerate(lines, 1):
        for match in LINK.finditer(line):
            target = match.group(1) or match.group(3)
            links.append({"line": number, "target": target})
        for match in WIKILINK.finditer(line):
            links.append({"line": number, "target": match.group(1), "kind": "wikilink"})

    return {
        "source": str(path),
        "title": frontmatter.get("title") or (headings[0]["text"] if headings else path.stem),
        "frontmatter": frontmatter,
        "line_count": len(lines),
        "word_count": len(path.read_text(encoding="utf-8").split()),
        "headings": headings,
        "blocks": blocks,
        "links_and_embeds": links,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("-o", "--output", type=Path)
    args = parser.parse_args()
    source = args.source.expanduser().resolve()
    if not source.is_file():
        print(f"source not found: {source}", file=sys.stderr)
        return 2
    payload = extract(source)
    rendered = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
