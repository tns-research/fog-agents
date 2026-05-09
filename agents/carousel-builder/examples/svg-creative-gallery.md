# Creative SVG gallery

Bespoke SVG patterns beyond the 15 helpers in `scripts/svg_helpers.py` and the 6 base patterns in `references/svg-patterns.md`. Use these when the slide needs visual punch, not a chart.

**Same hard rules apply:** brand tokens via `var(--accent)`, `var(--accent-secondary)`, `var(--text-primary)`, `var(--text-secondary)`, `var(--card-bg)`, `var(--card-border)`. Mandatory `viewBox`, no `width`/`height` attrs, no `<foreignObject>`, no `<script>`/`<style>`. `role="img" aria-hidden="true"`. `font-family="inherit"`.

---

## 1. Network graph (nodes + edges)

For "ecosystem", "stack", "team map" slides. Nodes are brand-colored, edges fade.

```svg
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 500" role="img" aria-hidden="true">
  <g stroke="var(--accent)" stroke-width="2" opacity="0.35" fill="none">
    <line x1="400" y1="250" x2="160" y2="120"/>
    <line x1="400" y1="250" x2="640" y2="120"/>
    <line x1="400" y1="250" x2="120" y2="380"/>
    <line x1="400" y1="250" x2="680" y2="380"/>
    <line x1="400" y1="250" x2="400" y2="80"/>
    <line x1="160" y1="120" x2="400" y2="80"/>
    <line x1="640" y1="120" x2="400" y2="80"/>
  </g>
  <g font-family="inherit" font-size="20" fill="var(--text-primary)" text-anchor="middle">
    <circle cx="400" cy="250" r="58" fill="var(--accent)"/>
    <text x="400" y="258" font-weight="700" fill="var(--card-bg)">core</text>
    <circle cx="400" cy="80" r="38" fill="var(--card-bg)" stroke="var(--accent)" stroke-width="3"/>
    <text x="400" y="88">data</text>
    <circle cx="160" cy="120" r="38" fill="var(--card-bg)" stroke="var(--accent)" stroke-width="3"/>
    <text x="160" y="128">api</text>
    <circle cx="640" cy="120" r="38" fill="var(--card-bg)" stroke="var(--accent)" stroke-width="3"/>
    <text x="640" y="128">ui</text>
    <circle cx="120" cy="380" r="38" fill="var(--card-bg)" stroke="var(--accent)" stroke-width="3"/>
    <text x="120" y="388">auth</text>
    <circle cx="680" cy="380" r="38" fill="var(--card-bg)" stroke="var(--accent)" stroke-width="3"/>
    <text x="680" y="388">jobs</text>
  </g>
</svg>
```

---

## 2. Speech bubble with tail

For testimonial slides without a logo helper available. Tail points down-left toward the attribution.

```svg
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 700 380" role="img" aria-hidden="true">
  <path d="M40 40 H660 Q680 40 680 60 V260 Q680 280 660 280 H180 L120 340 L140 280 H40 Q20 280 20 260 V60 Q20 40 40 40 Z"
        fill="var(--card-bg)" stroke="var(--card-border)" stroke-width="2"/>
  <text x="60" y="140" font-family="inherit" font-size="32" font-style="italic"
        fill="var(--text-primary)">"It changed how I plan content."</text>
  <text x="60" y="200" font-family="inherit" font-size="22"
        fill="var(--text-secondary)">No more 4-hour Saturday rituals.</text>
  <text x="60" y="240" font-family="inherit" font-size="20" font-weight="600"
        fill="var(--accent)">— early user, week 2</text>
</svg>
```

---

## 3. Sankey-style ribbon flow

For funnel transitions where bars look too rigid. Two ribbons converging into one outcome.

```svg
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1000 400" role="img" aria-hidden="true">
  <path d="M0 80 C300 80 300 200 600 200 L600 280 C300 280 300 80 0 160 Z"
        fill="var(--accent)" opacity="0.85"/>
  <path d="M0 280 C300 280 300 220 600 220 L600 300 C300 300 300 360 0 360 Z"
        fill="var(--accent-secondary)" opacity="0.7"/>
  <rect x="0" y="60" width="120" height="120" fill="var(--accent)"/>
  <rect x="0" y="280" width="120" height="100" fill="var(--accent-secondary)"/>
  <rect x="600" y="180" width="120" height="140" fill="var(--text-primary)"/>
  <g font-family="inherit" font-size="22" fill="var(--card-bg)" text-anchor="middle">
    <text x="60" y="128" font-weight="700">organic</text>
    <text x="60" y="338" font-weight="700">paid</text>
    <text x="660" y="258" fill="var(--bg)" font-weight="700">signups</text>
  </g>
</svg>
```

---

## 4. Concentric orbit (rings of priority)

For "what matters", "tier" slides. Center ring is brand accent, outer rings fade.

```svg
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 600 600" role="img" aria-hidden="true">
  <g fill="none" stroke="var(--accent)" stroke-width="2">
    <circle cx="300" cy="300" r="260" opacity="0.18"/>
    <circle cx="300" cy="300" r="190" opacity="0.32"/>
    <circle cx="300" cy="300" r="120" opacity="0.55"/>
  </g>
  <circle cx="300" cy="300" r="60" fill="var(--accent)"/>
  <text x="300" y="296" text-anchor="middle"
        fill="var(--card-bg)" font-family="inherit" font-size="20" font-weight="700">core</text>
  <text x="300" y="320" text-anchor="middle"
        fill="var(--card-bg)" font-family="inherit" font-size="14">value</text>
  <g font-family="inherit" font-size="20" fill="var(--text-secondary)" text-anchor="middle">
    <text x="300" y="180">retention</text>
    <text x="300" y="115">brand</text>
    <text x="300" y="50">vanity</text>
  </g>
</svg>
```

---

## 5. Hand-drawn underline scribble

For emphasizing a single word in a title. Drop in inline next to the word.

```svg
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 320 30" role="img" aria-hidden="true">
  <path d="M4 18 C 50 8, 110 26, 160 14 S 270 22, 316 12"
        fill="none" stroke="var(--accent)" stroke-width="5" stroke-linecap="round"
        stroke-dasharray="800" stroke-dashoffset="0"/>
  <path d="M14 24 C 80 18, 140 28, 220 20 S 290 26, 310 22"
        fill="none" stroke="var(--accent)" stroke-width="2.5" stroke-linecap="round" opacity="0.5"/>
</svg>
```

---

## 6. Phone / device frame

For "in the wild" mockups. Drop a `<rect>` or `<image>` inside the screen area.

```svg
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 320 640" role="img" aria-hidden="true">
  <rect x="10" y="10" width="300" height="620" rx="42"
        fill="var(--card-bg)" stroke="var(--card-border)" stroke-width="3"/>
  <rect x="22" y="22" width="276" height="596" rx="32"
        fill="var(--bg-alt, #0a0e2a)"/>
  <rect x="118" y="34" width="84" height="20" rx="10" fill="var(--card-bg)"/>
  <!-- screen content area is x:22 y:22 w:276 h:596 - drop content here -->
  <g transform="translate(40, 90)">
    <rect width="220" height="48" rx="10" fill="var(--accent)"/>
    <rect y="80" width="180" height="14" rx="7" fill="var(--text-secondary)" opacity="0.45"/>
    <rect y="110" width="220" height="14" rx="7" fill="var(--text-secondary)" opacity="0.45"/>
    <rect y="160" width="220" height="120" rx="14" fill="var(--accent-secondary)" opacity="0.18"/>
    <rect y="300" width="140" height="40" rx="20" fill="var(--accent)"/>
  </g>
</svg>
```

---

## 7. Geometric mountain landscape

For "the climb", "milestone" slides. Three peaks, parallax feel via opacity.

```svg
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1080 500" role="img" aria-hidden="true">
  <path d="M0 500 L0 320 L220 180 L380 280 L540 140 L760 260 L920 200 L1080 320 L1080 500 Z"
        fill="var(--accent)" opacity="0.25"/>
  <path d="M0 500 L0 380 L160 280 L320 360 L480 240 L660 320 L820 280 L1080 380 L1080 500 Z"
        fill="var(--accent)" opacity="0.55"/>
  <path d="M0 500 L0 440 L120 380 L260 420 L420 360 L600 400 L780 360 L960 410 L1080 380 L1080 500 Z"
        fill="var(--accent)"/>
  <circle cx="880" cy="120" r="44" fill="var(--accent-secondary)" opacity="0.85"/>
</svg>
```

---

## 8. Sunburst rays

For "the launch", "energy" cover slides. Behind-content decorative; pair with a backdrop.

```svg
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 800" role="img" aria-hidden="true"
     preserveAspectRatio="xMidYMid slice">
  <g transform="translate(400 400)" opacity="0.18">
    <g fill="var(--accent)">
      <polygon points="0,-380 18,-60 -18,-60"/>
      <polygon points="0,-380 18,-60 -18,-60" transform="rotate(30)"/>
      <polygon points="0,-380 18,-60 -18,-60" transform="rotate(60)"/>
      <polygon points="0,-380 18,-60 -18,-60" transform="rotate(90)"/>
      <polygon points="0,-380 18,-60 -18,-60" transform="rotate(120)"/>
      <polygon points="0,-380 18,-60 -18,-60" transform="rotate(150)"/>
      <polygon points="0,-380 18,-60 -18,-60" transform="rotate(180)"/>
      <polygon points="0,-380 18,-60 -18,-60" transform="rotate(210)"/>
      <polygon points="0,-380 18,-60 -18,-60" transform="rotate(240)"/>
      <polygon points="0,-380 18,-60 -18,-60" transform="rotate(270)"/>
      <polygon points="0,-380 18,-60 -18,-60" transform="rotate(300)"/>
      <polygon points="0,-380 18,-60 -18,-60" transform="rotate(330)"/>
    </g>
  </g>
</svg>
```

---

## 9. Stamp / achievement badge

For "shipped", "approved", "verified" tags. Outer dotted ring, inner solid disc.

```svg
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 240 240" role="img" aria-hidden="true">
  <circle cx="120" cy="120" r="108" fill="none" stroke="var(--accent)" stroke-width="3"
          stroke-dasharray="5,8"/>
  <circle cx="120" cy="120" r="84" fill="var(--accent)"/>
  <text x="120" y="115" text-anchor="middle"
        font-family="inherit" font-size="22" font-weight="700"
        fill="var(--card-bg)" letter-spacing="0.1em">SHIPPED</text>
  <text x="120" y="148" text-anchor="middle"
        font-family="inherit" font-size="14"
        fill="var(--card-bg)" opacity="0.85" letter-spacing="0.18em">v1.0 / 2026</text>
</svg>
```

---

## 10. Polaroid photo frame

For "in the field" testimonial / behind-the-scenes. Drop an `<image href="..."/>` inside the inner rect.

```svg
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 360 420" role="img" aria-hidden="true">
  <g transform="rotate(-3 180 210)">
    <rect x="20" y="20" width="320" height="380" fill="var(--accent-secondary)"
          stroke="var(--card-border)" stroke-width="1"/>
    <rect x="40" y="40" width="280" height="280" fill="var(--bg-alt, #0a0e2a)"/>
    <text x="180" y="370" text-anchor="middle"
          font-family="inherit" font-size="22" font-style="italic"
          fill="var(--bg)">first user, week 1</text>
  </g>
</svg>
```

---

## 11. Calendar grid mini (highlight a day)

For "deadline", "shipped on", "launch week" slides.

```svg
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 480 380" role="img" aria-hidden="true">
  <rect x="20" y="20" width="440" height="340" rx="14"
        fill="var(--card-bg)" stroke="var(--card-border)" stroke-width="2"/>
  <text x="40" y="68" font-family="inherit" font-size="22" font-weight="600"
        fill="var(--text-secondary)">May 2026</text>
  <g font-family="inherit" font-size="18" fill="var(--text-muted)">
    <text x="62" y="108">M</text><text x="122" y="108">T</text><text x="182" y="108">W</text>
    <text x="242" y="108">T</text><text x="302" y="108">F</text><text x="362" y="108">S</text>
    <text x="422" y="108">S</text>
  </g>
  <g font-family="inherit" font-size="20" fill="var(--text-primary)">
    <text x="62" y="158">5</text><text x="122" y="158">6</text><text x="182" y="158">7</text>
    <text x="242" y="158">8</text>
    <circle cx="305" cy="151" r="22" fill="var(--accent)"/>
    <text x="305" y="158" text-anchor="middle" fill="var(--card-bg)" font-weight="700">9</text>
    <text x="362" y="158">10</text><text x="422" y="158">11</text>
  </g>
  <text x="40" y="240" font-family="inherit" font-size="22" font-weight="600"
        fill="var(--accent)">Friday — ship day</text>
</svg>
```

---

## 12. Constellation / dot pattern

For abstract "connect the dots" slides. Sparser than the dotted-grid background.

```svg
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 500" role="img" aria-hidden="true">
  <g fill="var(--accent)">
    <circle cx="120" cy="80" r="6"/>
    <circle cx="280" cy="180" r="9"/>
    <circle cx="460" cy="120" r="5"/>
    <circle cx="640" cy="240" r="7"/>
    <circle cx="200" cy="320" r="6"/>
    <circle cx="380" cy="380" r="9"/>
    <circle cx="600" cy="400" r="5"/>
    <circle cx="720" cy="80" r="6"/>
  </g>
  <g stroke="var(--accent)" stroke-width="1.5" opacity="0.45">
    <line x1="120" y1="80" x2="280" y2="180"/>
    <line x1="280" y1="180" x2="460" y2="120"/>
    <line x1="460" y1="120" x2="640" y2="240"/>
    <line x1="280" y1="180" x2="200" y2="320"/>
    <line x1="200" y1="320" x2="380" y2="380"/>
    <line x1="380" y1="380" x2="600" y2="400"/>
    <line x1="640" y1="240" x2="600" y2="400"/>
    <line x1="460" y1="120" x2="720" y2="80"/>
  </g>
</svg>
```

---

## 13. Code ribbon (decorative window)

For technical / "under the hood" slides. Stylized terminal frame, brand-colored chrome.

```svg
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 700 360" role="img" aria-hidden="true">
  <rect x="20" y="20" width="660" height="320" rx="14"
        fill="var(--bg-alt, #0a0e2a)" stroke="var(--card-border)" stroke-width="2"/>
  <rect x="20" y="20" width="660" height="44" rx="14"
        fill="var(--card-bg)"/>
  <circle cx="46" cy="42" r="7" fill="#ff5f56"/>
  <circle cx="68" cy="42" r="7" fill="#ffbd2e"/>
  <circle cx="90" cy="42" r="7" fill="#27c93f"/>
  <text x="350" y="48" text-anchor="middle"
        font-family="inherit" font-size="16" fill="var(--text-muted)">~/projects/carousel-builder</text>
  <g font-family="SF Mono, Menlo, monospace" font-size="20">
    <text x="50" y="120" fill="var(--accent)">$ </text>
    <text x="80" y="120" fill="var(--text-primary)">propose-angles</text>
    <text x="50" y="160" fill="var(--text-secondary)">→ 3 angles generated</text>
    <text x="50" y="200" fill="var(--accent)">$ </text>
    <text x="80" y="200" fill="var(--text-primary)">render-carousel</text>
    <text x="50" y="240" fill="var(--text-secondary)">→ 8 slides @ 1080×1350</text>
    <text x="50" y="280" fill="var(--accent-secondary)">✓ carousel.pdf written</text>
  </g>
</svg>
```

---

## 14. Vertical timeline with dots

For "roadmap", "process", "history" slides where horizontal timeline is too wide.

```svg
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 600 600" role="img" aria-hidden="true">
  <line x1="80" y1="60" x2="80" y2="540" stroke="var(--accent)" stroke-width="3" opacity="0.4"/>
  <g font-family="inherit">
    <circle cx="80" cy="80" r="14" fill="var(--accent)"/>
    <text x="120" y="78" font-size="24" font-weight="600" fill="var(--text-primary)">Q1 — research</text>
    <text x="120" y="110" font-size="18" fill="var(--text-secondary)">12 founder interviews</text>

    <circle cx="80" cy="200" r="14" fill="var(--accent)"/>
    <text x="120" y="198" font-size="24" font-weight="600" fill="var(--text-primary)">Q2 — prototype</text>
    <text x="120" y="230" font-size="18" fill="var(--text-secondary)">3 paths shipped, 2 cut</text>

    <circle cx="80" cy="320" r="14" fill="var(--accent)"/>
    <text x="120" y="318" font-size="24" font-weight="600" fill="var(--text-primary)">Q3 — launch</text>
    <text x="120" y="350" font-size="18" fill="var(--text-secondary)">closed beta with 30 users</text>

    <circle cx="80" cy="440" r="18" fill="var(--accent-secondary)"
            stroke="var(--accent)" stroke-width="3"/>
    <text x="120" y="442" font-size="24" font-weight="700" fill="var(--accent-secondary)">today</text>
    <text x="120" y="474" font-size="18" fill="var(--text-secondary)">open source release</text>
  </g>
</svg>
```

---

## 15. Annotated callout (number + arrow + caption)

For "how to read this" overlay slides. Stack 3-4 of these on a background image.

```svg
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 500 220" role="img" aria-hidden="true">
  <defs>
    <marker id="ann-arr" viewBox="0 0 10 10" refX="9" refY="5"
            markerWidth="10" markerHeight="10" orient="auto">
      <path d="M0,0 L10,5 L0,10 Z" fill="var(--accent)"/>
    </marker>
  </defs>
  <circle cx="60" cy="60" r="38" fill="var(--accent)"/>
  <text x="60" y="72" text-anchor="middle"
        font-family="inherit" font-size="36" font-weight="700"
        fill="var(--card-bg)">1</text>
  <path d="M100 60 Q200 60 200 130" fill="none"
        stroke="var(--accent)" stroke-width="3" stroke-dasharray="6,5"
        marker-end="url(#ann-arr)"/>
  <rect x="200" y="140" width="280" height="68" rx="10"
        fill="var(--card-bg)" stroke="var(--card-border)" stroke-width="2"/>
  <text x="220" y="172" font-family="inherit" font-size="20" font-weight="600"
        fill="var(--text-primary)">Topic in</text>
  <text x="220" y="196" font-family="inherit" font-size="16"
        fill="var(--text-secondary)">a single line is enough</text>
</svg>
```

---

## 16. Hexagonal honeycomb (skill matrix / values)

For "what we ship", "values", "stack" grids. Four hexagons in a 2×2 offset.

```svg
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 700 600" role="img" aria-hidden="true">
  <g font-family="inherit" font-size="22" font-weight="600" text-anchor="middle">
    <polygon points="120,80 240,80 300,180 240,280 120,280 60,180"
             fill="var(--accent)" opacity="0.95"/>
    <text x="180" y="190" fill="var(--card-bg)">speed</text>

    <polygon points="420,80 540,80 600,180 540,280 420,280 360,180"
             fill="var(--card-bg)" stroke="var(--accent)" stroke-width="3"/>
    <text x="480" y="190" fill="var(--text-primary)">trust</text>

    <polygon points="270,300 390,300 450,400 390,500 270,500 210,400"
             fill="var(--card-bg)" stroke="var(--accent)" stroke-width="3"/>
    <text x="330" y="410" fill="var(--text-primary)">craft</text>

    <polygon points="570,300 690,300 750,400 690,500 570,500 510,400"
             fill="var(--accent-secondary)"/>
    <text x="630" y="410" fill="var(--bg)">edge</text>
  </g>
</svg>
```

---

## 17. Layered cards (depth stack)

For "v1 → v2 → v3", "iterations", "shipped many times" slides.

```svg
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 700 400" role="img" aria-hidden="true">
  <rect x="60" y="80" width="380" height="240" rx="14"
        fill="var(--card-bg)" stroke="var(--card-border)" stroke-width="2"
        opacity="0.5" transform="rotate(-3 250 200)"/>
  <rect x="120" y="60" width="380" height="240" rx="14"
        fill="var(--card-bg)" stroke="var(--card-border)" stroke-width="2"
        opacity="0.75"/>
  <rect x="180" y="40" width="380" height="240" rx="14"
        fill="var(--accent)" opacity="0.95"/>
  <text x="370" y="140" text-anchor="middle"
        font-family="inherit" font-size="48" font-weight="700"
        fill="var(--card-bg)">v3.0</text>
  <text x="370" y="190" text-anchor="middle"
        font-family="inherit" font-size="22"
        fill="var(--card-bg)" opacity="0.85">shipped May 2026</text>
  <text x="370" y="230" text-anchor="middle"
        font-family="inherit" font-size="18"
        fill="var(--card-bg)" opacity="0.7">3 iterations behind</text>
</svg>
```

---

## When to use bespoke vs. helper

| Need | Use |
|---|---|
| Standard chart (bar, donut, funnel, timeline) | helper from `svg_helpers.py` |
| Decorative background | base pattern from `references/svg-patterns.md` |
| Editorial / one-off statement | bespoke from this gallery |

If you find yourself reusing a bespoke SVG more than twice across runs, promote it to a helper (see procedure at the bottom of `references/svg-patterns.md`).
