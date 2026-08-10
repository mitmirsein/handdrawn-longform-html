# Character continuity

## Anchor record

Create one approved anchor before scene generation. Record:

- silhouette, hair, face cues, clothing, accessories, signature prop, palette;
- proportions, eye spacing, limb length, and stable expression range;
- the narrative role: narrator, observer, participant, learner, or emotional witness;
- elements that must never change.

Use the same approved anchor file as the first character reference for every page. Store it under the run’s `character/` directory, not in the source directory.

## Scene translation

Translate the page’s argument into one concrete scene. Specify character action and expression every time; “cute character” is not an expression. Prefer maps, timelines, doors, bridges, scales, tables, paths, objects, and relationship diagrams for abstract claims.

Use this base language and select exactly one line mode:

```text
EXTREMELY cute mini pen-doodle illustration, tiny chibi subject on a large pure-white page, naive dot-eye face, simple clean flat color fills, sparse article-relevant micro-scene, lots of empty white space.
```

`rough`: visibly jittery black ink, uneven pressure, tiny contour gaps, incomplete closures, imperfect pen control.

`clean`: even confident hand-drawn black ink, closed shapes, slight organic irregularity, never vector or clip art.

Keep the character to roughly 20–40% of the canvas. Avoid dense posters, generic stock scenes, and a character that dominates the evidence diagram.

## Drift controls

- Generate every page from the approved anchor, never from the previous page.
- If a page drifts, remove that page from references and regenerate from the anchor.
- After two failed edits, restart the page instead of extending the edit chain.
- Review all pages side by side for face, hair, clothing, proportions, palette, and narrative role.
- Keep generated Korean text short. Put long quotes and explanations in ordinary slide text or notes.
