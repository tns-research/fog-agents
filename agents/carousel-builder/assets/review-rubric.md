# Review rubric

Used by the model's own visual review (build-and-review, loop step 2) and by the fresh reviewer ([`../../../shared/skills/reviewing-with-fresh-eyes/SKILL.md`](../../../shared/skills/reviewing-with-fresh-eyes/SKILL.md)). Score each criterion 0, 1 or 2 for the deck, and name the slide for anything under 2. Ship at 0 errors in `qa.json` and no criterion under 2; after three rounds, ship with the open items listed.

| # | Criterion | 2 | 1 | 0 |
|---|-----------|---|---|---|
| 1 | Truth | every number and quote traces to `research.md` and a URL or approved proof, scopes are stated | a scope or date is missing | a number or a claim has no source |
| 2 | Cover | at 25 % the hook reads in one second, it gives the start of the answer, the subject's material is on it | readable but generic or slow | needs a second look, or a teaser with no content |
| 3 | One idea per slide | each slide has one point that its title states | one slide carries two ideas | several slides are lists of loose points |
| 4 | Hierarchy | title, then the number or the visual, then support: obvious at 25 % | one slide reads in the wrong order | flat hierarchy across the deck |
| 5 | Rhythm and series | calm and dense alternate, same margins, title position and footer throughout | one break in the series | every slide has the same density, or the layout jumps around |
| 6 | Space | the frame is filled on purpose, no dead band, air where it helps | one slide has an empty zone without purpose | 40 to 50 % empty slides |
| 7 | Data-viz | one accent on the message, direct labels, unit, source, readable at 25 % | a label or the scope is unclear | decorative chart, colours that encode nothing, missing source |
| 8 | Real material | photos whole, screenshots annotated, visuals drawn from the subject | one generic visual | stock-looking or unrelated decoration |
| 9 | Brand | logo small and posed on cover and CTA, accent used as the brand's, fonts loaded | one misuse | logo distorted, oversized, or on a background it vanishes into |
| 10 | Copy | active, specific, passes the writing gate, the CTA asks one question or gives one action | one weak line | slop patterns, teaser, vague CTA |
| 11 | Legibility | every text holds at feed scale, contrast clean, nothing cut | one tight spot | cut text or unreadable labels |
| 12 | No generated-deck tells | none of the tells of [`../references/design-rules.md`](../references/design-rules.md) | one tell | several |

Total out of 24. Under 20, or any 0, is a FAIL for the fresh reviewer.

How to look: the contact sheet first (series, rhythm, hierarchy at 25 %), then each PNG at full size (text, contrast, details, alignment), then the cover alone at 360 px wide.
