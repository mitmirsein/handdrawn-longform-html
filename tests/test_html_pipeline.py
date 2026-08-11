#!/usr/bin/env python3
"""Small, dependency-light tests for the HTML-first deck contract."""

from __future__ import annotations

import json
import tempfile
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.render_html import render  # noqa: E402
from scripts.validate_outline import validate  # noqa: E402


FIXTURE = ROOT / "tests/fixtures/romans/rom00-1-1-2.deck.json"
CURRENT = ROOT / "output/rom00-1-1-2-gospel-v2-rough/deck-gangwon-bold.json"


class HtmlPipelineTests(unittest.TestCase):
    def test_fixture_remains_valid(self) -> None:
        self.assertEqual(validate(FIXTURE), [])

    def test_fixture_renders_one_section_per_slide(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "fixture.html"
            render(FIXTURE, output)
            document = output.read_text(encoding="utf-8")
            self.assertEqual(document.count('class="slide-page"'), 12)
            self.assertIn("@page", document)
            self.assertIn("window.__DECK_READY__", document)
            self.assertIn("window.__DECK_LAYOUT_ISSUES__", document)
            self.assertIn("Reserve a right-side art rail", document)
            self.assertIn("bottom caption rail below the artwork", document)

    def test_current_deck_declares_local_exact_fonts(self) -> None:
        self.assertTrue(CURRENT.is_file(), CURRENT)
        self.assertEqual(validate(CURRENT), [])
        data = json.loads(CURRENT.read_text(encoding="utf-8"))
        self.assertEqual(data.get("theme"), "rough-diary")
        self.assertEqual(data.get("character_anchor"), "character/anchor.png")
        self.assertTrue((CURRENT.parent / data["character_anchor"]).is_file())
        self.assertEqual(
            set(data.get("font_files", {})),
            {"display", "body"},
        )
        for relative in data["font_files"].values():
            self.assertTrue((CURRENT.parent / relative).is_file(), relative)

    def test_image_deck_requires_run_local_character_anchor(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            data = json.loads(FIXTURE.read_text(encoding="utf-8"))
            data["slides"][0]["image"] = "illustrations/opening.png"
            (root / "illustrations").mkdir()
            (root / "illustrations/opening.png").write_bytes(b"fixture")
            deck = root / "deck.json"
            deck.write_text(json.dumps(data), encoding="utf-8")

            errors = validate(deck)

        self.assertIn("character_anchor required when slides include images", errors)

    def test_character_anchor_must_live_under_character_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            data = json.loads(FIXTURE.read_text(encoding="utf-8"))
            data["character_anchor"] = "anchor.png"
            (root / "anchor.png").write_bytes(b"fixture")
            deck = root / "deck.json"
            deck.write_text(json.dumps(data), encoding="utf-8")

            errors = validate(deck)

        self.assertIn("character_anchor must be under character/", errors)

    def test_character_anchor_must_exist_on_disk(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            data = json.loads(FIXTURE.read_text(encoding="utf-8"))
            data["character_anchor"] = "character/anchor.png"
            (root / "character").mkdir()
            deck = root / "deck.json"
            deck.write_text(json.dumps(data), encoding="utf-8")

            errors = validate(deck)

        self.assertIn("character_anchor not found: character/anchor.png", errors)


if __name__ == "__main__":
    unittest.main()
