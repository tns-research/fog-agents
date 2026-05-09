# SVG patterns for bespoke slide visuals

When the 15 helpers in `scripts/svg_helpers.py` do not fit the slide content, the agent authors inline SVG directly in the slide spec under `svg_inline`. This file collects the reusable patterns that have come up in real runs.

**Promote any pattern reused twice to a helper in `svg_helpers.py`.** Keep this file as the on-ramp; helpers are the canonical home.

## Hard rules (every bespoke SVG must follow)

- Use brand tokens, not hex: `var(--accent)`, `var(--accent-secondary)`, `var(--text-primary)`, `var(--text-secondary)`, `var(--card-bg)`, `var(--card-border)`.
- Mandatory `viewBox`. Skip `width` and `height` attrs so CSS can scale.
- No `<foreignObject>` (breaks PDF), no `<script>`, no `<style>`.
- One `<svg>` per slide. Total markup under ~80 lines.
- Add `role="img" aria-hidden="true"` so screen readers skip decorative SVG.
- Inherit fonts via `font-family="inherit"` so brand fonts apply.

---

## Pattern: KPI tile

Big number + label + delta indicator. Useful when `number_badge` is too plain.

```svg
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 600 320" role="img" aria-hidden="true">
  <rect x="20" y="20" width="560" height="280" rx="24"
        fill="var(--card-bg)" stroke="var(--card-border)" stroke-width="2"/>
  <text x="300" y="160" text-anchor="middle"
        fill="var(--accent)" font-family="inherit" font-size="120" font-weight="700">3.4×</text>
  <text x="300" y="220" text-anchor="middle"
        fill="var(--text-primary)" font-family="inherit" font-size="28">conversion lift</text>
  <text x="300" y="262" text-anchor="middle"
        fill="var(--text-secondary)" font-family="inherit" font-size="20">vs. control, n=1,840</text>
</svg>
```

---

## Pattern: Annotated screenshot frame

When a slide carries a real screenshot but you want a brand-colored annotation overlay. Drop the `<image>` outside the SVG, use this SVG as a transparent overlay positioned above it.

```svg
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1080 720" role="img" aria-hidden="true">
  <rect x="120" y="180" width="320" height="80" rx="6"
        fill="none" stroke="var(--accent)" stroke-width="4" stroke-dasharray="8,6"/>
  <line x1="440" y1="220" x2="640" y2="120"
        stroke="var(--accent)" stroke-width="3"/>
  <circle cx="640" cy="120" r="22" fill="var(--accent)"/>
  <text x="640" y="128" text-anchor="middle" fill="var(--card-bg)"
        font-family="inherit" font-size="22" font-weight="700">1</text>
</svg>
```

---

## Pattern: Before / after bar comparison

Two horizontal bars with a single label each, accent vs. muted.

```svg
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 240" role="img" aria-hidden="true">
  <text x="20" y="40" fill="var(--text-secondary)" font-family="inherit" font-size="22">Before</text>
  <rect x="120" y="20" width="200" height="36" rx="4" fill="var(--text-secondary)" opacity="0.4"/>
  <text x="335" y="44" fill="var(--text-primary)" font-family="inherit" font-size="22">$2.40 CAC</text>

  <text x="20" y="140" fill="var(--text-secondary)" font-family="inherit" font-size="22">After</text>
  <rect x="120" y="120" width="540" height="36" rx="4" fill="var(--accent)"/>
  <text x="675" y="144" fill="var(--text-primary)" font-family="inherit" font-size="22">$0.90 CAC</text>
</svg>
```

---

## Pattern: Stage flow with arrows

Three to five labeled boxes connected by arrows. Better when the boxes are not equal-width (use `funnel` for symmetric narrowing).

```svg
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1000 200" role="img" aria-hidden="true">
  <defs>
    <marker id="arr" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto">
      <path d="M0,0 L10,5 L0,10 Z" fill="var(--accent)"/>
    </marker>
  </defs>
  <rect x="20" y="60" width="200" height="80" rx="12"
        fill="var(--card-bg)" stroke="var(--card-border)"/>
  <text x="120" y="108" text-anchor="middle" fill="var(--text-primary)"
        font-family="inherit" font-size="22">Lead</text>

  <line x1="230" y1="100" x2="380" y2="100"
        stroke="var(--accent)" stroke-width="3" marker-end="url(#arr)"/>

  <rect x="390" y="40" width="240" height="120" rx="12" fill="var(--accent)"/>
  <text x="510" y="108" text-anchor="middle" fill="var(--card-bg)"
        font-family="inherit" font-size="26" font-weight="700">Activated</text>

  <line x1="640" y1="100" x2="790" y2="100"
        stroke="var(--accent)" stroke-width="3" marker-end="url(#arr)"/>

  <rect x="800" y="60" width="180" height="80" rx="12"
        fill="var(--card-bg)" stroke="var(--card-border)"/>
  <text x="890" y="108" text-anchor="middle" fill="var(--text-primary)"
        font-family="inherit" font-size="22">Paid</text>
</svg>
```

---

## Pattern: Background blob

Decorative organic shape behind a stat or quote. Use as a `<g opacity="0.15">` overlay; never put readable text on top of it without a backdrop.

```svg
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1080 1080" role="img" aria-hidden="true"
     preserveAspectRatio="xMidYMid slice">
  <g opacity="0.15">
    <path d="M540,80 C780,80 980,300 980,540 C980,780 780,980 540,980
             C300,980 100,780 100,540 C100,300 300,80 540,80 Z"
          fill="var(--accent)"/>
  </g>
</svg>
```

---

## Pattern: Dotted grid background

Same intent as the blob, less colorful. Useful for `cover` slides.

```svg
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1080 1350" role="img" aria-hidden="true"
     preserveAspectRatio="xMidYMid slice">
  <defs>
    <pattern id="dots" width="40" height="40" patternUnits="userSpaceOnUse">
      <circle cx="20" cy="20" r="1.5" fill="var(--text-muted)" opacity="0.4"/>
    </pattern>
  </defs>
  <rect x="0" y="0" width="100%" height="100%" fill="url(#dots)"/>
</svg>
```

---

## When to promote a pattern to a helper

If you find yourself writing the same SVG twice with only data changing:

1. Extract the structure into a function in `scripts/svg_helpers.py`.
2. Signature: `(data: dict, brand: dict, width: int, height: int) -> str`.
3. Read brand colors via `_color(brand, key, default)`.
4. Add to the `HELPERS` registry dict.
5. Add a row to the table in `skills/handle-assets/SKILL.md`.
6. Move the example from this file into the helper's docstring; leave a one-liner pointer here.
