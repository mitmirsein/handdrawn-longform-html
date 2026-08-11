#!/usr/bin/env python3
"""Plan and run provider-neutral character and illustration generation jobs.

The core pipeline deliberately knows nothing about Imagen, Nano Banana, or any
other image provider.  Providers implement the small JSON adapter contract
documented in ``references/image-generation.md``.  A host-native image tool
can use the ``accept`` command to import its reviewed output into the same
state machine.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Sequence


PROTOCOL = "handdrawn-image/v1"
PLAN_SCHEMA = "handdrawn-assets/v1"
STATE_FILE = "generation-state.json"
MANIFEST_FILE = "asset-manifest.json"
STAGING_PREFIX = ".asset-staging-"
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}


class AssetPipelineError(RuntimeError):
    """Raised for a user-actionable planning or generation failure."""


def load_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise AssetPipelineError(f"JSON file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise AssetPipelineError(f"invalid JSON at {path}:{exc.lineno}:{exc.colno}: {exc.msg}") from exc
    if not isinstance(data, dict):
        raise AssetPipelineError(f"expected a JSON object: {path}")
    return data


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", dir=path.parent, prefix=f".{path.name}.", delete=False
        ) as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            temporary = handle.name
        os.replace(temporary, path)
    finally:
        if temporary:
            temporary_path = Path(temporary)
            if temporary_path.exists():
                temporary_path.unlink()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def relative_path(value: object, label: str, *, required_prefix: str | None = None) -> str:
    if not isinstance(value, str) or not value.strip():
        raise AssetPipelineError(f"{label} must be a non-empty relative path")
    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        raise AssetPipelineError(f"{label} must not escape the run directory: {value}")
    normalized = path.as_posix()
    if required_prefix and not (normalized == required_prefix or normalized.startswith(required_prefix + "/")):
        raise AssetPipelineError(f"{label} must be under {required_prefix}: {value}")
    return normalized


def safe_slug(value: object, fallback: str = "slide") -> str:
    text = str(value or "").strip().lower()
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return text[:56] or fallback


def validate_image(path: Path) -> tuple[bool, str | None]:
    """Check that a generated asset is a decodable raster image."""

    if not path.is_file():
        return False, f"image not found: {path}"
    if path.suffix.lower() not in IMAGE_SUFFIXES:
        return False, f"unsupported image suffix: {path.suffix}"
    try:
        from PIL import Image
    except ImportError:
        # The project requirements include Pillow, but retain a useful fallback
        # for the planning CLI in a minimal environment.
        if path.stat().st_size == 0:
            return False, f"empty image: {path}"
        return True, None
    try:
        with Image.open(path) as image:
            image.verify()
        with Image.open(path) as image:
            width, height = image.size
    except Exception as exc:  # Pillow raises several format-specific errors.
        return False, f"unreadable image {path}: {exc}"
    if width < 16 or height < 16:
        return False, f"image is too small ({width}x{height}): {path}"
    return True, None


def source_context(deck: dict[str, Any], run_dir: Path) -> dict[str, Any]:
    source = deck.get("source")
    source_name = Path(source).name if isinstance(source, str) else None
    return {
        "title": str(deck.get("title") or "장문 원고 슬라이드"),
        "language": str(deck.get("language") or "ko"),
        "line_mode": str(deck.get("line_mode") or "clean"),
        "theme": str(deck.get("theme") or "clean"),
        "aspect_ratio": str(deck.get("aspect_ratio") or "16:9"),
        "source_file": source_name,
        "run": run_dir.name,
    }


def character_profile(deck: dict[str, Any], slides: list[dict[str, Any]], run_dir: Path) -> dict[str, Any]:
    """Create a safe, provider-neutral creative brief for a fictional observer."""

    supplied = deck.get("character_profile")
    if supplied is not None and not isinstance(supplied, dict):
        raise AssetPipelineError("character_profile must be an object when provided")
    supplied = supplied or {}
    motifs: list[str] = []
    for slide in slides:
        scene = str(slide.get("visual_scene") or "").strip()
        if scene and scene not in motifs:
            motifs.append(scene)
        if len(motifs) >= 6:
            break
    context = source_context(deck, run_dir)
    return {
        "schema_version": "1",
        "narrative_role": str(supplied.get("narrative_role") or "fictional observer and learner"),
        "identity_policy": "Use a fictional visual narrator; do not impersonate the author, Jesus, Paul, or another real person.",
        "tone": str(supplied.get("tone") or "warm, thoughtful, humble, curious"),
        "stable_identity": supplied.get(
            "stable_identity",
            [
                "small chibi human silhouette",
                "simple expressive face with stable eye spacing",
                "hand-drawn black ink with restrained flat colors",
                "one small recurring prop related to learning or carrying a message",
            ],
        ),
        "must_not_change": supplied.get(
            "must_not_change",
            ["silhouette and proportions", "face construction", "line mode", "core palette", "narrative role"],
        ),
        "source_context": context,
        "visual_motifs": motifs,
    }


def character_prompt(profile: dict[str, Any], deck: dict[str, Any]) -> dict[str, Any]:
    context = profile["source_context"]
    return {
        "use_case": "illustration-story",
        "asset_type": "run-local character identity anchor",
        "primary_request": "Create one approved fictional observer character for a hand-drawn long-form teaching deck.",
        "input_images": [],
        "scene_backdrop": "clean, empty, light paper-like background with generous padding",
        "subject": "; ".join(str(item) for item in profile["stable_identity"]),
        "style_medium": f"{context['line_mode']} hand-drawn pen-doodle illustration, chibi proportions",
        "composition_framing": "full body, centered, front-facing three-quarter neutral pose, clearly readable silhouette",
        "lighting_mood": profile["tone"],
        "color_palette": "warm paper, ink black, restrained teal, mustard, coral, and brown accents",
        "materials_textures": "slightly organic ink texture, simple flat fills, no photorealism",
        "text_verbatim": "",
        "constraints": [
            "This is a fictional observer, not a portrait of a named real person.",
            "No Korean, English, alphabetic text, numbers, logo, watermark, or lettering inside the image.",
            "Keep the character isolated and suitable as the identity reference for every later scene.",
        ],
        "avoid": ["extra characters", "busy background", "photorealism", "religious figure impersonation", "embedded text"],
        "deck_context": {
            "title": deck.get("title"),
            "language": context["language"],
            "theme": context["theme"],
        },
    }


def scene_prompt(deck: dict[str, Any], slide: dict[str, Any], anchor: str, profile: dict[str, Any]) -> dict[str, Any]:
    scene = str(slide.get("visual_scene") or slide.get("one_sentence_takeaway") or slide.get("headline") or "").strip()
    action = str(slide.get("character_action") or "observe the scene with a clear, relevant expression").strip()
    diagram = str(slide.get("diagram_type") or "metaphor")
    line_mode = str(deck.get("line_mode") or "clean")
    return {
        "use_case": "illustration-story",
        "asset_type": "hand-drawn slide illustration",
        "primary_request": scene,
        "input_images": [{"path": anchor, "role": "character_identity"}],
        "scene_backdrop": "sparse article-relevant micro-scene on a clean paper-like background",
        "subject": f"the exact same fictional observer from {anchor}; action: {action}",
        "style_medium": f"{line_mode} hand-drawn black pen line, simple flat color illustration",
        "composition_framing": f"{diagram} composition; keep the character around 20–40% of the canvas and reserve clear whitespace for HTML text",
        "lighting_mood": "warm, legible, emotionally aligned with the slide argument",
        "color_palette": "the locked anchor palette with restrained accents",
        "materials_textures": "organic ink texture, simple flat fills, no dense poster detail",
        "text_verbatim": "",
        "constraints": [
            "Use the anchor as the only character identity reference; do not use previous scene images.",
            "Do not generate Korean, English, alphabetic text, numbers, labels, logos, or watermarks inside the image.",
            "All explanatory and presentation text is rendered by HTML outside the image.",
            "Preserve the anchor silhouette, face, proportions, clothing palette, and recurring prop.",
        ],
        "avoid": ["embedded text", "previous scene as reference", "generic stock art", "character dominating the evidence", "busy background"],
        "character_profile": profile,
    }


def _slide_image_target(slide: dict[str, Any], index: int) -> str:
    value = slide.get("image")
    if value:
        return relative_path(value, f"slide {index} image", required_prefix="illustrations")
    slide_id = safe_slug(slide.get("id"), f"slide-{index:02d}")
    return f"illustrations/{index:02d}-{slide_id}.png"


def _load_deck_for_plan(deck_path: Path) -> dict[str, Any]:
    data = load_json(deck_path)
    slides = data.get("slides")
    if not isinstance(slides, list) or not slides:
        raise AssetPipelineError("deck must contain a non-empty slides array")
    for index, slide in enumerate(slides, 1):
        if not isinstance(slide, dict):
            raise AssetPipelineError(f"slide {index} must be an object")
        for field in ("id", "headline", "one_sentence_takeaway", "role"):
            if not isinstance(slide.get(field), str) or not slide[field].strip():
                raise AssetPipelineError(f"slide {index} missing non-empty {field}")
    return data


def plan_assets(deck_path: Path, *, character_reference: Path | None = None) -> Path:
    deck_path = deck_path.expanduser().resolve()
    if not deck_path.is_file():
        raise AssetPipelineError(f"deck not found: {deck_path}")
    run_dir = deck_path.parent
    deck = _load_deck_for_plan(deck_path)
    slides = [slide for slide in deck["slides"] if isinstance(slide, dict)]
    profile = character_profile(deck, slides, run_dir)
    profile_path = run_dir / "character" / "profile.json"
    if profile_path.is_file():
        profile = load_json(profile_path)

    scene_jobs: list[dict[str, Any]] = []
    for index, slide in enumerate(slides, 1):
        if str(slide.get("asset_mode") or "illustration").lower() == "none":
            continue
        target = _slide_image_target(slide, index)
        scene_jobs.append(
            {
                "job_id": str(slide["id"]),
                "kind": "scene_illustration",
                "slide_id": str(slide["id"]),
                "slide_number": index,
                "target": target,
                "references": ["character/anchor.png"],
                "required_capabilities": {"generate": True, "reference_images": True},
                "prompt_spec": scene_prompt(deck, slide, "character/anchor.png", profile),
                "status": "planned",
            }
        )

    jobs: list[dict[str, Any]] = []
    anchor_value = deck.get("character_anchor") or "character/anchor.png"
    anchor_target = relative_path(anchor_value, "character_anchor", required_prefix="character")
    anchor_path = run_dir / anchor_target
    character_source = "existing" if anchor_path.is_file() else "generated"

    if character_reference is not None:
        reference = character_reference.expanduser().resolve()
        if not reference.is_file():
            raise AssetPipelineError(f"character reference not found: {reference}")
        if anchor_path.exists() and sha256_file(anchor_path) != sha256_file(reference):
            raise AssetPipelineError(
                f"refusing to replace existing character anchor: {anchor_path}; choose a new run or remove it explicitly"
            )
        anchor_path.parent.mkdir(parents=True, exist_ok=True)
        if not anchor_path.exists():
            shutil.copy2(reference, anchor_path)
        valid, reason = validate_image(anchor_path)
        if not valid:
            raise AssetPipelineError(reason or f"invalid character reference: {anchor_path}")
        character_source = "provided"

    if scene_jobs and not anchor_path.is_file():
        jobs.append(
            {
                "job_id": "character-anchor",
                "kind": "character_anchor",
                "target": anchor_target,
                "references": [],
                "required_capabilities": {"generate": True, "reference_images": False},
                "prompt_spec": character_prompt(profile, deck),
                "status": "planned",
            }
        )
    elif anchor_path.is_file():
        valid, reason = validate_image(anchor_path)
        if not valid:
            raise AssetPipelineError(reason or f"invalid character anchor: {anchor_path}")

    for job in scene_jobs:
        target_path = run_dir / job["target"]
        if target_path.is_file():
            valid, _ = validate_image(target_path)
            if valid:
                job["status"] = "ready"
        jobs.append(job)

    plan = {
        "schema_version": PLAN_SCHEMA,
        "deck": "deck.json",
        "deck_sha256": sha256_file(deck_path),
        "status": "ready" if all(job["status"] == "ready" for job in jobs) else "planned",
        "policy": {
            "anchor_per_run": True,
            "anchor_immutable_after_scene_generation": True,
            "scene_reference_policy": "character/anchor.png only; never chain previous scenes",
            "embedded_text": "forbidden; render all presentation text in HTML",
            "overwrite": "forbidden unless an explicit future regeneration command is used",
        },
        "character": {
            "path": anchor_target,
            "source": character_source,
            "profile": profile,
            "sha256": sha256_file(anchor_path) if anchor_path.is_file() else None,
        },
        "jobs": jobs,
    }
    if not profile_path.is_file():
        write_json(profile_path, profile)
    plan_path = run_dir / "asset-plan.json"
    write_json(plan_path, plan)
    return plan_path


def _state_path(run_dir: Path) -> Path:
    return run_dir / STATE_FILE


def _load_or_initialize_state(plan: dict[str, Any]) -> dict[str, Any]:
    run_dir = Path(plan["_run_dir"])
    state_path = _state_path(run_dir)
    if state_path.is_file():
        state = load_json(state_path)
        if state.get("plan_sha256") != sha256_file(run_dir / "asset-plan.json"):
            raise AssetPipelineError("generation state belongs to a different asset-plan.json")
        return state
    state = {
        "schema_version": "1",
        "protocol": PROTOCOL,
        "plan_sha256": sha256_file(run_dir / "asset-plan.json"),
        "jobs": {},
    }
    for job in plan["jobs"]:
        state["jobs"][job["job_id"]] = {
            "status": job["status"],
            "target": job["target"],
            "kind": job["kind"],
        }
    write_json(state_path, state)
    return state


def _assert_anchor_locked(plan: dict[str, Any], state: dict[str, Any]) -> None:
    run_dir = Path(plan["_run_dir"])
    anchor_path = run_dir / plan["character"]["path"]
    if not anchor_path.is_file():
        return
    expected = plan["character"].get("sha256")
    anchor_state = state.get("jobs", {}).get("character-anchor", {})
    expected = anchor_state.get("sha256") or expected
    if expected and sha256_file(anchor_path) != expected:
        raise AssetPipelineError(
            "character anchor changed after planning; create a new run or explicitly replace the anchor"
        )


def _load_plan(plan_path: Path) -> tuple[dict[str, Any], Path]:
    plan_path = plan_path.expanduser().resolve()
    plan = load_json(plan_path)
    if plan.get("schema_version") != PLAN_SCHEMA:
        raise AssetPipelineError(f"unsupported asset plan schema: {plan.get('schema_version')!r}")
    run_dir = plan_path.parent
    deck_rel = relative_path(plan.get("deck"), "asset plan deck")
    deck_path = (run_dir / deck_rel).resolve()
    try:
        deck_path.relative_to(run_dir.resolve())
    except ValueError as exc:
        raise AssetPipelineError("asset plan deck escapes the run directory") from exc
    if not deck_path.is_file():
        raise AssetPipelineError(f"asset plan deck not found: {deck_path}")
    plan["_run_dir"] = str(run_dir)
    return plan, run_dir


def _resolve_adapter(adapter: str) -> str:
    path = Path(adapter).expanduser()
    if path.is_file():
        if not os.access(path, os.X_OK):
            raise AssetPipelineError(f"image adapter is not executable: {path}")
        return str(path.resolve())
    resolved = shutil.which(adapter)
    if resolved:
        return resolved
    raise AssetPipelineError(f"image adapter not found or not executable: {adapter}")


def _call_adapter(adapter: str, request: dict[str, Any], *, cwd: Path) -> dict[str, Any]:
    try:
        completed = subprocess.run(
            [_resolve_adapter(adapter)],
            cwd=cwd,
            input=json.dumps(request, ensure_ascii=False),
            text=True,
            capture_output=True,
            check=False,
        )
    except OSError as exc:
        raise AssetPipelineError(f"could not start image adapter: {exc}") from exc
    if completed.returncode:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise AssetPipelineError(f"image adapter failed ({completed.returncode}): {detail}")
    try:
        response = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise AssetPipelineError(f"image adapter returned non-JSON output: {completed.stdout[:300]!r}") from exc
    if not isinstance(response, dict):
        raise AssetPipelineError("image adapter response must be a JSON object")
    if response.get("protocol") != PROTOCOL:
        raise AssetPipelineError(f"image adapter protocol mismatch: {response.get('protocol')!r}")
    if response.get("status") == "error":
        raise AssetPipelineError(str(response.get("error") or "image adapter returned an error"))
    return response


def _require_capability(capabilities: dict[str, Any], name: str, job: dict[str, Any]) -> None:
    if capabilities.get(name) is not True:
        raise AssetPipelineError(
            f"adapter does not support required capability {name!r} for job {job['job_id']!r}; "
            "select an adapter with reference-image support"
        )


def _safe_result_metadata(response: dict[str, Any]) -> dict[str, Any]:
    metadata: dict[str, Any] = {}
    for key in ("provider", "model", "request_id", "adapter_version"):
        value = response.get(key)
        if isinstance(value, (str, int, float, bool)):
            metadata[key] = value
    return metadata


def _write_manifest(plan: dict[str, Any], state: dict[str, Any]) -> Path:
    run_dir = Path(plan["_run_dir"])
    character_path = run_dir / plan["character"]["path"]
    character = {
        "path": plan["character"]["path"],
        "source": plan["character"]["source"],
        "sha256": sha256_file(character_path) if character_path.is_file() else None,
        "role": "fixed identity anchor for every scene",
    }
    scenes: list[dict[str, Any]] = []
    for job in plan["jobs"]:
        if job["kind"] != "scene_illustration":
            continue
        target = run_dir / job["target"]
        scenes.append(
            {
                "slide": job["slide_id"],
                "path": job["target"],
                "sha256": sha256_file(target),
                "references": job["references"],
                "status": state["jobs"][job["job_id"]]["status"],
            }
        )
    providers = {
        job_id: value.get("provider_metadata", {})
        for job_id, value in state["jobs"].items()
        if value.get("provider_metadata")
    }
    manifest = {
        "schema_version": "1",
        "character_anchor": character,
        "scene_assets": scenes,
        "generation": {
            "protocol": PROTOCOL,
            "provider_metadata_by_job": providers,
            "reference_policy": "anchor only; previous scene images are never chained",
            "text_policy": "no embedded Korean, English, alphabetic text, numbers, labels, logos, or watermarks",
        },
    }
    path = run_dir / MANIFEST_FILE
    write_json(path, manifest)
    return path


def _finalize_deck(plan: dict[str, Any], state: dict[str, Any]) -> None:
    run_dir = Path(plan["_run_dir"])
    deck_path = run_dir / plan["deck"]
    if sha256_file(deck_path) != plan["deck_sha256"]:
        raise AssetPipelineError("deck.json changed after planning; create a new asset plan before finalizing")
    for job in plan["jobs"]:
        if state["jobs"].get(job["job_id"], {}).get("status") != "ready":
            raise AssetPipelineError(f"job is not ready: {job['job_id']}")
        valid, reason = validate_image(run_dir / job["target"])
        if not valid:
            raise AssetPipelineError(reason or f"invalid generated image: {job['target']}")
    _assert_anchor_locked(plan, state)
    deck = load_json(deck_path)
    scene_jobs = [job for job in plan["jobs"] if job["kind"] == "scene_illustration"]
    if scene_jobs:
        deck["character_anchor"] = plan["character"]["path"]
    by_id = {str(slide.get("id")): slide for slide in deck.get("slides", []) if isinstance(slide, dict)}
    for job in plan["jobs"]:
        if job["kind"] != "scene_illustration":
            continue
        slide = by_id.get(job["slide_id"])
        if slide is None:
            raise AssetPipelineError(f"slide disappeared from deck: {job['slide_id']}")
        slide["image"] = job["target"]
    if scene_jobs:
        deck["asset_generation"] = {
            "plan": "asset-plan.json",
            "manifest": MANIFEST_FILE,
            "protocol": PROTOCOL,
        }
    write_json(deck_path, deck)
    _write_manifest(plan, state)


def run_generation(plan_path: Path, adapter: str) -> Path:
    plan, run_dir = _load_plan(plan_path)
    state = _load_or_initialize_state(plan)
    _assert_anchor_locked(plan, state)
    pending = [job for job in plan["jobs"] if state["jobs"].get(job["job_id"], {}).get("status") != "ready"]
    capabilities: dict[str, Any] = {}
    if pending:
        response = _call_adapter(
            adapter,
            {"protocol": PROTOCOL, "operation": "capabilities"},
            cwd=run_dir,
        )
        capabilities = response.get("capabilities") or {}
        if not isinstance(capabilities, dict):
            raise AssetPipelineError("image adapter capabilities must be an object")

    for job in pending:
        if job["kind"] == "scene_illustration":
            _assert_anchor_locked(plan, state)
        target = run_dir / job["target"]
        if target.is_file():
            valid, reason = validate_image(target)
            if valid:
                state["jobs"][job["job_id"]]["status"] = "ready"
                state["jobs"][job["job_id"]]["sha256"] = sha256_file(target)
                continue
            raise AssetPipelineError(reason or f"invalid existing image: {target}")
        _require_capability(capabilities, "generate", job)
        if job["references"]:
            _require_capability(capabilities, "reference_images", job)
        stage_dir = Path(tempfile.mkdtemp(prefix=STAGING_PREFIX, dir=run_dir))
        stage_relative = (stage_dir / Path(job["target"]).name).relative_to(run_dir).as_posix()
        stage_path = run_dir / stage_relative
        request = {
            "protocol": PROTOCOL,
            "operation": "generate_with_references" if job["references"] else "generate",
            "job_id": job["job_id"],
            "kind": job["kind"],
            "prompt_spec": job["prompt_spec"],
            "references": job["references"],
            "output": {
                "path": stage_relative,
                "final_path": job["target"],
                "format": "png",
            },
            "requirements": job["required_capabilities"],
        }
        try:
            response = _call_adapter(adapter, request, cwd=run_dir)
            valid, reason = validate_image(stage_path)
            if not valid:
                raise AssetPipelineError(reason or f"adapter did not produce a valid image for {job['job_id']}")
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists():
                raise AssetPipelineError(f"refusing to overwrite existing asset: {target}")
            shutil.copy2(stage_path, target)
            state["jobs"][job["job_id"]].update(
                {
                    "status": "ready",
                    "sha256": sha256_file(target),
                    "provider_metadata": _safe_result_metadata(response),
                }
            )
            write_json(_state_path(run_dir), state)
        except AssetPipelineError as exc:
            state["jobs"][job["job_id"]].update({"status": "failed", "error": str(exc)})
            write_json(_state_path(run_dir), state)
            raise
        finally:
            shutil.rmtree(stage_dir, ignore_errors=True)

    state["status"] = "ready"
    write_json(_state_path(run_dir), state)
    _finalize_deck(plan, state)
    return run_dir / MANIFEST_FILE


def accept_asset(plan_path: Path, job_id: str, source: Path) -> Path:
    plan, run_dir = _load_plan(plan_path)
    state = _load_or_initialize_state(plan)
    job = next((item for item in plan["jobs"] if item["job_id"] == job_id), None)
    if job is None:
        raise AssetPipelineError(f"unknown asset job: {job_id}")
    if job["kind"] == "scene_illustration" and not (run_dir / plan["character"]["path"]).is_file():
        raise AssetPipelineError("accept the character anchor first")
    _assert_anchor_locked(plan, state)
    source = source.expanduser().resolve()
    valid, reason = validate_image(source)
    if not valid:
        raise AssetPipelineError(reason or f"invalid imported image: {source}")
    target = run_dir / job["target"]
    if target.exists():
        raise AssetPipelineError(f"refusing to overwrite existing asset: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    state["jobs"][job_id].update(
        {
            "status": "ready",
            "sha256": sha256_file(target),
            "provider_metadata": {"provider": "host-import"},
        }
    )
    if all(value.get("status") == "ready" for value in state["jobs"].values()):
        state["status"] = "ready"
        write_json(_state_path(run_dir), state)
        _finalize_deck(plan, state)
    else:
        write_json(_state_path(run_dir), state)
    return target


def status(plan_path: Path) -> dict[str, Any]:
    plan, run_dir = _load_plan(plan_path)
    state_path = _state_path(run_dir)
    if state_path.is_file():
        state = load_json(state_path)
        jobs = state.get("jobs", {})
    else:
        jobs = {job["job_id"]: {"status": job["status"], "target": job["target"]} for job in plan["jobs"]}
    return {
        "plan": "asset-plan.json",
        "status": "ready" if jobs and all(value.get("status") == "ready" for value in jobs.values()) else "planned",
        "jobs": jobs,
    }


def parser() -> argparse.ArgumentParser:
    command = argparse.ArgumentParser(description=__doc__)
    subparsers = command.add_subparsers(dest="command", required=True)

    plan_parser = subparsers.add_parser("plan", help="create a provider-neutral asset plan")
    plan_parser.add_argument("deck", type=Path)
    plan_parser.add_argument("--character-reference", type=Path, default=None)

    run_parser = subparsers.add_parser("run", help="run planned jobs through an executable image adapter")
    run_parser.add_argument("plan", type=Path)
    run_parser.add_argument("--adapter", required=True, help="executable implementing handdrawn-image/v1")

    accept_parser = subparsers.add_parser("accept", help="import one asset produced by a host-native image tool")
    accept_parser.add_argument("plan", type=Path)
    accept_parser.add_argument("job_id")
    accept_parser.add_argument("source", type=Path)

    status_parser = subparsers.add_parser("status", help="show generation state")
    status_parser.add_argument("plan", type=Path)
    return command


def main(argv: Sequence[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.command == "plan":
            path = plan_assets(args.deck, character_reference=args.character_reference)
            print(f"asset plan created: {path}")
        elif args.command == "run":
            path = run_generation(args.plan, args.adapter)
            print(f"assets generated and finalized: {path}")
        elif args.command == "accept":
            path = accept_asset(args.plan, args.job_id, args.source)
            print(f"asset accepted: {path}")
        elif args.command == "status":
            print(json.dumps(status(args.plan), ensure_ascii=False, indent=2))
        return 0
    except AssetPipelineError as exc:
        print(f"asset pipeline failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
