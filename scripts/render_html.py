#!/usr/bin/env python3
"""Render a reviewed deck.json as a fixed-canvas, print-ready HTML deck.

The HTML renderer keeps the editorial deck schema independent from the legacy
PPTX renderer.  It intentionally emits a small static document with local
asset references so that the same file can be presented in a browser and
printed by the Playwright PDF adapter.
"""

from __future__ import annotations

import argparse
import html
import json
import os
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from validate_outline import validate  # noqa: E402


CANVAS_WIDTH = 1920
CANVAS_HEIGHT = 1080
PAGE_WIDTH = 1280
PAGE_HEIGHT = 720

ROLE_LABELS = {
    "cover": "OPENING",
    "context": "CONTEXT",
    "claim": "CLAIM",
    "transition": "TURN",
    "application": "LIFE",
    "recap": "RECAP",
}


def esc(value: object) -> str:
    """Escape a value for HTML while preserving deliberate line breaks."""

    if value is None:
        return ""
    # The downloadable Noonfonts WOFF declares U+00B7 as an alias for a
    # non-punctuation glyph.  Use the proper bullet glyph so Chrome does not
    # silently pull Times-Roman into the PDF for a single separator.
    return html.escape(str(value).replace("·", "•"), quote=True).replace("\n", "<br>")


def plain(value: object) -> str:
    return "" if value is None else str(value)


def rel_asset(source: Path, output: Path) -> str:
    return os.path.relpath(source.resolve(), output.parent.resolve()).replace(os.sep, "/")


REVIEW_NOTE_KEYWORDS = ("검토 필요", "검증 필요", "확인 필요", "NEEDS-REVIEW", "검토필요", "검증필요")
REVIEW_NOTE_PREFIXES = ("원문 추정", "원문 사례", "원문 주장", "어휘·역사", "명명 주체", "어원")


def clean_source_text(text: str) -> str:
    if not text:
        return ""
    raw_parts = [p.strip() for p in str(text).split("·")]
    valid_parts = []
    for part in raw_parts:
        if any(kw in part for kw in REVIEW_NOTE_KEYWORDS) or part in REVIEW_NOTE_PREFIXES:
            continue
        if part:
            valid_parts.append(part)
    return " · ".join(valid_parts)


def source_label(slide: dict) -> str:
    parts: list[str] = []
    source = clean_source_text(plain(slide.get("source")).strip())
    if source:
        parts.append(source)
    lines = slide.get("source_lines")
    if isinstance(lines, list) and lines:
        parts.append("원문 행 " + ", ".join(str(line) for line in lines))
    refs = slide.get("primary_references")
    if isinstance(refs, list) and refs:
        for ref in refs:
            cleaned_ref = clean_source_text(str(ref).strip())
            if cleaned_ref:
                parts.append(cleaned_ref)
    return " · ".join(parts)


def tokens(value: object) -> list[str]:
    raw = plain(value).strip()
    if not raw:
        return []
    result = [part.strip() for part in re.split(r"\s*(?:·|→|↔|\+)\s*", raw) if part.strip()]
    return result or [raw]


def token_row(value: object, class_name: str = "") -> str:
    items = tokens(value)
    if not items:
        return ""
    parts: list[str] = []
    for index, item in enumerate(items):
        if index:
            parts.append('<span class="token-arrow" aria-hidden="true">→</span>')
        parts.append(f'<span class="token">{esc(item)}</span>')
    return f'<div class="token-row {class_name}">' + "".join(parts) + "</div>"


def art(image: str | None, base: Path, output: Path, class_name: str = "art-wide") -> str:
    if not image:
        return ""
    path = (base / image).resolve()
    src = rel_asset(path, output)
    return (
        f'<figure class="art {class_name}">'
        f'<img src="{esc(src)}" alt="" decoding="async">'
        "</figure>"
    )


def role_badge(slide: dict) -> str:
    role = plain(slide.get("role")).strip()
    return f'<div class="role-badge">{esc(ROLE_LABELS.get(role, role.upper() or "PAGE"))}</div>'


def common_header(slide: dict, index: int, total: int, deck: dict) -> str:
    title = plain(deck.get("title"))
    return (
        '<div class="brand-mark"><span class="brand-rule"></span>'
        f'<span>{esc(title or "longform diary")}</span></div>'
        f'<div class="page-count">{index:02d} — {total:02d}</div>'
        f"{role_badge(slide)}"
    )


def slide_content(slide: dict, index: int, total: int, deck: dict, base: Path, output: Path) -> str:
    layout = plain(slide.get("layout", "content"))
    headline = esc(slide.get("headline", ""))
    takeaway = esc(slide.get("one_sentence_takeaway", ""))
    body_raw = plain(slide.get("body", "")).strip()
    body = esc(body_raw)
    visible_raw = slide.get("visible_text")

    def norm(t: object) -> str:
        return re.sub(r"[\s·→↔\+,\.\:\?!=]+", "", plain(t))

    if visible_raw is not None and body_raw and norm(visible_raw) == norm(body_raw):
        visible = None
    else:
        visible = visible_raw
    source = esc(source_label(slide))
    image = slide.get("image")

    header = common_header(slide, index, total, deck)
    source_html = f'<div class="source-footer">{source}</div>' if source else ""
    note = esc(slide.get("speaker_notes", "")) or "(스피커 노트 없음)"
    notes = (
        '<aside class="notes-panel" aria-label="스피커 노트">'
        '<div class="notes-kicker">SPEAKER NOTES</div>'
        f'<div class="notes-text">{note}</div>'
        "</aside>"
    )
    scribble = (
        '<svg class="scribble" viewBox="0 0 1920 1080" aria-hidden="true">'
        '<path d="M120 930 C390 923 570 935 810 928" />'
        '<path class="scribble-accent" d="M120 955 C300 948 455 961 610 954" />'
        "</svg>"
    )

    if layout == "title":
        main = (
            '<div class="title-layout">'
            '<div class="title-copy">'
            f'<div class="eyebrow">{esc(plain(deck.get("title")))}</div>'
            f'<h1>{headline}</h1>'
            f'<p class="takeaway">{takeaway}</p>'
            f'<div class="body-copy">{body}</div>'
            "</div>"
            f'{art(image, base, output, "art-title")}'
            "</div>"
        )
    elif layout == "full":
        main = (
            '<div class="full-layout">'
            '<div class="full-copy">'
            f'<h1>{headline}</h1>'
            f'<p class="takeaway full-takeaway">{takeaway}</p>'
            "</div>"
            f'{art(image, base, output, "art-full")}'
            f'<div class="full-caption">{esc(visible or "")}</div>'
            "</div>"
        )
    elif layout == "quote":
        main = (
            '<div class="quote-layout">'
            '<div class="quote-mark">“</div>'
            '<div class="quote-copy">'
            f'<h1>{headline}</h1>'
            f'<p class="takeaway">{takeaway}</p>'
            f'<div class="body-copy quote-body">{body}</div>'
            "</div>"
            f'{art(image, base, output, "art-quote")}'
            "</div>"
        )
    elif layout in {"comparison", "timeline", "flow", "table"}:
        row_class = f"row-{layout}"
        main = (
            f'<div class="structured-layout {row_class}">'
            '<div class="structured-copy-col">'
            f'<h1>{headline}</h1>'
            f'<p class="takeaway">{takeaway}</p>'
            f'<div class="structured-copy">{body}</div>'
            f'{token_row(visible, "structured-tokens")}'
            "</div>"
            f'{art(image, base, output, "art-structured")}'
            "</div>"
        )
    else:
        art_class = "has-art" if image else "no-art"
        main = (
            '<div class="content-layout">'
            f'<div class="content-copy {art_class}">'
            f'<h1>{headline}</h1>'
            f'<p class="takeaway">{takeaway}</p>'
            f'<div class="body-copy">{body}</div>'
            f'{token_row(visible, "content-tokens")}'
            "</div>"
            f'{art(image, base, output, "art-content")}'
            "</div>"
        )

    return (
        f'<section class="slide-page" data-slide-index="{index - 1}" '
        f'data-slide-id="{esc(slide.get("id", ""))}">'
        '<div class="canvas">'
        f"{header}{main}{source_html}{scribble}"
        f'<div class="slide-anchor">{index:02d}</div>'
        "</div>"
        f"{notes}"
        "</section>"
    )


def render(deck_path: Path, output_path: Path) -> Path:
    errors = validate(deck_path)
    if errors:
        raise ValueError("outline validation failed:\n" + "\n".join(f"- {error}" for error in errors))
    data = json.loads(deck_path.read_text(encoding="utf-8"))
    if data.get("aspect_ratio", "16:9") != "16:9":
        raise ValueError("HTML renderer currently requires aspect_ratio=16:9")

    base = deck_path.parent.resolve()
    output_path = output_path.expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    font_files = data.get("font_files") or {}
    if not isinstance(font_files, dict):
        raise ValueError("font_files must be an object with display/body paths")
    font_css: list[str] = []
    font_required = bool(font_files)
    font_family = "GangwonEducationModuche"
    for key, weight in (("display", 700), ("body", 300)):
        relative = font_files.get(key)
        if not relative:
            if font_required:
                raise ValueError(f"font_files.{key} is required when font_files is configured")
            continue
        font_path = (base / str(relative)).resolve()
        if not font_path.is_file():
            raise ValueError(f"font file not found: {font_path}")
        font_src = rel_asset(font_path, output_path)
        font_format = {
            ".otf": "opentype",
            ".ttf": "truetype",
            ".woff": "woff",
            ".woff2": "woff2",
        }.get(font_path.suffix.lower())
        if not font_format:
            raise ValueError(f"unsupported font format: {font_path.suffix}")
        font_css.append(
            "@font-face {"
            f"font-family: '{font_family}'; src: url('{font_src}') format('{font_format}'); "
            f"font-weight: {weight}; font-style: normal; font-display: block;"
            "}"
        )

    display_family = font_family if font_files else plain(data.get("font")) or "sans-serif"
    body_family = font_family if font_files else plain(data.get("body_font")) or display_family
    slides = data["slides"]
    pages = "\n".join(
        slide_content(slide, index, len(slides), data, base, output_path)
        for index, slide in enumerate(slides, 1)
    )
    font_list = json.dumps(
        ([font_family] if font_required else []), ensure_ascii=False
    )
    css = f"""
{os.linesep.join(font_css)}
:root {{
  --paper: #fffefa;
  --ink: #171717;
  --muted: #8f8a82;
  --line: #1b1b1b;
  --accent: #e24e43;
  --blue: #526d98;
  --paper-shadow: rgba(31, 27, 22, .13);
  --display: '{display_family}';
  --body: '{body_family}';
}}

* {{ box-sizing: border-box; }}
html, body {{ margin: 0; min-height: 100%; }}
body {{
  background: #e6e2db;
  color: var(--ink);
  font-family: var(--body);
  font-weight: 300;
  font-synthesis: none;
  -webkit-font-smoothing: antialiased;
}}
button {{ font: inherit; }}
.app {{ min-height: 100vh; padding: 34px; }}
.toolbar {{
  max-width: 1280px; margin: 0 auto 18px; display: flex; align-items: center;
  justify-content: space-between; gap: 16px; color: #3e3a35; font-size: 15px;
}}
.toolbar-title {{ font-family: var(--display); font-weight: 700; font-size: 24px; letter-spacing: .04em; }}
.toolbar-actions {{ display: flex; align-items: center; gap: 8px; }}
.toolbar button {{
  border: 1px solid #8f8980; background: #f7f3eb; color: #2e2a26;
  border-radius: 999px; padding: 7px 14px; cursor: pointer;
}}
.toolbar button:hover {{ background: #fffefa; }}
.viewer-shell {{ max-width: 1280px; margin: 0 auto; position: relative; }}
.deck-viewer {{ width: 1280px; height: 720px; position: relative; }}
.slide-page {{
  width: 1280px; height: 720px; position: relative; display: none;
  overflow: hidden; background: var(--paper); box-shadow: 0 12px 32px var(--paper-shadow);
  break-after: page; page-break-after: always;
}}
.slide-page.is-active {{ display: block; }}
.canvas {{
  width: {CANVAS_WIDTH}px; height: {CANVAS_HEIGHT}px; position: absolute;
  inset: 0 auto auto 0; transform: scale({PAGE_WIDTH / CANVAS_WIDTH}); isolation: isolate;
  transform-origin: top left; overflow: hidden; background: var(--paper);
}}
.canvas::before {{
  content: ''; position: absolute; inset: 0; pointer-events: none; opacity: .24;
  background-image: radial-gradient(rgba(80, 68, 52, .10) .6px, transparent .6px);
  background-size: 7px 7px;
}}
.brand-mark, .page-count, .role-badge, .slide-anchor, .source-footer, .full-caption, .art {{
  position: absolute; z-index: 2;
}}
.brand-mark {{ left: 120px; top: 42px; display: flex; align-items: center; gap: 20px;
  font-family: var(--display); font-weight: 700; font-size: 27px; letter-spacing: .10em; }}
.brand-rule {{ width: 58px; height: 4px; display: inline-block; background: var(--ink); transform: rotate(-1deg); }}
.page-count {{ right: 120px; top: 42px; font-family: var(--display); font-weight: 700; font-size: 26px; letter-spacing: .13em; }}
.role-badge {{ left: 120px; top: 107px; padding: 9px 22px 8px; border: 3px solid var(--accent);
  color: var(--accent); border-radius: 999px; font-family: var(--display); font-weight: 700; font-size: 24px; letter-spacing: .08em;
  transform: rotate(-1.5deg); }}
.slide-anchor {{ right: 122px; bottom: 62px; color: var(--muted); font-family: var(--display); font-weight: 700; font-size: 24px; }}
.source-footer {{ left: 120px; right: 400px; bottom: 62px; color: var(--muted); font-family: var(--body);
  font-weight: 300; font-size: 19px; line-height: 1.35; letter-spacing: .02em; }}
h1 {{ margin: 0; font-family: var(--display); font-weight: 700; font-size: 82px; line-height: 1.10;
  letter-spacing: -.025em; }}
.takeaway {{ margin: 0; font-family: var(--body); font-weight: 300; font-size: 29px; line-height: 1.45; color: #5f5a53; }}
.body-copy, .structured-copy {{ font-family: var(--body); font-weight: 300; font-size: 35px; line-height: 1.35; margin: 0; }}
.eyebrow {{ color: var(--muted); font-family: var(--body); font-weight: 300; font-size: 23px; letter-spacing: .04em; margin: 0; }}

.title-copy, .content-copy, .structured-copy-col, .full-copy, .quote-copy {{
  position: absolute; z-index: 2; display: flex; flex-direction: column;
}}
.title-copy {{ left: 120px; top: 190px; width: 950px; gap: 20px; }}
.title-copy h1 {{ font-size: 88px; }}
.title-copy .body-copy {{ color: var(--accent); }}

.content-copy, .structured-copy-col {{ left: 120px; top: 175px; width: 680px; gap: 20px; }}
.content-copy.no-art {{ width: 1050px; }}
.content-copy .body-copy, .structured-copy-col .structured-copy {{ color: #3b3834; }}

.full-copy {{ left: 120px; top: 175px; width: 1300px; gap: 16px; }}
.full-layout .full-caption {{ left: 125px; top: 875px; font-family: var(--display); font-weight: 700; font-size: 40px; color: var(--accent); }}

.quote-mark {{ position: absolute; z-index: 2; left: 125px; top: 170px; color: var(--accent); font-family: var(--display); font-weight: 700; font-size: 170px; line-height: .7; }}
.quote-copy {{ left: 220px; top: 225px; width: 750px; gap: 20px; }}
.quote-copy h1 {{ font-size: 91px; line-height: 1.14; }}
.quote-copy .quote-body {{ color: var(--accent); }}

.art {{ margin: 0; z-index: 1; }}
/* Opaque white illustration canvases must disappear into the paper even when
   the optional Pillow preprocessing step is not available. */
.art img {{ width: 100%; height: 100%; object-fit: contain; display: block; mix-blend-mode: multiply; }}
.art-title {{ left: 1100px; top: 340px; width: 700px; height: 530px; }}
/* Reserve a right-side art rail so body copy and tokens never sit on the image. */
.art-content, .art-structured {{ left: 850px; top: 290px; width: 950px; height: 600px; }}
/* Full-layout pages reserve a bottom caption rail below the artwork. */
.art-full {{ left: 100px; top: 390px; width: 1720px; height: 440px; }}
.art-quote {{ left: 1000px; top: 330px; width: 760px; height: 500px; }}
.structured-layout .art-structured {{ left: 850px; top: 290px; width: 950px; height: 600px; }}
.structured-tokens, .content-tokens {{ display: flex; flex-wrap: wrap; align-items: center; gap: 13px; }}
.token-row {{ display: flex; align-items: center; gap: 13px; }}
.token {{ display: inline-block; max-width: 350px; padding: 12px 19px 10px; border: 3px solid var(--ink);
  background: rgba(255,254,250,.87); border-radius: 12px 7px 15px 8px; font-family: var(--display); font-size: 31px;
  font-weight: 700; line-height: 1.1; transform: rotate(-.7deg); }}
.token:nth-child(even) {{ transform: rotate(1deg); background: rgba(226,78,67,.10); }}
.token-arrow {{ color: var(--accent); font-family: var(--display); font-weight: 700; font-size: 34px; }}
.scribble {{ position: absolute; z-index: 3; inset: 0; width: 1920px; height: 1080px; pointer-events: none; fill: none;
  stroke: var(--ink); stroke-width: 3; stroke-linecap: round; opacity: .8; }}
.scribble-accent {{ stroke: var(--accent); stroke-width: 4; }}
.notes-panel {{
  display: none; position: fixed; z-index: 20; right: 28px; bottom: 28px; width: 360px; max-height: 42vh;
  overflow: auto; padding: 18px 20px; background: #fffefa; border: 2px solid #36322e;
  box-shadow: 6px 7px 0 rgba(27,27,27,.12); transform: rotate(.7deg);
}}
.slide-page.is-active .notes-panel.is-open {{ display: block; }}
.notes-kicker {{ color: var(--accent); font-family: var(--display); font-size: 16px; letter-spacing: .08em; margin-bottom: 8px; }}
.notes-text {{ font-family: var(--body); font-size: 18px; line-height: 1.5; }}
.help {{ max-width: 1280px; margin: 16px auto 0; color: #716b63; font-size: 14px; display: flex; justify-content: space-between; align-items: center; }}

/* Drawing Canvas & Floating Presentation Tool Bar */
#drawCanvas {{
  position: absolute; top: 0; left: 0; width: 100%; height: 100%; z-index: 50; pointer-events: none;
}}
#drawCanvas.active-draw {{ pointer-events: auto; cursor: crosshair; }}
#drawCanvas.active-laser {{ pointer-events: auto; cursor: none; }}

.floating-tool-bar {{
  position: fixed; bottom: 18px; right: 24px; display: flex; gap: 4px;
  background: rgba(255, 254, 250, 0.96); backdrop-filter: blur(10px);
  border: 2px solid var(--ink); border-radius: 20px; padding: 5px 10px;
  z-index: 60; box-shadow: 4px 5px 0 rgba(27,27,27,.12); opacity: 0.35;
  transition: opacity 0.2s ease, transform 0.2s ease;
}}
.floating-tool-bar:hover, .floating-tool-bar.active {{ opacity: 1; transform: translateY(-2px); }}
.tool-btn {{
  background: transparent; border: none; font-family: var(--display); font-size: 12px;
  font-weight: 700; color: var(--ink); padding: 4px 8px; border-radius: 10px;
  cursor: pointer; transition: all 0.15s; white-space: nowrap;
}}
.tool-btn:hover {{ background: rgba(226,78,67,.12); color: var(--accent); }}
.tool-btn.active {{ background: var(--accent); color: #fff; }}

@media screen and (max-width: 1360px) {{
  .app {{ padding: 18px; }}
  .viewer-shell, .toolbar, .help {{ max-width: calc(100vw - 36px); }}
  .deck-viewer {{ transform-origin: top left; transform: scale(calc((100vw - 36px) / 1280)); margin-bottom: calc(-720px * (1 - ((100vw - 36px) / 1280))); }}
}}
@media print {{
  @page {{ size: 1280px 720px; margin: 0; }}
  html, body {{ width: 1280px; height: 720px; background: white; }}
  .app {{ padding: 0; }}
  .toolbar, .help, .notes-panel, .floating-tool-bar, #drawCanvas {{ display: none !important; }}
  .viewer-shell, .deck-viewer {{ width: 1280px; height: 720px; max-width: none; transform: none !important; margin: 0; }}
  .slide-page, .slide-page.is-active {{ display: block; width: 1280px; height: 720px; box-shadow: none; }}
  .canvas {{ transform: none !important; zoom: .6666667; print-color-adjust: exact; -webkit-print-color-adjust: exact; }}
}}
"""
    clean_title = re.sub(r"[^a-zA-Z0-9_]", "_", plain(data.get("title", "deck")).strip().lower())[:30]
    channel_name = f"handdrawn_slide_sync_{clean_title}"
    presenter_rel = f"{output_path.stem}_presenter.html"

    slide_titles_json = json.dumps([
        f"{i+1}. {plain(s.get('headline') or s.get('title') or f'Slide {i+1}')}"
        for i, s in enumerate(slides)
    ], ensure_ascii=False)
    
    slide_speeches_json = json.dumps([
        plain(s.get("speaker_notes", "")).strip() or plain(s.get("one_sentence_takeaway", ""))
        for s in slides
    ], ensure_ascii=False)

    html_doc = f"""<!doctype html>
<html lang="{esc(data.get('language', 'ko'))}" data-font-required="{'true' if font_required else 'false'}">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="deck-title" content="{esc(data.get('title', ''))}">
  <meta name="deck-slide-count" content="{len(slides)}">
  <meta name="deck-font-display" content="{esc(data.get('font', ''))}">
  <meta name="deck-theme" content="{esc(data.get('theme', 'rough-diary'))}">
  <title>{esc(data.get('title', 'Handdrawn Longform HTML'))}</title>
  <style>{css}</style>
</head>
<body>
<main class="app">
  <div class="toolbar" role="toolbar" aria-label="Deck controls">
    <div class="toolbar-title">{esc(data.get('title', 'longform diary'))}</div>
    <div class="toolbar-actions">
      <button type="button" data-action="prev" aria-label="Previous slide">←</button>
      <span data-current>01 / {len(slides):02d}</span>
      <button type="button" data-action="next" aria-label="Next slide">→</button>
      <button type="button" data-action="notes">Notes</button>
      <button type="button" data-action="presenter" style="font-weight:700; color:var(--accent);">🎙️ 발표자창</button>
    </div>
  </div>
  <div class="viewer-shell">
    <div class="deck-viewer" data-deck-viewer>
      <canvas id="drawCanvas"></canvas>
      {pages}
    </div>
  </div>
  <div class="help">
    <span>← → 이동 · N 노트 · P 인쇄 · W 발표자창 · F 전체화면</span>
    <span>판서: H 형광펜 · P 펜 · L 레이저 · C 지우기 · ESC 선택</span>
  </div>

  <div class="floating-tool-bar" id="floatingToolBar">
    <button class="tool-btn active" id="btnModeNone" title="선택 모드 (ESC)">🖱️ 선택</button>
    <button class="tool-btn" id="btnModeHighlighter" title="형광펜 (H)">🖍️ 형광펜</button>
    <button class="tool-btn" id="btnModePen" title="펜 필기 (P)">✏️ 펜</button>
    <button class="tool-btn" id="btnModeLaser" title="레이저 포인터 (L)">🔴 레이저</button>
    <button class="tool-btn" id="btnClearCanvas" title="판서 지우기 (C)">🧹 지우기</button>
    <button class="tool-btn" id="btnToggleFullscreen" title="전체화면 토글 (F)">⛶ 전체화면</button>
    <button class="tool-btn" id="btnOpenPresenter" title="발표자 전용 창 열기 (W)" style="color:var(--accent); font-weight:800;">🎙️ 발표자창</button>
  </div>
</main>
<script>
(() => {{
  const root = document.documentElement;
  const pages = [...document.querySelectorAll('.slide-page')];
  const current = document.querySelector('[data-current]');
  const viewer = document.querySelector('[data-deck-viewer]');
  const requiredFonts = {font_list};
  const syncChannelName = '{channel_name}';
  const presenterFile = '{presenter_rel}';
  const slideTitles = {slide_titles_json};
  const slideSpeeches = {slide_speeches_json};

  let index = 0;
  let notesOpen = false;

  // BroadcastChannel Sync
  const sync = new BroadcastChannel(syncChannelName);
  let presenterWindow = null;

  function broadcastState() {{
    sync.postMessage({{
      type: 'SLIDE_CHANGE',
      currentSlide: index + 1,
      totalSlides: pages.length,
      title: slideTitles[index] || '',
      nextTitle: slideTitles[index + 1] || '(마지막 슬라이드입니다)',
      speech: slideSpeeches[index] || '',
      nextSpeech: slideSpeeches[index + 1] || ''
    }});
    try {{ localStorage.setItem(syncChannelName + '_current', String(index + 1)); }} catch(e){{}}
  }}

  sync.onmessage = (e) => {{
    if (e.data && e.data.type === 'GOTO_SLIDE') {{
      setSlide(e.data.slide - 1, false);
    }} else if (e.data && e.data.type === 'REQUEST_STATE') {{
      broadcastState();
    }}
  }};

  window.addEventListener('storage', (e) => {{
    if (e.key === syncChannelName + '_current' && e.newValue) {{
      setSlide(parseInt(e.newValue, 10) - 1, false);
    }}
  }});

  function setSlide(next, broadcast = true) {{
    index = (next + pages.length) % pages.length;
    pages.forEach((page, i) => page.classList.toggle('is-active', i === index));
    if (current) current.textContent = `${{String(index + 1).padStart(2, '0')}} / ${{String(pages.length).padStart(2, '0')}}`;
    renderCanvas();
    if (broadcast) broadcastState();
  }}

  function toggleNotes() {{
    notesOpen = !notesOpen;
    pages.forEach((page) => {{
      const panel = page.querySelector('.notes-panel');
      if (panel) panel.classList.toggle('is-open', notesOpen);
    }});
  }}

  function openPresenter() {{
    if (presenterWindow && !presenterWindow.closed) {{
      presenterWindow.focus();
      broadcastState();
      return;
    }}
    presenterWindow = window.open(presenterFile, 'HanddrawnPresenterView', 'width=1100,height=750,menubar=no,toolbar=no,location=no,status=no');
    setTimeout(broadcastState, 300);
  }}

  function toggleFullscreen() {{
    if (!document.fullscreenElement) {{
      document.documentElement.requestFullscreen().catch(() => {{}});
    }} else {{
      if (document.exitFullscreen) document.exitFullscreen();
    }}
  }}

  // Canvas Drawing Overlay
  const canvas = document.getElementById('drawCanvas');
  const ctx = canvas.getContext('2d');
  let toolMode = 'none';
  let isDrawing = false;
  let currentStroke = [];
  let laserX = -100;
  let laserY = -100;
  let animFrameId = null;
  const slideBuffers = {{}};

  function resizeCanvas() {{
    if (!viewer) return;
    const rect = viewer.getBoundingClientRect();
    const dpr = window.devicePixelRatio || 1;
    canvas.width = rect.width * dpr;
    canvas.height = rect.height * dpr;
    ctx.scale(dpr, dpr);
    renderCanvas();
  }}
  window.addEventListener('resize', resizeCanvas);

  function setToolMode(mode) {{
    toolMode = mode;
    canvas.classList.remove('active-draw', 'active-laser');
    document.querySelectorAll('.tool-btn').forEach(btn => btn.classList.remove('active'));

    if (mode === 'highlighter') {{
      canvas.classList.add('active-draw');
      document.getElementById('btnModeHighlighter')?.classList.add('active');
    }} else if (mode === 'pen') {{
      canvas.classList.add('active-draw');
      document.getElementById('btnModePen')?.classList.add('active');
    }} else if (mode === 'laser') {{
      canvas.classList.add('active-laser');
      document.getElementById('btnModeLaser')?.classList.add('active');
      startLaserLoop();
    }} else {{
      document.getElementById('btnModeNone')?.classList.add('active');
    }}
  }}

  function getCanvasCoords(e) {{
    const rect = canvas.getBoundingClientRect();
    return {{ x: e.clientX - rect.left, y: e.clientY - rect.top }};
  }}

  canvas.addEventListener('mousedown', (e) => {{
    if (toolMode !== 'pen' && toolMode !== 'highlighter') return;
    isDrawing = true;
    const coords = getCanvasCoords(e);
    currentStroke = [{{ x: coords.x, y: coords.y, mode: toolMode }}];
    renderCanvas();
  }});

  canvas.addEventListener('mousemove', (e) => {{
    const coords = getCanvasCoords(e);
    if (toolMode === 'laser') {{ laserX = coords.x; laserY = coords.y; }}
    if (!isDrawing || (toolMode !== 'pen' && toolMode !== 'highlighter')) return;
    currentStroke.push({{ x: coords.x, y: coords.y, mode: toolMode }});
    renderCanvas();
  }});

  window.addEventListener('mouseup', () => {{
    if (isDrawing) {{
      isDrawing = false;
      if (currentStroke.length > 0) {{
        if (!slideBuffers[index]) {{
          const off = document.createElement('canvas');
          const rect = viewer.getBoundingClientRect();
          const dpr = window.devicePixelRatio || 1;
          off.width = rect.width * dpr; off.height = rect.height * dpr;
          slideBuffers[index] = off;
        }}
        const bCtx = slideBuffers[index].getContext('2d');
        const dpr = window.devicePixelRatio || 1;
        bCtx.save();
        bCtx.scale(dpr, dpr);
        drawPath(bCtx, currentStroke);
        bCtx.restore();
      }}
      currentStroke = [];
      renderCanvas();
    }}
  }});

  function drawPath(targetCtx, stroke) {{
    if (stroke.length < 2) return;
    const mode = stroke[0].mode;
    targetCtx.save();
    if (mode === 'highlighter') {{
      targetCtx.globalCompositeOperation = 'multiply';
      targetCtx.strokeStyle = 'rgba(255, 230, 80, 0.55)';
      targetCtx.lineWidth = 28; targetCtx.lineCap = 'round'; targetCtx.lineJoin = 'round';
    }} else if (mode === 'pen') {{
      targetCtx.globalCompositeOperation = 'source-over';
      targetCtx.strokeStyle = '#e24e43';
      targetCtx.lineWidth = 4; targetCtx.lineCap = 'round'; targetCtx.lineJoin = 'round';
    }}
    targetCtx.beginPath();
    targetCtx.moveTo(stroke[0].x, stroke[0].y);
    for (let i = 1; i < stroke.length - 1; i++) {{
      const xc = (stroke[i].x + stroke[i + 1].x) / 2;
      const yc = (stroke[i].y + stroke[i + 1].y) / 2;
      targetCtx.quadraticCurveTo(stroke[i].x, stroke[i].y, xc, yc);
    }}
    targetCtx.lineTo(stroke[stroke.length - 1].x, stroke[stroke.length - 1].y);
    targetCtx.stroke();
    targetCtx.restore();
  }}

  function renderCanvas() {{
    if (!viewer) return;
    const rect = viewer.getBoundingClientRect();
    ctx.clearRect(0, 0, rect.width, rect.height);
    const buf = slideBuffers[index];
    if (buf) ctx.drawImage(buf, 0, 0, rect.width, rect.height);
    if (currentStroke.length > 1) drawPath(ctx, currentStroke);
  }}

  function clearCanvas() {{
    const buf = slideBuffers[index];
    if (buf) {{
      const bCtx = buf.getContext('2d');
      bCtx.clearRect(0, 0, buf.width, buf.height);
    }}
    currentStroke = [];
    renderCanvas();
  }}

  function startLaserLoop() {{
    if (animFrameId) cancelAnimationFrame(animFrameId);
    function renderLaser() {{
      if (toolMode === 'laser' && laserX > 0 && laserY > 0) {{
        renderCanvas();
        ctx.save();
        ctx.beginPath();
        ctx.arc(laserX, laserY, 14, 0, Math.PI * 2);
        ctx.fillStyle = 'rgba(255, 50, 50, 0.35)';
        ctx.fill();

        ctx.beginPath();
        ctx.arc(laserX, laserY, 6, 0, Math.PI * 2);
        ctx.fillStyle = '#FF1A1A';
        ctx.shadowColor = '#FF0000';
        ctx.shadowBlur = 10;
        ctx.fill();
        ctx.restore();
      }}
      if (toolMode === 'laser') animFrameId = requestAnimationFrame(renderLaser);
    }}
    renderLaser();
  }}

  document.addEventListener('keydown', (event) => {{
    const key = event.key.toLowerCase();
    if (event.key === 'ArrowRight' || event.key === ' ' || event.key === 'PageDown') {{
      event.preventDefault(); setSlide(index + 1);
    }} else if (event.key === 'ArrowLeft' || event.key === 'PageUp' || event.key === 'Backspace') {{
      event.preventDefault(); setSlide(index - 1);
    }} else if (key === 'n') {{
      event.preventDefault(); toggleNotes();
    }} else if (key === 'w') {{
      event.preventDefault(); openPresenter();
    }} else if (key === 'f') {{
      event.preventDefault(); toggleFullscreen();
    }} else if (key === 'h') {{
      setToolMode(toolMode === 'highlighter' ? 'none' : 'highlighter');
    }} else if (key === 'p' && !event.metaKey && !event.ctrlKey) {{
      setToolMode(toolMode === 'pen' ? 'none' : 'pen');
    }} else if (key === 'l') {{
      setToolMode(toolMode === 'laser' ? 'none' : 'laser');
    }} else if (key === 'c') {{
      clearCanvas();
    }} else if (event.key === 'Escape') {{
      setToolMode('none');
    }} else if (event.key >= '1' && event.key <= '9') {{
      setSlide(parseInt(event.key, 10) - 1);
    }}
  }});

  document.querySelectorAll('[data-action="prev"]').forEach(btn => btn.addEventListener('click', () => setSlide(index - 1)));
  document.querySelectorAll('[data-action="next"]').forEach(btn => btn.addEventListener('click', () => setSlide(index + 1)));
  document.querySelectorAll('[data-action="notes"]').forEach(btn => btn.addEventListener('click', toggleNotes));
  document.querySelectorAll('[data-action="presenter"]').forEach(btn => btn.addEventListener('click', openPresenter));

  document.getElementById('btnModeNone')?.addEventListener('click', () => setToolMode('none'));
  document.getElementById('btnModeHighlighter')?.addEventListener('click', () => setToolMode(toolMode === 'highlighter' ? 'none' : 'highlighter'));
  document.getElementById('btnModePen')?.addEventListener('click', () => setToolMode(toolMode === 'pen' ? 'none' : 'pen'));
  document.getElementById('btnModeLaser')?.addEventListener('click', () => setToolMode(toolMode === 'laser' ? 'none' : 'laser'));
  document.getElementById('btnClearCanvas')?.addEventListener('click', clearCanvas);
  document.getElementById('btnToggleFullscreen')?.addEventListener('click', toggleFullscreen);
  document.getElementById('btnOpenPresenter')?.addEventListener('click', openPresenter);

  function rectanglesOverlap(first, second, gap = 4) {{
    const a = first.getBoundingClientRect();
    const b = second.getBoundingClientRect();
    return a.left < b.right - gap && a.right > b.left + gap
      && a.top < b.bottom - gap && a.bottom > b.top + gap;
  }}
  function collectLayoutIssues() {{
    const issues = [];
    pages.forEach((page, pageIndex) => {{
      const art = page.querySelector('.art');
      const layout = page.querySelector('.title-layout, .content-layout, .structured-layout, .full-layout, .quote-layout');
      if (!layout) return;
      const textNodes = [...layout.querySelectorAll('h1, .takeaway, .body-copy, .structured-copy, .token-row, .full-caption, .quote-body')].filter((node) => node.textContent.trim());

      if (art) {{
        textNodes.forEach((textNode) => {{
          if (!rectanglesOverlap(art, textNode)) return;
          issues.push({{
            page: pageIndex + 1,
            slide: page.dataset.slideId || '',
            image: art.className,
            text: textNode.className || textNode.tagName.toLowerCase(),
            textContent: textNode.textContent.trim().slice(0, 80),
          }});
        }});
      }}

      for (let i = 0; i < textNodes.length; i += 1) {{
        for (let j = i + 1; j < textNodes.length; j += 1) {{
          if (!rectanglesOverlap(textNodes[i], textNodes[j])) continue;
          issues.push({{
            page: pageIndex + 1,
            slide: page.dataset.slideId || '',
            textOverlap: true,
            first: textNodes[i].className || textNodes[i].tagName.toLowerCase(),
            second: textNodes[j].className || textNodes[j].tagName.toLowerCase(),
            firstText: textNodes[i].textContent.trim().slice(0, 40),
            secondText: textNodes[j].textContent.trim().slice(0, 40),
          }});
        }}
      }}
    }});
    return issues;
  }}
  const imagesReady = Promise.all([...document.images].map((image) => image.complete
    ? Promise.resolve()
    : new Promise((resolve, reject) => {{ image.addEventListener('load', resolve, {{once:true}}); image.addEventListener('error', reject, {{once:true}}); }})));
  const fontsReady = document.fonts.ready.then(async () => {{
    for (const family of requiredFonts) await document.fonts.load(`300 24px "${{family}}"`);
    return document.fonts.status;
  }});
  Promise.all([imagesReady, fontsReady]).then(() => {{
    window.__DECK_LAYOUT_ISSUES__ = collectLayoutIssues();
    root.dataset.deckLayoutIssues = String(window.__DECK_LAYOUT_ISSUES__.length);
    root.dataset.deckReady = 'true';
    window.__DECK_READY__ = true;
    resizeCanvas();
    setSlide(0, false);
  }}).catch((error) => {{
    root.dataset.deckError = String(error);
    window.__DECK_READY__ = false;
  }});
}})();
</script>
</body>
</html>
"""
    output_path.write_text(html_doc, encoding="utf-8")

    # Also generate Presenter View HTML
    presenter_path = output_path.with_name(presenter_rel)
    render_presenter_html(data, slides, presenter_path, channel_name)

    return output_path


def render_presenter_html(data: dict, slides: list[dict], output_path: Path, channel_name: str) -> Path:
    title = esc(plain(data.get("title", "Handdrawn Longform HTML")))
    total_slides = len(slides)

    titles = [
        f"{i+1}. {plain(s.get('headline') or s.get('title') or f'Slide {i+1}')}"
        for i, s in enumerate(slides)
    ]
    speeches = [
        plain(s.get("speaker_notes", "")).strip() or plain(s.get("one_sentence_takeaway", ""))
        for s in slides
    ]

    titles_json = json.dumps(titles, ensure_ascii=False)
    speeches_json = json.dumps(speeches, ensure_ascii=False)

    presenter_doc = f"""<!DOCTYPE html>
<html lang="{esc(data.get('language', 'ko'))}">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>🎙️ 발표자 모드 (Presenter View) · {title}</title>
  <link rel="preconnect" href="https://cdn.jsdelivr.net">
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard/dist/web/static/pretendard.css">
  <link href="https://fonts.googleapis.com/css2?family=Noto+Serif+KR:wght@400;600;700&display=swap" rel="stylesheet">
  <style>
    :root {{
      --bg: #141416;
      --card-bg: #202024;
      --border: #323238;
      --text-main: #EDEDF0;
      --text-muted: #9E9EA8;
      --accent: #E24E43;
      --green: #4EBA7C;
      --blue: #4D96FF;
    }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      background: var(--bg);
      color: var(--text-main);
      font-family: "Pretendard", system-ui, sans-serif;
      height: 100vh;
      display: flex;
      flex-direction: column;
      overflow: hidden;
      user-select: text;
    }}
    header {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 12px 24px;
      background: #1A1A1E;
      border-bottom: 1.5px solid var(--border);
    }}
    .header-left {{
      display: flex;
      align-items: center;
      gap: 16px;
    }}
    .slide-badge {{
      background: var(--accent);
      color: #fff;
      font-weight: 800;
      font-size: 15px;
      padding: 4px 12px;
      border-radius: 20px;
    }}
    .timer-container {{
      display: flex;
      align-items: center;
      gap: 10px;
      font-family: monospace;
      font-size: 22px;
      font-weight: 700;
      color: #FFF;
      background: #000;
      padding: 4px 14px;
      border-radius: 8px;
      border: 1px solid #333;
    }}
    .clock-display {{
      font-size: 15px;
      color: var(--text-muted);
      font-family: monospace;
    }}
    .main-grid {{
      display: grid;
      grid-template-columns: 1.6fr 1fr;
      gap: 20px;
      padding: 20px 24px;
      flex: 1;
      overflow: hidden;
    }}
    .notes-panel {{
      background: var(--card-bg);
      border: 1.5px solid var(--border);
      border-radius: 14px;
      padding: 24px;
      display: flex;
      flex-direction: column;
      overflow: hidden;
    }}
    .panel-header {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 16px;
      padding-bottom: 12px;
      border-bottom: 1px solid var(--border);
    }}
    .panel-title {{
      font-size: 14px;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      color: var(--accent);
    }}
    .font-btns {{
      display: flex;
      gap: 6px;
    }}
    .small-btn {{
      background: #2C2C32;
      border: 1px solid var(--border);
      color: #FFF;
      padding: 2px 10px;
      border-radius: 6px;
      cursor: pointer;
      font-size: 12px;
      font-weight: 700;
    }}
    .small-btn:hover {{ background: #3E3E48; }}
    .speech-box {{
      flex: 1;
      overflow-y: auto;
      font-family: "Noto Serif KR", serif;
      font-size: 22px;
      line-height: 1.8;
      color: #F0EDE6;
      white-space: pre-wrap;
      padding-right: 10px;
    }}
    .speech-box::-webkit-scrollbar {{ width: 6px; }}
    .speech-box::-webkit-scrollbar-thumb {{ background: #444; border-radius: 4px; }}
    .side-panel {{
      display: flex;
      flex-direction: column;
      gap: 16px;
      overflow: hidden;
    }}
    .card {{
      background: var(--card-bg);
      border: 1.5px solid var(--border);
      border-radius: 14px;
      padding: 18px 20px;
    }}
    .current-title-card {{
      border-left: 4px solid var(--accent);
    }}
    .current-slide-heading {{
      font-size: 18px;
      font-weight: 800;
      color: #FFF;
      margin-top: 4px;
      line-height: 1.4;
    }}
    .next-slide-card {{
      border-left: 4px solid var(--green);
      flex: 1;
      display: flex;
      flex-direction: column;
      overflow: hidden;
    }}
    .next-slide-heading {{
      font-size: 16px;
      font-weight: 700;
      color: var(--green);
      margin-top: 4px;
      line-height: 1.4;
    }}
    .next-speech-snippet {{
      margin-top: 10px;
      font-size: 14px;
      line-height: 1.6;
      color: var(--text-muted);
      overflow-y: auto;
      font-family: "Noto Serif KR", serif;
    }}
    footer {{
      background: #1A1A1E;
      border-top: 1.5px solid var(--border);
      padding: 12px 24px;
      display: flex;
      justify-content: space-between;
      align-items: center;
    }}
    .nav-btn {{
      background: #2D2D34;
      border: 1.5px solid var(--border);
      color: #FFF;
      font-size: 15px;
      font-weight: 700;
      padding: 8px 18px;
      border-radius: 8px;
      cursor: pointer;
      display: flex;
      align-items: center;
      gap: 8px;
      transition: all 0.15s;
    }}
    .nav-btn:hover {{ background: var(--accent); border-color: var(--accent); }}
    .jump-group {{
      display: flex;
      gap: 6px;
    }}
    .jump-btn {{
      background: #25252B;
      border: 1px solid var(--border);
      color: var(--text-muted);
      font-size: 13px;
      font-weight: 700;
      width: 32px;
      height: 32px;
      border-radius: 6px;
      cursor: pointer;
    }}
    .jump-btn.active {{
      background: var(--accent);
      color: #FFF;
      border-color: var(--accent);
    }}
    .jump-btn:hover {{ color: #FFF; border-color: #555; }}
  </style>
</head>
<body>

  <header>
    <div class="header-left">
      <span class="slide-badge" id="pSlideBadge">Slide 1 / {total_slides}</span>
      <span style="font-size:14px; font-weight:700; color:#888;">{title}</span>
    </div>
    <div style="display:flex; align-items:center; gap:20px;">
      <span class="clock-display" id="pClock">00:00:00</span>
      <div class="timer-container">
        <span id="pTimer">00:00</span>
        <button class="small-btn" id="pTimerBtn" title="타이머 일시정지/재생" style="padding:2px 6px;">⏸️</button>
        <button class="small-btn" id="pTimerReset" title="타이머 초기화" style="padding:2px 6px;">🔄</button>
      </div>
    </div>
  </header>

  <div class="main-grid">
    <div class="notes-panel">
      <div class="panel-header">
        <span class="panel-title">🗒️ 이번 슬라이드 발표 대본 (Speaker Notes)</span>
        <div class="font-btns">
          <button class="small-btn" id="pFontDown">가-</button>
          <button class="small-btn" id="pFontUp">가+</button>
        </div>
      </div>
      <div class="speech-box" id="pSpeechBox">대본을 불러오는 중...</div>
    </div>

    <div class="side-panel">
      <div class="card current-title-card">
        <span style="font-size:12px; font-weight:700; color:var(--text-muted); text-transform:uppercase;">현재 화면</span>
        <div class="current-slide-heading" id="pCurrentTitle">-</div>
      </div>

      <div class="card next-slide-card">
        <span style="font-size:12px; font-weight:700; color:var(--text-muted); text-transform:uppercase;">다음 슬라이드 미리보기</span>
        <div class="next-slide-heading" id="pNextTitle">-</div>
        <div class="next-speech-snippet" id="pNextSnippet">-</div>
      </div>
    </div>
  </div>

  <footer>
    <button class="nav-btn" id="pPrevBtn">◀ 이전 슬라이드 (←)</button>
    <div class="jump-group" id="pJumpGroup"></div>
    <button class="nav-btn" id="pNextBtn" style="background:var(--accent); border-color:var(--accent);">다음 슬라이드 ▶ (Space / →)</button>
  </footer>

  <script>
    const speeches = {speeches_json};
    const slideTitles = {titles_json};
    const syncChannelName = '{channel_name}';

    const sync = new BroadcastChannel(syncChannelName);
    let pCurrentSlide = 1;
    let pTotalSlides = slideTitles.length;
    let fontSize = 22;

    function renderPresenterUI(index) {{
      if (index < 1) index = 1;
      if (index > pTotalSlides) index = pTotalSlides;
      pCurrentSlide = index;

      document.getElementById('pSlideBadge').textContent = `Slide ${{pCurrentSlide}} / ${{pTotalSlides}}`;
      document.getElementById('pCurrentTitle').textContent = slideTitles[pCurrentSlide - 1] || '';
      document.getElementById('pNextTitle').textContent = slideTitles[pCurrentSlide] || '(마지막 슬라이드입니다)';
      document.getElementById('pSpeechBox').textContent = speeches[pCurrentSlide - 1] || '';
      
      const nextSp = speeches[pCurrentSlide] || '';
      document.getElementById('pNextSnippet').textContent = nextSp ? (nextSp.slice(0, 180) + (nextSp.length > 180 ? '...' : '')) : '-';

      document.querySelectorAll('.jump-btn').forEach((b, idx) => {{
        if (idx + 1 === pCurrentSlide) b.classList.add('active');
        else b.classList.remove('active');
      }});
    }}

    setInterval(() => {{
      const now = new Date();
      document.getElementById('pClock').textContent = now.toLocaleTimeString('ko-KR', {{ hour12: false }});
    }}, 1000);
    const now = new Date();
    document.getElementById('pClock').textContent = now.toLocaleTimeString('ko-KR', {{ hour12: false }});

    let timerSec = 0;
    let timerRunning = true;
    const timerEl = document.getElementById('pTimer');
    setInterval(() => {{
      if (timerRunning) {{
        timerSec++;
        const mins = String(Math.floor(timerSec / 60)).padStart(2, '0');
        const secs = String(timerSec % 60).padStart(2, '0');
        timerEl.textContent = `${{mins}}:${{secs}}`;
      }}
    }}, 1000);

    document.getElementById('pTimerBtn').onclick = () => {{
      timerRunning = !timerRunning;
      document.getElementById('pTimerBtn').textContent = timerRunning ? '⏸️' : '▶️';
    }};
    document.getElementById('pTimerReset').onclick = () => {{
      timerSec = 0;
      timerEl.textContent = '00:00';
    }};

    document.getElementById('pFontUp').onclick = () => {{
      if (fontSize < 40) fontSize += 2;
      document.getElementById('pSpeechBox').style.fontSize = fontSize + 'px';
    }};
    document.getElementById('pFontDown').onclick = () => {{
      if (fontSize > 14) fontSize -= 2;
      document.getElementById('pSpeechBox').style.fontSize = fontSize + 'px';
    }};

    function goToSlide(target) {{
      if (target < 1) target = 1;
      if (target > pTotalSlides) target = pTotalSlides;
      renderPresenterUI(target);
      sync.postMessage({{ type: 'GOTO_SLIDE', slide: target }});
      try {{
        localStorage.setItem(syncChannelName + '_current', target);
      }} catch(e){{}}
    }}

    document.getElementById('pNextBtn').onclick = () => goToSlide(pCurrentSlide + 1);
    document.getElementById('pPrevBtn').onclick = () => goToSlide(pCurrentSlide - 1);

    const jumpGroup = document.getElementById('pJumpGroup');
    jumpGroup.innerHTML = '';
    for (let i = 1; i <= pTotalSlides; i++) {{
      const btn = document.createElement('button');
      btn.className = 'jump-btn' + (i === 1 ? ' active' : '');
      btn.id = 'pJump' + i;
      btn.textContent = i;
      btn.onclick = () => goToSlide(i);
      jumpGroup.appendChild(btn);
    }}

    document.addEventListener('keydown', (e) => {{
      if (e.key === 'ArrowRight' || e.key === ' ' || e.key === 'PageDown' || e.key === 'Enter') {{
        e.preventDefault();
        goToSlide(pCurrentSlide + 1);
      }} else if (e.key === 'ArrowLeft' || e.key === 'PageUp' || e.key === 'Backspace') {{
        e.preventDefault();
        goToSlide(pCurrentSlide - 1);
      }} else if (e.key >= '1' && e.key <= '9') {{
        goToSlide(parseInt(e.key));
      }}
    }});

    sync.onmessage = (e) => {{
      if (e.data && e.data.type === 'SLIDE_CHANGE') {{
        renderPresenterUI(e.data.currentSlide);
      }}
    }};

    window.addEventListener('storage', (e) => {{
      if (e.key === syncChannelName + '_current' && e.newValue) {{
        renderPresenterUI(parseInt(e.newValue));
      }}
    }});

    const saved = localStorage.getItem(syncChannelName + '_current');
    renderPresenterUI(saved ? parseInt(saved) : 1);
    sync.postMessage({{ type: 'REQUEST_STATE' }});
  </script>
</body>
</html>
"""
    output_path.write_text(presenter_doc, encoding="utf-8")
    return output_path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("deck", type=Path, help="reviewed deck.json")
    parser.add_argument("-o", "--output", required=True, type=Path, help="HTML output path")
    args = parser.parse_args()
    try:
        output = render(args.deck.expanduser().resolve(), args.output)
    except (OSError, ValueError) as exc:
        print(f"HTML render failed: {exc}", file=sys.stderr)
        return 1
    print(f"HTML rendered: {output}")
    print(f"Presenter View rendered: {output.with_name(f'{output.stem}_presenter.html')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
