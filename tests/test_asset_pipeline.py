#!/usr/bin/env python3

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from scripts.asset_pipeline import (
    AssetPipelineError,
    _require_capability,
    accept_asset,
    load_json,
    plan_assets,
    run_generation,
)
from scripts.validate_outline import validate


ROOT = Path(__file__).resolve().parents[1]
MOCK_ADAPTER = ROOT / "tests/fixtures/mock_image_adapter.py"


def make_fixture_deck(root: Path) -> Path:
    deck = root / "deck.json"
    deck.write_text(
        json.dumps(
            {
                "title": "자산 자동 생성 테스트",
                "source": "source-analysis.md",
                "language": "ko",
                "line_mode": "clean",
                "theme": "rough-diary",
                "slides": [
                    {
                        "id": "s01-cover",
                        "role": "cover",
                        "layout": "title",
                        "headline": "시작 질문",
                        "one_sentence_takeaway": "질문으로 시작한다.",
                        "visual_scene": "빈 문 앞에서 질문을 품은 관찰자",
                        "character_action": "문을 바라보며 조심스럽게 손을 든다",
                    },
                    {
                        "id": "s02-claim",
                        "role": "claim",
                        "layout": "content",
                        "headline": "핵심 주장",
                        "one_sentence_takeaway": "앵커가 모든 장면의 기준이 된다.",
                        "source_lines": [1, 2],
                        "visual_scene": "하나의 기준점에서 여러 장면으로 이어지는 길",
                        "character_action": "같은 나침반을 들고 길을 확인한다",
                    },
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return deck


def make_image(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGBA", (64, 64), (255, 254, 250, 255)).save(path)


class AssetPipelineTests(unittest.TestCase):
    def test_plan_creates_anchor_and_scene_jobs_when_no_assets_are_present(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            deck = make_fixture_deck(root)
            plan_path = plan_assets(deck)
            plan = load_json(plan_path)

            self.assertEqual(plan["status"], "planned")
            self.assertEqual(plan["jobs"][0]["job_id"], "character-anchor")
            scene_jobs = [job for job in plan["jobs"] if job["kind"] == "scene_illustration"]
            self.assertEqual(len(scene_jobs), 2)
            self.assertEqual({tuple(job["references"]) for job in scene_jobs}, {("character/anchor.png",)})
            self.assertNotIn("illustrations/01-s01-cover.png", scene_jobs[0]["references"])
            self.assertIn("No Korean", " ".join(plan["jobs"][0]["prompt_spec"]["constraints"]))

    def test_mock_adapter_generates_anchor_and_illustrations_then_finalizes_deck(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            deck = make_fixture_deck(root)
            plan_path = plan_assets(deck)
            manifest_path = run_generation(plan_path, str(MOCK_ADAPTER))

            manifest = load_json(manifest_path)
            finalized = load_json(deck)
            self.assertTrue((root / "character/anchor.png").is_file())
            self.assertEqual(len(list((root / "illustrations").glob("*.png"))), 2)
            self.assertEqual(finalized["character_anchor"], "character/anchor.png")
            self.assertTrue(all(slide.get("image", "").startswith("illustrations/") for slide in finalized["slides"]))
            self.assertEqual(validate(deck), [])
            self.assertEqual(manifest["generation"]["provider_metadata_by_job"]["character-anchor"]["provider"], "mock")
            self.assertEqual(load_json(root / "generation-state.json")["status"], "ready")
            self.assertEqual(
                {asset["references"][0] for asset in manifest["scene_assets"]},
                {"character/anchor.png"},
            )

    def test_host_import_requires_anchor_before_scene(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            deck = make_fixture_deck(root)
            plan_path = plan_assets(deck)
            anchor = root / "anchor-source.png"
            scene = root / "scene-source.png"
            make_image(anchor)
            make_image(scene)

            with self.assertRaisesRegex(AssetPipelineError, "accept the character anchor first"):
                accept_asset(plan_path, "s01-cover", scene)

            accept_asset(plan_path, "character-anchor", anchor)
            accept_asset(plan_path, "s01-cover", scene)
            accept_asset(plan_path, "s02-claim", scene)
            self.assertEqual(validate(deck), [])

    def test_reference_capability_is_required_for_scene_jobs(self) -> None:
        job = {"job_id": "s01", "references": ["character/anchor.png"]}
        with self.assertRaisesRegex(AssetPipelineError, "reference_images"):
            _require_capability({"generate": True, "reference_images": False}, "reference_images", job)

    def test_changed_anchor_is_rejected_after_planning(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            deck = make_fixture_deck(root)
            anchor = root / "existing-anchor.png"
            make_image(anchor)
            plan_path = plan_assets(deck, character_reference=anchor)
            (root / "character/anchor.png").write_bytes(b"changed")
            with self.assertRaisesRegex(AssetPipelineError, "anchor changed"):
                run_generation(plan_path, str(MOCK_ADAPTER))


if __name__ == "__main__":
    unittest.main()
