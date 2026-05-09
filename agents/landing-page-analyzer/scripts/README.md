# Landing-page screenshot capture script

`capture-page.py` is a single-page screenshot tool used by the `landing-page-analyzer` agent. It produces two PNGs (desktop + mobile) for the audit, dismisses common cookie banners, and waits for client-side redirects when a page initially returns 404.

The agent calls this script at Step 1 of its workflow. The user can also run it manually.

## Requirements

- Python 3.8+
- Playwright (Chromium)

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
  "https://acme.com/pricing"
```

- **Argument 1:** output directory. Will be created if it does not exist.
- **Argument 2:** the landing-page URL.

## What the script does

- Opens the URL in Chromium under a desktop viewport (1280 x 900) then a mobile viewport (390 x 844). Both viewports use a 2x screen height so the screenshot covers above-the-fold plus the first scroll.
- Dismisses common cookie banners (Cookiebot, OneTrust, generic accept buttons) and newsletter modals (Klaviyo, Mailchimp common patterns).
- If the URL initially returns 404, polls for up to 5 seconds for a client-side redirect (meta refresh or JavaScript) before capturing. Captures anyway after timeout, with a warning printed.
- Uses real desktop and mobile user-agent strings so sites serve the correct responsive layout.

## Output

Two PNG files in the output directory:

- `desktop.png` (1280 x 1800)
- `mobile.png` (390 x 1688)

After the script finishes, the agent reads the PNGs as the visual stimulus for:

- the 10-second comprehension test (`skills/running-comprehension-test/SKILL.md`),
- the visual criteria (V1 to V10 in `assets/visual-criteria-checklist.md`),
- the mobile UX checks (`assets/mobile-ux-checklist.md`).

## Fallback when Playwright is unavailable

If Playwright cannot be installed in the user's environment, the agent falls back to a text-only audit on the markdown returned by `firecrawl scrape`. Visual criteria are then scored at low confidence. The Limitations section of the report documents the missing screenshots.

## Cross-platform notes

- Forward slashes in paths only. The script accepts paths from any platform.
- On Linux without a sandboxed display, the launch flags `--no-sandbox` and `--disable-dev-shm-usage` are already set.
- On macOS and Windows no extra flags are required.

## Troubleshooting

- **Cookie banner persists in the screenshot.** The script handles common patterns (Cookiebot, OneTrust, Klaviyo). Non-standard banners (custom-built modals) may persist. Capture the screenshot manually and pass it to the agent in chat.
- **The hero image is missing in the screenshot.** Some sites lazy-load the hero. The script waits 1.5 s after `networkidle`; if the image still has not loaded, the page likely lazy-loads its LCP element (a separate audit finding, criterion PM4 in `assets/mobile-ux-checklist.md`).
- **Auth-gated page.** The script does not support login. Ask the user for screenshots of the page behind login.
