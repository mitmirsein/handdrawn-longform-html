# Rendering and capability routing

The editorial artifacts are mandatory; rendering is an adapter. Do not let a missing image or slide tool change the argument map.

## Capability order

1. Detect the host’s local file, image-generation, web/search, and slide-export capabilities.
2. Use the host’s native image tool with the anchor and required reference images when available.
3. Otherwise use an installed MCP/CLI/API adapter that documents image inputs and output paths.
4. If image generation is unavailable, write prompts and a reference manifest and leave placeholders.
5. Render a static HTML deck from the reviewed `deck.json`.
6. Convert HTML to PDF with the installed system Chrome through Playwright; preflight page size, image loading, overflow, and exact font embedding.
7. Use the legacy PPTX adapter only when `pptx` is explicitly included in the build targets.

Do not hard-code Claude, Codex, Gemini, a home directory, a provider API key, or a model name in the core workflow. Use paths relative to this skill for bundled files and paths relative to the user’s project for generated artifacts.

## Rendering gates

- Complete `source-analysis` and `slide-outline` before a paid image batch.
- Confirm page count, aspect ratio, line mode, image count, and theme before rendering.
- Keep the user’s character anchor in every generated scene.
- Validate `deck.json` before calling `scripts/build_deck.py`.
- Review visual output for claim fidelity, source labels, legible Korean, character continuity, whitespace, and file integrity.
- If `font_files` is present, fail rather than silently falling back to a system font.

## Renderer contract

`scripts/render_html.py` must only assemble reviewed local images and text. It
must not search, call an image model, or fabricate missing images. Its minimum
layouts are `title`, `content`, `full`, and `quote`; sources appear on the
slide, while speaker notes remain in the browser-only Notes panel.

`scripts/render_pdf.mjs` prints the HTML without browser chrome. The PDF page
size is 960×540 points (16:9), and a strict-font deck must contain the declared
Gangwon Education fonts without MalgunGothic, Calibri, or other fallback faces.

`scripts/render_pptx.py` remains a compatibility adapter. It must only
assemble reviewed local images and text, and is not the source of truth for
the HTML/PDF layout.

If an open-slide/React host is available, emit its page source from the same `deck.json`; keep the editorial schema independent of that renderer.
