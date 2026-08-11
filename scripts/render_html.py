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
.help {{ max-width: 1280px; margin: 16px auto 0; color: #716b63; font-size: 14px; }}

@media screen and (max-width: 1360px) {{
  .app {{ padding: 18px; }}
  .viewer-shell, .toolbar, .help {{ max-width: calc(100vw - 36px); }}
  .deck-viewer {{ transform-origin: top left; transform: scale(calc((100vw - 36px) / 1280)); margin-bottom: calc(-720px * (1 - ((100vw - 36px) / 1280))); }}
}}
@media print {{
  @page {{ size: 1280px 720px; margin: 0; }}
  html, body {{ width: 1280px; height: 720px; background: white; }}
  .app {{ padding: 0; }}
  .toolbar, .help, .notes-panel {{ display: none !important; }}
  .viewer-shell, .deck-viewer {{ width: 1280px; height: 720px; max-width: none; transform: none !important; margin: 0; }}
  .slide-page, .slide-page.is-active {{ display: block; width: 1280px; height: 720px; box-shadow: none; }}
  .canvas {{ transform: none !important; zoom: .6666667; print-color-adjust: exact; -webkit-print-color-adjust: exact; }}
}}
"""
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
    </div>
  </div>
  <div class="viewer-shell">
    <div class="deck-viewer" data-deck-viewer>
      {pages}
    </div>
  </div>
  <div class="help">← → 페이지 이동 · N 스피커 노트 · P 인쇄 대화상자</div>
</main>
<script>
(() => {{
  const root = document.documentElement;
  const pages = [...document.querySelectorAll('.slide-page')];
  const current = document.querySelector('[data-current]');
  const requiredFonts = {font_list};
  let index = 0;
  function setSlide(next) {{
    index = (next + pages.length) % pages.length;
    pages.forEach((page, i) => page.classList.toggle('is-active', i === index));
    if (current) current.textContent = `${{String(index + 1).padStart(2, '0')}} / ${{String(pages.length).padStart(2, '0')}}`;
    history.replaceState(null, '', `#${{index + 1}}`);
  }}
  function toggleNotes() {{
    const panel = pages[index]?.querySelector('.notes-panel');
    if (panel) panel.classList.toggle('is-open');
  }}
  document.querySelector('[data-action="prev"]')?.addEventListener('click', () => setSlide(index - 1));
  document.querySelector('[data-action="next"]')?.addEventListener('click', () => setSlide(index + 1));
  document.querySelector('[data-action="notes"]')?.addEventListener('click', toggleNotes);
  window.addEventListener('keydown', (event) => {{
    if (event.key === 'ArrowRight' || event.key === 'PageDown') setSlide(index + 1);
    if (event.key === 'ArrowLeft' || event.key === 'PageUp') setSlide(index - 1);
    if (event.key.toLowerCase() === 'n') toggleNotes();
    if (event.key.toLowerCase() === 'p') window.print();
  }});
  const hashNumber = Number.parseInt(location.hash.slice(1), 10);
  setSlide(Number.isFinite(hashNumber) && hashNumber > 0 ? hashNumber - 1 : 0);
  function rectanglesOverlap(first, second, gap = 1) {{
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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
