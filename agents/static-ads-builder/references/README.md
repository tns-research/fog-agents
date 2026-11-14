# References

External docs the agent's rules come from. Each number the scripts apply carries its source and the date it was read; when a page disagrees with a script, the page wins and the script is updated.

## Meta ad specs

| Rule | Where it is applied | Source (read 2026-10-12) |
|------|---------------------|--------------------------|
| 9:16 safe zone: leave roughly 14 % of the top, 35 % of the bottom and 6 % on each side free of text, logos and key elements (Reels; Meta gives Instagram Stories the same zone) | `scripts/adspec.py` `SAFE`, checked by `scripts/qa.py` | https://www.facebook.com/business/ads-guide/update/image/instagram-reels, https://www.facebook.com/business/ads-guide/update/video/instagram-story |
| Feed image: 4:5 recommended, 1440x1800 recommended resolution; primary text 50 to 150 characters, headline 27 characters | `scripts/render.py --width 1440`, warnings in `scripts/package_meta.py` | https://www.facebook.com/business/ads-guide/update/image/facebook-feed |
| Bulk import: Ads Manager > Import ads in bulk; export a blank template there to get the column headers of the day | `scripts/package_meta.py` column names | Ads Manager (in product) |
| Insights: `GET /<ad-account>/insights` with `level=ad`, fields `spend`, `impressions`, `inline_link_clicks`, `actions` | `scripts/perf.py` JSON reader | https://developers.facebook.com/docs/marketing-api/insights |

Feed formats rendered: 1080x1080 (1:1), 1080x1350 (4:5), 1080x1920 (9:16), or the same at 1440 px wide.

## Rendering and checks

- Playwright for Python (local Chromium): https://playwright.dev/python/
- WCAG 2.1 contrast ratio (4.5:1 text, 3:1 large text and graphics): https://www.w3.org/TR/WCAG21/#contrast-minimum
- Shared render review checklist: [`../../../shared/skills/reviewing-renders/SKILL.md`](../../../shared/skills/reviewing-renders/SKILL.md)

## Image generation for plates (capability `image_gen`)

`scripts/render_ads.py --provider <fal|openai|manual>`, only for text-free photographic plates written by `scripts/plates.py`. Providers and fallbacks: [`../../../shared/tools.md`](../../../shared/tools.md).

- **fal.** The script shells the `fal` CLI (binary `fal` on PATH, `FAL_KEY` or `FAL_API_KEY`), which owns endpoint routing, queue submit, polling and result extraction. Models of the menu: `fal-ai/nano-banana-2` (default), `openai/gpt-image-2`, `fal-ai/nano-banana-pro`. Check prices on the model pages before quoting Gate 2: the bundled table in `render_ads.py` is the single place to update them.
- **openai.** OpenAI Images API, `POST /v1/images/generations`: https://platform.openai.com/docs/api-reference/images. `OPENAI_API_KEY`.
- **manual.** No API: a prompt pack for the founder's own tool, then the files dropped back.

## Photo edits (mode `photo_edit`, capability `image_gen`)

`scripts/photo_edit.py --backend openai`: OpenAI Images API, `POST /v1/images/edits` (multipart: `model`, `prompt`, `size`, `quality`, `n`, the photo as `image[]`, `input_fidelity` when set; the result comes back as `b64_json`): https://platform.openai.com/docs/api-reference/images/createEdit. `OPENAI_API_KEY`. Default model `gpt-image-2`, sizes `1024x1024`, `1536x1024`, `1024x1536`. The Gate 2 price, 0.17 USD per 1536x1024 high quality output, is an estimate kept in `config.example.json` `photo_edit.price_per_image_usd`, input image tokens not included: check it on https://openai.com/api/pricing/ before quoting it, and update the config when it moves.

Method of the edit concepts (30 to 80 % of the frame, three levels, labelled prompt fields, the people described and repeated in every prompt, five fingers named, no text painted): adapted from an internal photo-branding workflow, without its brand profile; the text layer moved to the HTML renderer.

Consent: the people registry contract of `project-context` (`people.json`, read by `../../../shared/scripts/registry.py`).

## Winning recipe (mode `winning_recipe`)

Hook types: [`../assets/ad-library.md`](../assets/ad-library.md) section 2. One variable per variant is the rule of a controlled creative test: when two things change, the result cannot be attributed to either. The naming token `_t-<variable>` is read back by `scripts/perf.py` (`aggregates.test`).

## Other capabilities

`scrape` (product packshot, landing-page preflight) and `web_search` (optional angle discovery) take any provider of [`../../../shared/tools.md`](../../../shared/tools.md); both degrade to files and facts given by the founder.

## Prior art

- The funnel-aware angle library and the two spend gates come from earlier creative-brief and image agents. This agent renders locally in HTML, and adds the blind proofread, the performance loop and the Meta package.
- Brand tokens come from `project-context` (`extract-brand`); this agent only reads `brand.json`.
