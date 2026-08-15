"""Renders the README's card screenshots from the real card files.

The images in docs/images/ are produced from
tools/card-preview/screenshots.html, which imports the actual card
modules from custom_components/ and feeds them a mocked `hass`. So they
cannot drift away from the code the way hand-taken screenshots do: when
a card changes, re-running this regenerates them.

    python -m pip install playwright
    python -m playwright install chromium
    python tools/capture_screenshots.py

Not part of the test suite - Playwright is a heavyweight dependency and
only needed when the images actually need refreshing.
"""

from __future__ import annotations

import contextlib
import functools
import http.server
import socketserver
import sys
import threading
from pathlib import Path

REPO = Path(__file__).parent.parent
PAGE_PATH = "/tools/card-preview/screenshots.html"
OUT = REPO / "docs" / "images"

# Element id -> output filename. Ids are defined in screenshots.html.
SHOTS = {
    "shot-health": "card-health-score.png",
    "shot-health-modal": "card-health-score-pillar.png",
    "shot-day-night": "card-day-night-active.png",
    "shot-day-night-rest": "card-day-night-resting.png",
    "shot-day-night-weather": "card-day-night-weather.png",
    "shot-running": "card-running.png",
    "shot-chronicle": "card-chronicle.png",
    "shot-ranking": "card-ranking.png",
    "shot-weight": "card-weight-syrian.png",
    "shot-weight-robo": "card-weight-roborovski.png",
}


@contextlib.contextmanager
def _serve(root: Path):
    """Serve `root` over HTTP for the duration of the block.

    The page imports the cards as ES modules, and Chromium refuses those
    over file:// - cross-origin rules only allow http/https/data. So the
    repo is served on a throwaway localhost port instead.
    """
    handler = functools.partial(
        http.server.SimpleHTTPRequestHandler, directory=str(root)
    )
    # Port 0 lets the OS pick a free one, so a second run (or anything
    # else on 8000) can't collide.
    with socketserver.TCPServer(("127.0.0.1", 0), handler) as httpd:
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        try:
            yield f"http://127.0.0.1:{httpd.server_address[1]}"
        finally:
            httpd.shutdown()


def main() -> int:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print(
            "Playwright is not installed. Run:\n"
            "  python -m pip install playwright\n"
            "  python -m playwright install chromium",
            file=sys.stderr,
        )
        return 1

    OUT.mkdir(parents=True, exist_ok=True)

    with _serve(REPO) as origin, sync_playwright() as p:
        browser = p.chromium.launch()
        # deviceScaleFactor=2 so the images stay sharp on the HiDPI screens
        # most people read GitHub on.
        page = browser.new_page(viewport={"width": 900, "height": 1200},
                                device_scale_factor=2)
        failures: list[str] = []
        page.on("pageerror", lambda e: failures.append(str(e)))
        page.goto(origin + PAGE_PATH)
        # Set by the page once every card has rendered; without it the
        # capture can land on a half-built DOM.
        try:
            page.wait_for_selector("body[data-ready='1']", timeout=30_000)
        except Exception:
            for line in failures:
                print(f"  page error: {line}", file=sys.stderr)
            raise
        page.wait_for_timeout(600)  # let the CSS animations settle

        for element_id, filename in SHOTS.items():
            element = page.query_selector(f"#{element_id}")
            if element is None:
                print(f"  MISSING #{element_id}", file=sys.stderr)
                return 1
            element.screenshot(path=str(OUT / filename))
            print(f"  {filename}")

        browser.close()

    print(f"\n{len(SHOTS)} screenshots written to {OUT.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
