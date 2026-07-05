"""Capture + compare helpers for visual-regression tests. The comparator is
pure (no browser) so it is unit-testable; the capture wrappers own the
Streamlit-specific settling."""
from __future__ import annotations

import io
import os
from pathlib import Path

from PIL import Image
from pixelmatch.contrib.PIL import pixelmatch

BASELINE_DIR = Path(__file__).parent / "baselines"
DIFF_DIR = Path(__file__).parent / "_diffs"

# First-render budget. This exists to catch hangs, not to benchmark: CI paints
# the masthead in ~2-3s, but a Docker-Desktop-on-Windows container has taken
# 36s+ to first paint on heavy pages (observed 2026-07-05, all pages timing out
# at the old 30s) — the suite must stay green on slow hosts too.
SETTLE_TIMEOUT_MS = 120_000


def compare_png(actual: bytes, baseline: bytes, *, max_diff_ratio: float = 0.002
                ) -> tuple[bool, bytes]:
    """Anti-aliasing-aware compare. Returns (ok, diff_png_bytes).

    A width mismatch always fails: the viewport width is pinned, so it can only
    mean a real layout change. A HEIGHT gap spends the normal diff budget
    instead (every missing/extra row counts as a full row of differing pixels):
    the grow-until-stable capture wobbles the page tail by a row or two between
    runs — the b08f500 ledger baseline was 3782px vs a pixel-identical 3780px
    CI render (run 28720778639), and the old hard size gate kept CI red on that
    jitter through four regens. A genuinely added band exceeds the budget and
    still fails.
    """
    a = Image.open(io.BytesIO(actual)).convert("RGBA")
    b = Image.open(io.BytesIO(baseline)).convert("RGBA")
    if a.size[0] != b.size[0]:  # width mismatch is always a fail; diff = the actual
        return False, actual
    overlap_h = min(a.size[1], b.size[1])
    gap_px = abs(a.size[1] - b.size[1]) * a.size[0]
    a_ov = a.crop((0, 0, a.size[0], overlap_h))
    b_ov = b.crop((0, 0, b.size[0], overlap_h))
    diff = Image.new("RGBA", (a.size[0], overlap_h))
    # includeAA=False -> anti-aliased pixels are detected and IGNORED (not counted
    # as diffs); critical for robustness against font/subpixel noise.
    n = pixelmatch(a_ov, b_ov, diff, includeAA=False, threshold=0.1) + gap_px
    ok = n <= max_diff_ratio * (a.size[0] * max(a.size[1], b.size[1]))
    buf = io.BytesIO()
    diff.save(buf, format="PNG")
    return ok, buf.getvalue()


def _content_height(page) -> int:
    """Full scroll height of the Streamlit app (body/doc/stMain, whichever is
    tallest). Streamlit scrolls its body INSIDE <section data-testid="stMain">,
    so the document stays viewport-height and stMain carries the real height."""
    return int(page.evaluate(
        "() => {const m = document.querySelector('[data-testid=\"stMain\"]');"
        " return Math.max(document.body.scrollHeight,"
        " document.documentElement.scrollHeight, m ? m.scrollHeight : 0);}"
    ))


def grow_viewport_to_content(page) -> None:
    """Grow the viewport height until it holds the app's full content height, so
    Playwright's full_page screenshot captures the whole app.

    Streamlit scrolls its body INSIDE <section data-testid="stMain">, so the
    document itself stays viewport-height and a full_page screenshot would
    otherwise capture only the first fold. Growing the viewport to the full
    content height makes full_page capture the entire page (below-the-fold Plotly
    charts included). Width is preserved so the responsive layout is unchanged.

    Grow-until-stable: Streamlit lazy-mounts content near the viewport, so a
    large page (e.g. Signal Tracker) can render MORE once the viewport enlarges
    and exceed the height measured at 900px — silently truncating its tail,
    identically every run (a coverage gap with no flake to catch it). So after
    each resize we re-measure and grow again until the content fits, capped at
    4 iterations so a page that never converges can't loop forever.

    Monotonic + idempotent: the loop only ever GROWS the viewport (it breaks the
    moment content already fits). That is what lets a caller run it a SECOND time
    after an interaction (expanding a drill-down row adds height): the extra
    content simply re-triggers the grow, while an already-tall default page is
    left untouched — so ``goto_and_settle``'s behavior is unchanged by the split.
    """
    width = page.viewport_size["width"]
    for _ in range(4):
        content_h = _content_height(page)
        # +48px slack absorbs scrollbar width + subpixel rounding so the final
        # row is never clipped; it also damps <48px reflow jitter into one grow.
        if content_h <= page.viewport_size["height"]:
            break
        page.set_viewport_size({"width": width, "height": content_h + 48})
        # Let the taller layout settle — Plotly canvases redraw on the resize and
        # newly-revealed content mounts before the next measurement.
        page.wait_for_timeout(800)
    # A page that never converges within the cap would otherwise capture a
    # truncated tail deterministically (no flake to reveal the loss). Re-measure
    # after the loop and fail loud instead of silently clipping.
    content_h = _content_height(page)
    vh = page.viewport_size["height"]
    if content_h > vh:
        raise RuntimeError(
            f"page did not fit after 4 grows: content {content_h}px > "
            f"viewport {vh}px — increase the cap or investigate lazy-mounting"
        )


def goto_and_settle(page, url: str) -> None:
    """Navigate, wait until Streamlit has finished its script run, then grow the
    viewport so a full-page screenshot captures the whole app."""
    page.goto(url, wait_until="networkidle")
    page.wait_for_selector("text=The Market Report", timeout=SETTLE_TIMEOUT_MS)
    # Streamlit shows a "Running..." status while a script runs; wait it out.
    page.wait_for_selector('[data-testid="stStatusWidget"]', state="detached",
                           timeout=SETTLE_TIMEOUT_MS)
    # Re-assert animation kill (survives reruns) and let layout settle.
    page.add_style_tag(content="*{animation:none!important;transition:none!important}")
    page.wait_for_timeout(600)
    grow_viewport_to_content(page)


def assert_snapshot(page, name: str, *, mask: list | None = None) -> None:
    """Compare a full-page screenshot against baselines/<name>.png, or write it
    when VISUAL_UPDATE=1."""
    BASELINE_DIR.mkdir(exist_ok=True)
    actual = page.screenshot(full_page=True, animations="disabled",
                             mask=mask or [], scale="css", type="png")
    baseline_path = BASELINE_DIR / f"{name}.png"
    if os.environ.get("VISUAL_UPDATE") == "1":
        # Rewrite only on a REAL change. A within-tolerance rewrite commits
        # capture jitter as a binary diff — which then diffs against CI's
        # equally-jittered render, keeping CI red for no visual reason.
        if (baseline_path.exists()
                and compare_png(actual, baseline_path.read_bytes())[0]):
            return
        baseline_path.write_bytes(actual)
        return
    if not baseline_path.exists():
        # Compare mode: a missing baseline is a hard error, NOT a silent
        # write-and-pass. Auto-writing here would let an uncommitted snapshot
        # pass forever in an ephemeral CI container, testing nothing.
        raise AssertionError(
            f"baseline '{name}.png' missing — generate it with VISUAL_UPDATE=1 "
            f"(make visual-update) and commit it"
        )
    ok, diff = compare_png(actual, baseline_path.read_bytes())
    if not ok:
        DIFF_DIR.mkdir(exist_ok=True)
        (DIFF_DIR / f"{name}.actual.png").write_bytes(actual)
        (DIFF_DIR / f"{name}.diff.png").write_bytes(diff)
        raise AssertionError(
            f"Visual diff for '{name}'. See tests/visual/_diffs/{name}.diff.png. "
            f"If intentional, regenerate with `make visual-update`."
        )
