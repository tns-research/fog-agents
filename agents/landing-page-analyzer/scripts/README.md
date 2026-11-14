# Landing-page-analyzer scripts

| Script | Step | What it does |
|--------|------|--------------|
| `capture-page.py` | 1 | desktop and mobile screenshots, first screen plus the whole page in slices |
| `pagespeed.py` | 1 | Core Web Vitals (PageSpeed Insights, else local Lighthouse) |
| `probe.py` (with `probe.js`) | 7 | DOM measures per viewport, annotated captures |
| `journey.py` | 7 | scripted visit of the conversion path, every final send blocked in the browser |
| `fixes.py` | 7 | before/after render of each fix injected in the live page |
| `repo_patch.py` | 8 | repo mode: one patch per validated fix against the site source |
| `check_evidence.py` | checks | every recommendation of the sidecar resolves to a measure, a capture or a passed fix |
| `selftest.py` | n/a | offline test of probe, journey, fixes, repo_patch and check_evidence on the fixture |
| `lpa_common.py` | n/a | helpers shared by probe.py, journey.py and fixes.py (not a command) |

Each script prints its full contract with `--help` (or in its docstring).

`capture-page.py` is the single-page screenshot tool. It produces the desktop and mobile PNGs for the audit, dismisses common cookie banners, and waits for client-side redirects when a page initially returns 404. The agent calls it at Step 1 of its workflow; the user can also run it manually.

## Requirements

- Python 3.8+
- Playwright (Chromium), version in `requirements.txt`
- Pillow, for the annotated captures and boards of `probe.py`, `journey.py` and `fixes.py`
- `git`, for `repo_patch.py` and `check_evidence.py` in repo mode

## One-time setup

```bash
pip install -r agents/landing-page-analyzer/scripts/requirements.txt
playwright install chromium
```

On Windows PowerShell, run the two commands separately (no `&&`).

## Usage

```bash
python3 agents/landing-page-analyzer/scripts/capture-page.py \
  "<your-projects-root>/<project>/landing-page-analyzer/screenshots-YYYYMMDD" \
  "https://acme.example/pricing"
```

- **Argument 1:** output directory. Will be created if it does not exist.
- **Argument 2:** the landing-page URL.

## What the script does

- Opens the URL in Chromium under a desktop viewport (1280 x 900) then a mobile viewport (390 x 844).
- Saves the first screen as is, scrolls to the bottom so lazy-loaded sections render, then saves the whole page as slices of 1.5 screen heights (capped at 20 slices).
- Dismisses common cookie banners (Cookiebot, OneTrust, generic accept buttons) and newsletter modals (Klaviyo, Mailchimp common patterns).
- If the URL initially returns 404, polls for up to 5 seconds for a client-side redirect (meta refresh or JavaScript) before capturing. Captures anyway after timeout, with a warning printed.
- Uses real desktop and mobile user-agent strings so sites serve the correct responsive layout.

## Output

PNG files in the output directory:

- `desktop.png` (1280 x 900) and `mobile.png` (390 x 844): the first screen, evidence for above-the-fold rows.
- `desktop-full-01.png` to `desktop-full-NN.png` (1280 x 1350 each) and `mobile-full-01.png` to `mobile-full-NN.png` (390 x 1266 each): the whole page, evidence for every other `S` row of the LEVER grid.

After the script finishes, the agent reads the PNGs as the visual stimulus for:

- the 10-second comprehension test (`skills/running-comprehension-test/SKILL.md`),
- the visual criteria (V1 to V10 in `assets/visual-criteria-checklist.md`),
- the mobile UX checks (`assets/mobile-ux-checklist.md`),
- every `S` row of `assets/lever-grid.md`.

## pagespeed.py

```bash
python3 agents/landing-page-analyzer/scripts/pagespeed.py <out_dir> <url>
```

Standard library only. `--provider auto` (default) calls the PageSpeed Insights API v5 (mobile, no key needed at low volume, `PAGESPEED_API_KEY` raises the quota), then falls back to a local Lighthouse run through `npx` (needs Node; it reuses the Chromium installed by Playwright when `CHROME_PATH` is unset). Force one with `--provider psi` or `--provider lighthouse`. Writes `psi-mobile.json` (raw) and `psi-summary.json` (LCP, INP, CLS against the web.dev good thresholds, field data when Google has it, lab data otherwise, plus the provider used). When no provider works it exits with code 2 and the agent marks rows U023 to U028 Unverified or asks the founder to paste the values from pagespeed.web.dev.

## probe.py

```bash
python3 agents/landing-page-analyzer/scripts/probe.py <url> --out <dir> [--cta "Book a demo"] [--viewports desktop,mobile] [--locale en-US] [--timezone UTC] [--no-annotate]
```

Measures the page in the DOM instead of judging a screenshot by eye, per viewport (desktop 1280 x 900; mobile is the Playwright iPhone 13 profile: 390 x 664 visible area, 390 x 844 screen, touch, DPR 2), after load, settle and one scroll to the bottom: horizontal overflow and its offenders, tap targets failing WCAG 2.2 2.5.8 (plus the counts under 24 px and under 44 px), small text, contrast per text node, every button-like element and the primary CTA against the fold, sticky elements, layout shifts observed on this load, images (dimensions, lazy in the first screen, broken, alt, LCP element), form fields, viewport meta and H1 list, page weight. Writes `<out>/probe.json` (full measures plus a flat `summary` per viewport, the keys used by evidence references and by `fixes.json` expectations) and, unless `--no-annotate`, `<out>/probe-<viewport>.png` (annotated full page, capped at 8 screens). Exit 0 when every viewport was measured, 1 when one failed, 2 on a fatal error.

## journey.py

```bash
python3 agents/landing-page-analyzer/scripts/journey.py <journey.json> --out <dir> [--url BASE_URL] [--viewports desktop,mobile]
python3 agents/landing-page-analyzer/scripts/journey.py <journey.json> --lint
```

Follows the conversion path written in `journey.json` (example in `../examples/northdock-apply-fixture/journey.json`, step verbs and locators in `--help`), captures every step on desktop and mobile, and blocks writes by network interception: every POST, PUT, PATCH and DELETE is aborted (except `allow_write` URLs before the final step), every write during a final step is aborted, payment-host writes and newsletter endpoints are always aborted, and once a field is filled any GET carrying a typed value is aborted. Test data must use reserved values (e-mails on `example.com`, `example.org`, `example.net` or a `.test`, `.invalid`, `.example` domain). Writes `<out>/journey/<viewport>/NN-<name>.png`, `<out>/journey/journey-log.json` and `<out>/journey/journey-board.jpg`. Exit 0 ok, 1 a required step or an expect failed, 2 fatal (bad spec, unsafe test data, Playwright missing or older than 1.48), 3 safety violation (a write left the browser during a final step).

## fixes.py

```bash
python3 agents/landing-page-analyzer/scripts/fixes.py <fixes.json> --out <dir> [--url BASE_URL] [--only ID] [--combined] [--preview <jpg>]
python3 agents/landing-page-analyzer/scripts/fixes.py <fixes.json> --lint
```

Loads the page twice per viewport, once as is and once with each fix injected (CSS, text, attributes, inserted markup; shape in `--help` and in `../examples/northdock-apply-fixture/fixes.json`), measures both with `probe.js` and checks each `expect` line (`<viewport>.<metric> <op> <number>`) on the after measures. A selector that matches nothing fails the fix. Writes per fix `<out>/fixes/<id>/` (`before-<viewport>.png`, `after-<viewport>.png`, `compare-<viewport>.png`, `patch.css`, `patch.js`, `fix.json`), plus `<out>/fixes/fixes.json`, `fixes.md` and `board.jpg`. `--combined` adds the variant `all` with every patch at once. Exit 0 when every fix applied and met its expectations, 1 when one did not, 2 fatal.

## repo_patch.py

```bash
python3 agents/landing-page-analyzer/scripts/repo_patch.py --repo <site source> --fixes <run folder>/fixes [--out <run folder>] [--css-dir <dir>] [--exclude <path>]
```

Standard library plus `git`. Repo mode, run after `fixes.py`: for every fix whose `fix.json` says `pass`, finds each change in the site source and writes `repo-patches/<id>.patch` (against the untouched repo), `repo-patches/all.patch` (every ready fix at once), `repo-patches.json` (status, `path:line` per change, candidates, reason, `git apply --check` result) and `repo-patches.md` (the report section). Statuses: `ready`, `ready-needs-import` (a new `lpa-fixes.css` to import after the main stylesheet), `manual` (found in several places or nowhere: no patch), `skipped` (fix not validated). The repo is only read; an `--out` inside it exits 2. Exit 1 when a written patch fails `git apply --check`. `check_evidence.py` re-runs that check on every patch the sidecar announces ready. The full contract is in the script docstring.

## check_evidence.py

```bash
python3 agents/landing-page-analyzer/scripts/check_evidence.py <landing-audit-YYYYMMDD.json> --root <run folder> [--repo <site source>]
```

Checks that every finding scored Partial or Missing (and any finding that lists evidence), every `top_fixes` entry and every `rewrites` entry of the sidecar carries a non-empty `evidence` list, and that each reference resolves under `--root`: `probe:<viewport>.<metric>`, `journey:<viewport>/<file>.png`, `journey:step:<n>`, `fix:<id>` (status pass), `shot:<relative path>`, `psi:<key>`, `url:<https://...>`, `page:"<quoted text>"` (found in `page.md` or `page.html` when present), `patch:<id>`. Also checks that `criteria` IDs exist in the LEVER grid or the visual and mobile checklists, and in repo mode that every `repo_patches` entry matches what `repo_patch.py` recorded and that each announced patch still passes `git apply --check`. Exit 0 when everything holds, 1 when not, 2 when the sidecar cannot be read.

## selftest.py

```bash
python3 agents/landing-page-analyzer/scripts/selftest.py [--keep DIR] [--only policy|probe|journey|fixes|repo|evidence]
```

Serves `../examples/northdock-apply-fixture/site/` on a free local port (no network needed) and runs, in order: the request policy of `journey.py`, `probe.py` on the planted defects, `journey.py` on the fixture journey, `fixes.py` on the 5 fixture fixes, `repo_patch.py` against the fictional Astro source in `repo/` (which must stay byte for byte unchanged), and `check_evidence.py` on `audit.example.json`. Last, the server's access log must hold no POST. Exit 0 when all hold, 1 otherwise. Needs Playwright, Chromium, Pillow and `git`.

## Fallback when Playwright is unavailable

If Playwright cannot be installed in the user's environment, the agent falls back to a text-only audit on the markdown returned by `firecrawl scrape`. Visual criteria are then scored at low confidence. The Limitations section of the report documents the missing screenshots.

## Cross-platform notes

- Forward slashes in paths only. The scripts accept paths from any platform.
- On Linux without a sandboxed display, `capture-page.py` and the scripts built on `lpa_common.py` already set the launch flags `--no-sandbox` and `--disable-dev-shm-usage`.
- On macOS and Windows no extra flags are required.

## Troubleshooting

- **Cookie banner persists in the screenshot.** The script handles common patterns (Cookiebot, OneTrust, Klaviyo). Non-standard banners (custom-built modals) may persist. Capture the screenshot manually and pass it to the agent in chat.
- **The hero image is missing in the screenshot.** Some sites lazy-load the hero. The script waits 1.5 s after `networkidle`; if the image still has not loaded, the page likely lazy-loads its LCP element (a separate audit finding, criterion PM4 in `assets/mobile-ux-checklist.md`).
- **Auth-gated page.** The script does not support login. Ask the user for screenshots of the page behind login.
