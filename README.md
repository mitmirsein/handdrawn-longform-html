# Handdrawn Longform HTML

Long-form Korean or English writing is analyzed into a sourced, character-led
hand-drawn deck and rendered as static HTML and print-ready PDF.

## Instruction hierarchy

[`SKILL.md`](SKILL.md) is the workflow entry point. The files under
[`references/`](references/) are subordinate process and quality references:

- `editorial-analysis.md` — thesis and argument modeling
- `outline-schema.md` — outline and `deck.json` contract
- `rendering.md` — HTML/PDF capability and preflight rules
- `source-and-citation.md` — evidence and citation handling
- `character-continuity.md` — anchor and scene continuity
- `genre-adapters.md` — sermon, essay, column, and lecture adaptations
- `review-checklist.md` — integrated review gates and final sign-off

The references do not run as independent skills. They are read as needed by
the workflow defined in `SKILL.md`.

## Commands

Install the locked Node dependency once:

```sh
npm install
```

Run the dependency-light Python checks:

```sh
npm test
```

Validate a reviewed deck and build HTML/PDF outputs. The output basename must
not already exist unless `--allow-overwrite` is supplied.

```sh
python3 scripts/validate_outline.py output/<slug>/deck.json
python3 scripts/build_deck.py output/<slug>/deck.json \
  -o output/<slug>/<slug>-html --targets html,pdf
```

The individual adapters are also available:

```sh
npm run build:html -- output/<slug>/deck.json -o output/<slug>/<slug>.html
npm run build:pdf -- output/<slug>/<slug>.html -o output/<slug>/<slug>.pdf
```

`pdf` requires a local Chrome executable, `pdfinfo`, and `pdffonts`. A deck
declaring `font_files` must load those exact local fonts; the PDF preflight
records page count, page size, image loading, overflow, and embedded fonts.

PPTX remains an optional compatibility target:

```sh
python3 scripts/build_deck.py output/<slug>/deck.json \
  -o output/<slug>/<slug> --targets pptx
```

## Output contract

Keep source analysis, argument map, claim ledger, outline, deck specification,
character anchor, illustrations, fonts, HTML, and PDF together under
`output/<slug>/`. The renderer only assembles reviewed local assets; it does
not search for sources or generate images.

Before calling a deck complete, use
[`references/review-checklist.md`](references/review-checklist.md) as the single
sign-off sheet and follow its links for domain-specific decisions.

## Acknowledgements

Inspired by [`moongiadventures-dev/handdrawn-ppt`](https://github.com/moongiadventures-dev/handdrawn-ppt).

