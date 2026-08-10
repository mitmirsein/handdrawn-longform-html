---
name: handdrawn-longform-html
description: Analyzes long-form Korean or English Markdown/prose such as sermons, essays, columns, lectures, and articles, then turns the argument into a sourced character-led hand-drawn HTML/PDF deck. Use when the user provides a long local document or asks to extract its thesis, argument structure, slide outline, speaker notes, and final HTML/PDF while preserving a character reference across pages.
---

# handdrawn-longform-html

Read a long document as an editor first and a slide maker second. Preserve the author’s reasoning, evidence, uncertainty, rhetorical turns, and intended application; compress paragraphs into a teachable visual sequence without turning interpretation into fact. Keep the user’s character consistent in every generated visual.

## Operating contract

- Never modify the source Markdown. Resolve relative links and embeds from the source file’s directory.
- Produce an editorial analysis and slide outline before generating paid images or a full deck. Render immediately only when the user explicitly asks for one-pass execution.
- Treat the source as authoritative for what the author says, not automatically authoritative for historical, linguistic, scientific, or theological claims. Label claims as direct text, quotation, external fact, interpretation, inference, or application.
- Ask for audience, speaking duration/page count, language, aspect ratio, character reference, and visual mode when they materially affect the result. Defaults: Korean source → Korean, 16:9, 12 pages, `clean` line mode, and a two-pass approval gate.
- Do not invent quotations, citations, source passages, image generations, tool results, or a finished PPTX. If a capability is absent, return the completed analysis, outline, prompt pack, and exact next command.

## Deliverables

Always create or report these logical artifacts, even when no files are written:

1. **Source profile** — title, genre, audience clues, thesis, central question, major sections, tone, and unresolved ambiguities.
2. **Argument map** — claim → reason → evidence/quotation → interpretation → implication/application, with source line ranges.
3. **Claim ledger** — status (`TEXT`, `QUOTE`, `HISTORICAL`, `INTERPRETATION`, `INFERENCE`, `APPLICATION`), confidence, verification need, and planned citation.
4. **Slide outline** — one central idea per page, visible takeaway, supporting evidence, source anchor, speaker note, visual metaphor, character action/expression, transition, and risk flag.
5. **Rendered deck** — reviewed image assets and `deck.json`; assemble a static `.html` deck and print-ready `.pdf`. Keep `.pptx` as an explicit compatibility target when required.

Use [outline-schema.md](references/outline-schema.md) for the field contract and [editorial-analysis.md](references/editorial-analysis.md) for the analysis method.

## Workflow

### 1. Read and segment the source

Read the complete document. Preserve heading hierarchy, paragraph order, lists, blockquotes, Bible or other passage references, Markdown links/images, and line numbers. Detect rhetorical questions, repeated phrases, examples, counterarguments, transitions, conclusions, and explicit audience applications. Summarize paragraphs; do not paste the source into slides.

Classify each block as one or more of: narrative/background, thesis, claim, evidence, quotation, interpretation, analogy, objection, application, transition, or recap. A heading is a candidate section, not automatically a slide.

### 2. Build the editorial model

Write the one-sentence thesis and the question the deck must answer. Draw the argument chain and identify the minimum claims needed to make the conclusion believable. Merge oral repetition into emphasis or speaker notes. Preserve a meaningful tension or counterpoint instead of producing a sequence of unrelated summaries.

Use the genre adapter only after the common argument model exists:

- sermon: text/exegesis → doctrine or theological interpretation → gospel/application → response;
- essay: observation/problem → thesis → development/counterpoint → insight → resonance;
- column: hook/event → stance → evidence/example → turn → concise closing;
- lecture/article: question → concepts → evidence → synthesis → practical consequence.

Read [genre-adapters.md](references/genre-adapters.md) when the genre is ambiguous or mixed.

### 3. Design the slide outline

Choose the page count from speaking time and argument density. Prefer 10–14 pages for a 20–30 minute teaching deck; fewer pages require denser speaker notes, not more text on screen. Give every page one sentence that can be answered with “why is this page here?”

For every page provide:

```text
page / role / headline
one_sentence_takeaway
source_lines and primary references
visible_text (short)
speaker_notes (full reasoning or quotation)
evidence_status and citation
visual_scene / diagram_type
character_action / expression
transition_to_next
risk_or_open_question
```

Keep quotations short on screen. Put long excerpts, cross-references, and pastoral or argumentative elaboration into speaker notes. Use a comparison, timeline, flow, table, or big number only when its structure clarifies the argument.

### 4. Verify and mark uncertainty

Before rendering, inspect every printed number, date, named person, etymology, translation claim, and external comparison. Preserve the source’s wording but mark claims needing verification; do not silently “correct” a sermon or essay. See [source-and-citation.md](references/source-and-citation.md).

For Scripture-heavy material, keep the cited passage, translation, and the speaker’s interpretation separate. Do not present a disputed translation or doctrinal inference as an uncontested fact.

### 5. Lock the character and translate meaning into scenes

Require a character reference image for image generation. Create one approved anchor, record stable identity cues, and use that exact anchor for every page. Never chain generated pages as references. The character may be narrator, observer, participant, or emotional witness; keep that role stable unless the outline explicitly changes it.

Use metaphors, maps, timelines, relationships, and object interactions for sacred or sensitive subjects. Do not make the character impersonate a real person, Jesus, Paul, or another protected/central figure unless the user explicitly requests that treatment. Read [character-continuity.md](references/character-continuity.md).

### 6. Render and review

Generate only the approved number of image assets. Use the selected hand-drawn mode and aspect ratio consistently. Review in this order: argument fidelity, source/citation accuracy, page hierarchy, Korean text legibility, character identity, visual meaning, line mode, whitespace, and file integrity.

Validate the outline with `scripts/validate_outline.py`. Assemble the reviewed local assets with `scripts/build_deck.py`, which renders static HTML first and then uses the system Chrome/Playwright adapter for PDF. The legacy `scripts/render_pptx.py` remains an optional target. If a renderer is unavailable, leave a valid `deck.json` and prompt/reference manifest; do not claim an exported deck.

The HTML renderer uses a 1920×1080 design canvas and a 16:9 print page. When
`font_files.display` and `font_files.body` are declared, both files must exist,
must load before export, and must remain the only text fonts in the PDF. Put
speaker notes in the browser’s Notes panel; the PDF contains visible slide
content and source footers only.

## Output paths

For a user project, keep generated work separate from the source:

```text
<project>/output/<slug>/
├── source-analysis.md
├── argument-map.md
├── claim-ledger.json
├── slide-outline.md
├── deck.json
├── character/anchor.png
├── illustrations/01-*.png
├── fonts/<declared-font-files>
├── <slug>.html
├── <slug>.pdf
└── <slug>.pptx          # optional compatibility output
```

Do not overwrite a previous run. Use a new slug or an explicit version directory.

## Resources

- [editorial-analysis.md](references/editorial-analysis.md) — thesis, argument graph, compression, and rhetorical analysis.
- [genre-adapters.md](references/genre-adapters.md) — sermon, essay, column, lecture, and mixed-form rules.
- [outline-schema.md](references/outline-schema.md) — `slide-outline.md`, `claim-ledger.json`, and `deck.json` fields.
- [source-and-citation.md](references/source-and-citation.md) — verification and quotation policy.
- [character-continuity.md](references/character-continuity.md) — anchor, roles, scene prompts, and drift checks.
- [rendering.md](references/rendering.md) — capability routing and deck export.
- [review-checklist.md](references/review-checklist.md) — integrated review gates and final sign-off.
