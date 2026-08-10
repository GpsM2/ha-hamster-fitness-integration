"""Loads every frontend .js file as an ES module in a real browser.

    python -m pip install playwright
    python -m playwright install chromium
    python tools/check_frontend_syntax.py

Not part of the pytest suite for the same reason capture_screenshots.py
isn't (see its docstring): Playwright is a heavyweight dependency. Run
instead as its own CI job (see .github/workflows/ci.yml) so the fast
pytest/ruff/mypy job stays fast, while a syntax error still fails the
build rather than reaching a user's dashboard.

tests/test_frontend_resources.py::test_style_blocks_contain_no_stray_backtick
already guards the most common way this breaks - a stray backtick inside
a card's `styles = \\`...\\`` template literal, which silently truncates
the string and turns the rest of the file into invalid JavaScript. That
test only checks that *some* CSS exists before the first backtick found,
though, so a stray one deep inside an already-valid stylesheet (inside a
comment, say) still slips past it - this happened twice in one afternoon
before this script existed. Actually loading the file in a browser is the
only check that can't be fooled that way, and it catches any other JS
syntax mistake the same way.
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
FRONTEND_DIR = REPO / "custom_components" / "hamster_fitness" / "frontend"


@contextlib.contextmanager
def _serve(root: Path):
    """Serve `root` over HTTP for the duration of the block.

    A dynamic import() needs a real http(s) origin - file:// and
    about:blank both refuse module loading under Chromium's CORS rules.
    """
    handler = functools.partial(
        http.server.SimpleHTTPRequestHandler, directory=str(root)
    )
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

    files = sorted(FRONTEND_DIR.glob("*.js"))
    if not files:
        print(f"No .js files found under {FRONTEND_DIR}", file=sys.stderr)
        return 1

    failures: dict[str, str] = {}

    with _serve(REPO) as origin, sync_playwright() as p:
        browser = p.chromium.launch()
        for path in files:
            # A fresh, unnavigated page shares no custom-element registry
            # with any other card - each file gets to call
            # customElements.define() for its own tag without colliding
            # with a previous iteration's registration of the same name.
            page = browser.new_page()
            page.goto(origin + "/")
            url = f"{origin}/custom_components/hamster_fitness/frontend/{path.name}"
            result = page.evaluate(
                """async (url) => {
                    try {
                        await import(url);
                        return { ok: true };
                    } catch (err) {
                        return { ok: false, message: String(err && err.message || err) };
                    }
                }""",
                url,
            )
            page.close()
            print(f"  {'OK  ' if result['ok'] else 'FAIL'}  {path.name}")
            if not result["ok"]:
                failures[path.name] = result["message"]
        browser.close()

    if failures:
        print("\nFrontend syntax check failed:", file=sys.stderr)
        for name, message in failures.items():
            print(f"  {name}: {message}", file=sys.stderr)
        return 1

    print(f"\nAll {len(files)} frontend files load cleanly.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
