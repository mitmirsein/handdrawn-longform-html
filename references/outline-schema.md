# Outline and deck schema

## Slide outline fields

Every page in `slide-outline.md` or its JSON equivalent should contain:

```text
id                  stable slug, e.g. s07-common-core
page                1-based number
role                cover | context | claim | evidence | comparison | process | application | conclusion
headline            short visible headline
one_sentence_takeaway  the single idea the audience should retain
source_lines        source line ranges, e.g. [75, 110]
primary_references   Bible/book/report citations when present
visible_text         labels, short quote, numbers, or captions
speaker_notes       fuller reasoning and delivery cue
evidence_status      text | quote | verified | interpretation | inference | application | needs-review
visual_scene         concrete scene or diagram, not a generic illustration
diagram_type         none | timeline | map | comparison | flow | table | big-number | metaphor
character_action     pose, gesture, role, and expression
transition_to_next   why the next page follows
risk_or_open_question factual, theological, copyright, or layout risk
```

## `deck.json` minimum

The renderer consumes a reviewed, source-relative specification:

```json
{
  "title": "Deck title",
  "source": "source-analysis.md",
  "aspect_ratio": "16:9",
  "language": "ko",
  "line_mode": "clean",
  "character_anchor": "character/anchor.png",
  "theme": "rough-diary",
  "font_files": {
    "display": "fonts/GangwonEdu_OTFBoldA.woff",
    "body": "fonts/GangwonEdu_OTFLightA.woff"
  },
  "slides": [
    {
      "id": "s01-opening-question",
      "layout": "title",
      "headline": "Opening question",
      "body": "Short supporting line",
      "image": "illustrations/01-opening.png",
      "source_lines": [1, 4],
      "source": "Source passage or citation",
      "speaker_notes": "Full speaker note and delivery cue"
    }
  ]
}
```

`theme` is optional and currently accepts `clean` or `rough-diary`. `font_files`
is optional for general fixtures, but when present it must contain relative
`display` and `body` files. The HTML build fails if either declared file is
missing or if the PDF falls back to another text font. Speaker notes are kept
in HTML’s Notes panel and are intentionally omitted from printed pages.

For automatic asset generation, a slide may declare `visual_scene`,
`character_action`, `diagram_type`, and optional `asset_mode` (`illustration` or
`none`). The image field may be absent during the planning phase; the asset
pipeline assigns a relative `illustrations/` target and writes it into
`deck.json` only after the anchor and scene files pass validation. Once
`asset_generation` is present, `image` is mandatory for the strict render phase
when `asset_mode` is not `none`.

Validate before rendering. Reject missing headlines, duplicate IDs, non-relative image paths,
image decks without a run-local `character_anchor`, anchors outside `character/` or missing
from disk, empty slide arrays, and slides without a source line, reference, or explicit
`source_lines` exception for a pure cover/transition.

## Outline review gate

Show the outline in a compact table before generating a paid image batch. Approval means the user accepts the thesis, page count, page order, visible takeaways, and flagged uncertainties; it does not mean every visual is final.
