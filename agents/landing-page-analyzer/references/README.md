# References

## CLIs and tools

| Tool | Used for | Repo |
|------|----------|------|
| `firecrawl` | scrape page markdown (desktop) | https://github.com/the20100/cli-skills/tree/main/firecrawl |
| `playwright` (bundled script) | desktop and mobile screenshots, cookie-banner dismissal | `agents/landing-page-analyzer/scripts/capture-page.py` |

## Frameworks

The audit is run with LEVER as the primary framework. The full cross-walk between LEVER, CXL, LIFT, and NN/g lives in `cro-frameworks.md`.

- **LEVER**: Cost, Trust, Usability, Comprehension, Motivation. Heuristic CRO framework. 80-criterion rubric in `assets/lever-checklist-80.md`.
- **CXL Institute**: clarity / relevancy / value / friction / distraction. Strongest when paid traffic is involved.
- **LIFT (WiderFunnel)**: Value Proposition, Relevance, Clarity, Distraction, Anxiety, Urgency. Useful when isolating which negative factor is binding.
- **NN/g 10 usability heuristics** (https://www.nngroup.com/articles/ten-usability-heuristics/): cross-walks mainly to the Usability dimension.

## Performance and Web Vitals

- Page Experience 2.0 (Google): https://developers.google.com/search/docs/appearance/page-experience
- Core Web Vitals (LCP, INP, CLS): https://web.dev/articles/vitals. INP replaced FID in March 2024.
- Lighthouse: https://developers.google.com/web/tools/lighthouse
- WebPageTest: https://www.webpagetest.org

## Mobile and accessibility

- Apple HIG (touch targets): https://developer.apple.com/design/human-interface-guidelines
- Material Design (touch targets, motion): https://m3.material.io
- WCAG 2.2 (contrast, focus, target size): https://www.w3.org/TR/WCAG22/

## CRO research and reading

- CXL Institute: https://cxl.com
- WiderFunnel (LIFT model): https://www.widerfunnel.com
- Joanna Wiebe (Copyhackers): messaging hierarchy, 5-second test variants.
- Talia Wolf (GetUplift): emotion-driven CRO research.
- Peep Laja (Wynter, formerly CXL): research-led optimization.
- Julian Shapiro: signal-to-noise ratio in startup positioning.

## Sister agents in the stack

- `market-signal`: feeds the **language** the analyzer should expect (pain words, common objections, verbatim quotes from the corpus).
- `seo-audit`: pairs well if the page has organic traffic. Intent gaps detected by `seo-audit` map to motivation gaps detected here.
- `cold-outreach-builder`: the landing page is the destination for cold outreach replies. Audit the page before scaling outbound.
