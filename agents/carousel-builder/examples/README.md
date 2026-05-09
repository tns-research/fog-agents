# examples/

Anonymized real runs and visual references for `carousel-builder`.

## Real runs

- [`swanbase-explainer-20260509/`](./swanbase-explainer-20260509/) — 8-slide LinkedIn + Instagram explainer of the agent itself, rendered with `swanbase.co` brand tokens. Cover + CTA PNG previews + full slide manifest, brand snapshot, engine notes, and posting guidance.

## Visual patterns

- [`svg-creative-gallery.md`](./svg-creative-gallery.md) — 17 bespoke SVG patterns beyond the 15 helpers in `scripts/svg_helpers.py` and the 6 base patterns in `references/svg-patterns.md`. Use as inspiration when a slide needs visual punch and no chart helper fits.

## Adding a new example

A single high-quality example is worth more than verbose documentation: it pins the output format and reduces hallucination.

Naming convention: `<project>-<topic-slug>-<YYYYMMDD>/` with a `README.md` and 1 to 3 preview PNGs. Use synthetic-but-realistic data if real runs are too sensitive to anonymize. Don't commit the full PDF or all 8 PNGs (size). Cover + CTA is enough to convey the look.

Each example README should include: inputs, slide manifest, brand snapshot, engine path used, creative patterns used, and the prompt to reproduce.
