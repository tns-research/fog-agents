# examples/

Anonymized real runs and visual references for `carousel-builder`.

## Real runs

- [`swanbase-explainer-20260509/`](./swanbase-explainer-20260509/) — 8-slide LinkedIn + Instagram explainer of the agent itself, rendered with `swanbase.co` brand tokens. Full 8-slide JPEG gallery + slide manifest, brand snapshot, engine notes, and posting guidance.

## Visual patterns

- [`svg-creative-gallery.md`](./svg-creative-gallery.md) — 17 bespoke SVG patterns beyond the 15 helpers in `scripts/svg_helpers.py` and the 6 base patterns in `references/svg-patterns.md`. Use as inspiration when a slide needs visual punch and no chart helper fits.

## Adding a new example

A single high-quality example is worth more than verbose documentation: it pins the output format and reduces hallucination.

Naming convention: `<project>-<topic-slug>-<YYYYMMDD>/` with a `README.md` and the full slide gallery as **JPEG, 600px wide, quality 80** (the 8-slide swanbase example weighs ~250 KB total this way). Use synthetic-but-realistic data if real runs are too sensitive to anonymize. Don't commit the raw 2160x2700 PNGs or the multi-MB PDF, those live in the user's project folder.

Each example README should include: inputs, slide manifest, brand snapshot, engine path used, creative patterns used, and the prompt to reproduce.
