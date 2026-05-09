# Marketing frameworks

Reference for the analytical layer applied by `extracting-psychographic-profile`. Three frameworks are used in combination: STP, Need Analysis, and a B2B/B2C segmentation grid.

---

## STP: Segmentation, Targeting, Positioning

### Segmentation

Carve the market into mutually exclusive groups along a meaningful axis. The agent picks axes from the corpus, not from the offer brief.

Common axes (pick 1 to 3 per analysis, not all):

| Axis | Use when |
|------|----------|
| Role / job title | Vertical SaaS where role determines workflow |
| Stage of company | When pain shifts with team size or revenue |
| Stage of journey | Awareness, evaluation, active use, switching, abandoned |
| Sophistication | Power-user vs novice vs former power-user |
| Geography + language | When cultural or regulatory context shifts the pain |
| Industry vertical | When sector-specific compliance / workflow matters |
| Stakes | Hobby vs job-on-the-line vs regulated context |

A useful segmentation axis is one where the **language** in quotes differs across segments. If two segments use the same words, they are not distinct segments for marketing purposes.

### Targeting

Pick the primary segment using three criteria:

1. **Pain density**: highest mention count / community-resonance score in the corpus.
2. **Solution void**: weakest existing solutions per quote evidence (most negative sentiment toward incumbents, most "I tried but..." quotes).
3. **Offer fit**: agent operator confirms the offer plausibly serves this segment. This is a constraint, not derived from corpus.

A segment that scores high on (1) and (2) but the operator says the offer does not fit is documented as **adjacent opportunity** in the report appendix, not the primary target.

### Positioning

The offer's place in the prospect's mental map. Built from corpus evidence:

- **Frame of reference**: which alternatives the prospect considers (their own words, not the operator's).
- **Point of difference**: what the offer does that the alternatives do not, in language mined from the corpus' Pull-force quotes.
- **Reason to believe**: proof points (named comparable customers, metrics, public artifacts).

Positioning statements look like:
```
For [primary target], who [Push pain in their words], [offer] is the [frame of reference category] that [Pull outcome in their words]. Unlike [top alternative], [offer] [point of difference], because [reason to believe].
```

---

## Need Analysis

Decompose every escalated pain into:

- **Stated need**: what the user says they want. ("I want a faster invoicing tool.")
- **Real need**: what they actually want behind the words. ("I want my Mondays back.")
- **Unstated need**: what they expect without saying. ("I expect it to import my history without me reformatting anything.")
- **Delight need**: what would impress them. ("It auto-detects mismatched currencies before I send the invoice.")

Stated needs become subheads. Real needs become headlines. Unstated needs become onboarding promises. Delight needs become differentiators.

The Need Analysis is run **per persona** (after STP-Targeting), not for the market as a whole.

---

## B2B / B2C segmentation grid

Different markets need different segmentation grids. Use one of:

### B2B grid

| Dimension | Granularity |
|-----------|-------------|
| Company size | Solo / 2-10 / 11-50 / 51-250 / 250+ |
| Revenue stage | Pre-seed / Seed / A / B / C+ / Profitable |
| Buying role | Champion / Decision-maker / End-user / Procurement |
| Decision speed | Founder-led (days) / Manager-led (weeks) / Committee (months) |
| Vertical | SaaS / E-commerce / Services / Industrial / Public sector |

### B2C grid

| Dimension | Granularity |
|-----------|-------------|
| Life stage | Student / Early career / Family-forming / Mid-career / Pre-retirement / Retired |
| Income proxy | Sub-€2k/mo, €2-5k, €5-10k, €10k+ (or local equivalents) |
| Tech sophistication | Mainstream / Power-user / Builder |
| Frequency of need | One-shot / Occasional / Weekly / Daily |
| Emotional driver | Status / Belonging / Mastery / Convenience / Purpose |

Pick the 2 to 3 most discriminating dimensions for the specific market. Do not output the full grid.

---

## How frameworks combine in the agent workflow

```
scanning-market-signals  -> corpus of admitted quotes
        |
        v
extracting-psychographic-profile
        |
        +---> STP-Segmentation (using grid)
        +---> STP-Targeting (3-criteria choice)
        +---> Need Analysis (per persona)
        +---> JTBD Forces of Progress (per pain) [see assets/jtbd-forces-of-progress.md]
        +---> Verbatim marketing copy mining
        |
        v
output-template.md
```

The four frameworks are not redundant: STP picks who, Need Analysis decomposes what, JTBD explains the switching dynamic, and the verbatim mining produces shippable copy.

---

## Sources

- Philip Kotler: _Marketing Management_ on STP.
- Bob Moesta: _Demand-Side Sales 101_ on JTBD Forces of Progress.
- Need Analysis adapted from Kano model and standard B2B sales decomposition.
