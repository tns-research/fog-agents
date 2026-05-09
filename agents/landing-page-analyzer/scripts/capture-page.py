#!/usr/bin/env python3
"""
Landing-page screenshot capture (desktop and mobile).

Bundled with the fog-agents landing-page-analyzer agent. Standalone:
only needs Python 3.8+ and Playwright (Chromium).

Behavior:
- Single landing page (no e-commerce flow). Takes one URL.
- Captures two screenshots: desktop.png (1280 x 900) and mobile.png (390 x 844).
- Each viewport uses a 2x screen height to capture above-the-fold plus first scroll.
- Dismisses common cookie banners and newsletter modals before screenshot.
- If the URL returns a 404, waits up to 5 seconds for a client-side redirect
  (meta refresh or JavaScript) before capturing. Captures anyway after timeout.
- Forward slashes only (cross-platform).

Usage:
  python3 capture-page.py <output_dir> <url>

Example:
  python3 capture-page.py ./screenshots-20260428 "https://acme.com/pricing"

Output: 2 PNG files in output_dir:
  desktop.png
  mobile.png

Setup (once):
  pip install -r requirements.txt
  playwright install chromium
"""

import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

# Viewport sizes (width x height). Height is multiplied by SCREEN_HEIGHT_MULTIPLIER
# to capture above-the-fold plus first scroll in a single screenshot.
VIEWPORTS = {
    "desktop": {"width": 1280, "height": 900},
    "mobile": {"width": 390, "height": 844},
}
SCREEN_HEIGHT_MULTIPLIER = 2

# Wait for client-side redirect when a 404 is detected (e.g. meta refresh or JS redirect).
REDIRECT_WAIT_MS = 5000
REDIRECT_POLL_MS = 500

# Wait between navigation completion and screenshot (lets late-loading hero images settle).
SETTLE_MS = 1500
POST_DISMISS_MS = 800

# User agents per viewport. Mobile UA triggers responsive layouts on most sites.
USER_AGENTS = {
    "desktop": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "mobile": (
        "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1"
    ),
}


def is_404_page(page):
    """Return True when the page content indicates a 404 / not found."""
    try:
        content = page.content()
        if "404" in content:
            return True
        if "page non trouvée" in content.lower():
            return True
        if "not found" in content.lower():
            return True
        return False
    except Exception:
        return False


def wait_for_redirect_if_404(page, timeout_ms=None, poll_interval_ms=None):
    """
    If the page looks like a 404, wait for a client-side redirect (meta refresh or JS).
    Polls until the page is no longer a 404, the URL changes, or timeout is reached.

    Returns True when no longer on a 404 page (or never was). Returns False on timeout.
    """
    timeout_ms = timeout_ms if timeout_ms is not None else REDIRECT_WAIT_MS
    poll_interval_ms = poll_interval_ms if poll_interval_ms is not None else REDIRECT_POLL_MS
    if not is_404_page(page):
        return True
    initial_url = page.url
    elapsed = 0
    while elapsed < timeout_ms:
        page.wait_for_timeout(poll_interval_ms)
        elapsed += poll_interval_ms
        if not is_404_page(page):
            return True
        if page.url != initial_url:
            return True
    return False


def dismiss_popups(page):
    """
    Dismiss common cookie banners and newsletter modals.

    Two passes:
    1. Generic close buttons (X icon, close-class).
    2. Cookie-consent specific accept / refuse buttons (English plus French).
    """
    close_selectors = [
        "button[aria-label='Close']",
        "button[aria-label='close']",
        "button.klaviyo-close-form",
        "svg[data-testid='CloseIcon']",
        "[class*='close-button']",
        "button:has-text('No thanks')",
        "button:has-text('Non, merci')",
        "button:has-text('NON, MERCI')",
    ]
    for selector in close_selectors:
        try:
            el = page.query_selector(selector)
            if el and el.is_visible():
                el.click()
                page.wait_for_timeout(400)
                break
        except Exception:
            pass

    cookie_selectors = [
        "button:has-text('Accept all')",
        "button:has-text('Accept')",
        "button:has-text('I accept')",
        "button:has-text('Got it')",
        "button:has-text('OK')",
        "button:has-text('Accepter')",
        "button:has-text('Tout accepter')",
        "button:has-text('Refuser')",
        "#CybotCookiebotDialogBodyButtonAccept",
        "#onetrust-accept-btn-handler",
        ".cookie-accept",
        ".cc-accept",
        "[id*='cookie'] button",
    ]
    for selector in cookie_selectors:
        try:
            el = page.query_selector(selector)
            if el and el.is_visible():
                el.click()
                page.wait_for_timeout(400)
                break
        except Exception:
            pass


def navigate(page, url):
    """Navigate to URL with a generous timeout and best-effort wait for load and networkidle."""
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=45000)
        try:
            page.wait_for_load_state("load", timeout=8000)
        except Exception:
            pass
        try:
            page.wait_for_load_state("networkidle", timeout=5000)
        except Exception:
            pass
        return True
    except Exception as e:
        print("     Navigation failed: {} ({})".format(url, e))
        return False


def capture(page, url, out_path, viewport):
    """
    Set the viewport, navigate, dismiss popups, wait, screenshot.

    Viewport height is doubled by SCREEN_HEIGHT_MULTIPLIER so the screenshot
    covers above-the-fold plus the first scroll without requiring a full-page capture.
    """
    target_viewport = {
        "width": viewport["width"],
        "height": viewport["height"] * SCREEN_HEIGHT_MULTIPLIER,
    }
    print(
        "  Capture {} ({}x{}) - {}".format(
            out_path.name, target_viewport["width"], target_viewport["height"], url
        )
    )
    page.set_viewport_size(target_viewport)
    if not navigate(page, url):
        raise RuntimeError("Navigation failed: {}".format(url))
    page.wait_for_timeout(SETTLE_MS)
    dismiss_popups(page)
    page.wait_for_timeout(POST_DISMISS_MS)
    if is_404_page(page):
        redirected = wait_for_redirect_if_404(page)
        if redirected:
            dismiss_popups(page)
            page.wait_for_timeout(POST_DISMISS_MS)
        else:
            print("     Warning: page still 404 after waiting for redirect; capturing anyway")
    page.screenshot(path=str(out_path), full_page=False)
    print("     Saved: {}".format(out_path))


def main():
    if len(sys.argv) < 3:
        print("Usage: python3 capture-page.py <output_dir> <url>")
        sys.exit(1)

    output_dir = Path(sys.argv[1])
    url = sys.argv[2].strip()
    if not url:
        print("Error: URL is empty")
        sys.exit(1)

    output_dir.mkdir(parents=True, exist_ok=True)

    print("\n=== Landing-page screenshots ===")
    print("URL:    {}".format(url))
    print("Output: {}\n".format(output_dir))

    with sync_playwright() as p:
        browser = p.chromium.launch(args=["--no-sandbox", "--disable-dev-shm-usage"])
        for device, viewport in VIEWPORTS.items():
            context = browser.new_context(
                viewport=viewport,
                user_agent=USER_AGENTS[device],
            )
            page = context.new_page()
            out_path = output_dir / "{}.png".format(device)
            try:
                capture(page, url, out_path, viewport)
            except Exception as e:
                print("     Failed: {}".format(e))
            finally:
                context.close()
        browser.close()

    print("\n=== Done ===")
    files = list(output_dir.glob("*.png"))
    print("{} screenshot(s) in {}:".format(len(files), output_dir))
    for f in sorted(files):
        size_kb = f.stat().st_size // 1024
        print("  {} ({} KB)".format(f.name, size_kb))


if __name__ == "__main__":
    main()
