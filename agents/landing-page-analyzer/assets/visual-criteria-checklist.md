# Visual criteria checklist (V1 to V10)

**Role.** Visual-only criteria evaluated from the rendered screenshots (`desktop.png` and `mobile.png`), not from the markdown. They sit alongside the 80-criterion LEVER rubric and feed the "Visual observations" subsection of the report. Each criterion is scored OK / Partial / Missing on each viewport, with a one-line observation.

These criteria do not enter the /100 LEVER total. They produce a separate visual verdict and a list of visual fixes.

---

## Visual hierarchy

### V1: Information hierarchy is clear
A single dominant H1, a visible primary CTA, and a readable supporting visual or value-prop block. The eye has a clear first stop, second stop, third stop. No three elements compete for the same level of attention.

| Viewport | Score | Observation |
|----------|-------|-------------|
| Desktop | OK / Partial / Missing | |
| Mobile | OK / Partial / Missing | |

### V2: The eye is naturally guided to the primary CTA
Within 2 seconds of looking at the screenshot, a first-time visitor can point at the primary CTA. Color, size, position, whitespace around it, or arrow / directional cue all work. If there are 3 buttons of equal weight, V2 fails.

| Viewport | Score | Observation |
|----------|-------|-------------|
| Desktop | OK / Partial / Missing | |
| Mobile | OK / Partial / Missing | |

### V3: No visual overload
The page is not stuffed: no auto-rotating carousel of 5 messages, no 8-tier pricing table above the fold, no 6 CTAs in the hero. White space is used. The visitor's working memory is not overloaded on first scroll.

| Viewport | Score | Observation |
|----------|-------|-------------|
| Desktop | OK / Partial / Missing | |
| Mobile | OK / Partial / Missing | |

---

## Design and brand

### V4: Design matches the price point and positioning
A $50k ACV product looks like one. A $9 / month tool also looks the part. Mismatch (cheap design at high price, or premium design at consumer price) hurts trust.

| Viewport | Score | Observation |
|----------|-------|-------------|
| Desktop | OK / Partial / Missing | |
| Mobile | OK / Partial / Missing | |

### V5: CTA contrast and distinctness
The primary CTA color is distinct from background, body text, and any secondary CTA. WCAG AA contrast ratio (4.5:1 for normal text, 3:1 for large) is met. Secondary CTA is visually quieter (outline, ghost, link).

| Viewport | Score | Observation |
|----------|-------|-------------|
| Desktop | OK / Partial / Missing | |
| Mobile | OK / Partial / Missing | |

### V6: Typography is readable
Body text is at least 16 px on desktop, 14 px on mobile. Line spacing 1.4 to 1.6. Line length 50 to 75 characters on desktop, narrower on mobile. No light-gray-on-white body text.

| Viewport | Score | Observation |
|----------|-------|-------------|
| Desktop | OK / Partial / Missing | |
| Mobile | OK / Partial / Missing | |

---

## Mobile UX (visual-only)

### V7: Touch targets are large enough
Buttons, form inputs, and tap-able list items are visually at least 44 px tall, with 8 px spacing. Checkboxes and toggles are not the actual native HTML default (often too small).

| Viewport | Score | Observation |
|----------|-------|-------------|
| Mobile | OK / Partial / Missing | |

### V8: No overlap, clipping, or overflow
Text is not cut off by a viewport edge. Sticky elements (header, chat bubble, cookie banner) do not overlap the primary CTA or hide form fields. No horizontal scroll on a 390-wide viewport.

| Viewport | Score | Observation |
|----------|-------|-------------|
| Mobile | OK / Partial / Missing | |

### V9: Primary CTA visible above the fold on mobile
On a 390 x 844 viewport (iPhone 14), the primary CTA is visible without scrolling. If the hero is full-screen with the CTA below, V9 fails.

| Viewport | Score | Observation |
|----------|-------|-------------|
| Mobile | OK / Partial / Missing | |

### V10: Images load correctly and are well framed
No broken image icons, no aspect-ratio distortion, no faces cropped at the eyes, no logos with white halos against a dark background. Hero image is preloaded so the LCP is not delayed.

| Viewport | Score | Observation |
|----------|-------|-------------|
| Desktop | OK / Partial / Missing | |
| Mobile | OK / Partial / Missing | |

---

## How to use these in the report

The visual checklist drives a dedicated "Visual observations" subsection in the report. Each row above becomes a one- or two-line observation. The output template provides the layout. Visual findings that overlap with LEVER criteria (e.g. V9 overlaps with U1) are reported once, in the LEVER table, with a `(visual)` tag.

Visual issues that have no LEVER counterpart (e.g. typography readability, image framing) live only in this section.
