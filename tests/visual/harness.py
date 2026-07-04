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


def compare_png(actual: bytes, baseline: bytes, *, max_diff_ratio: float = 0.002
                ) -> tuple[bool, bytes]:
    """Anti-aliasing-aware compare. Returns (ok, diff_png_bytes)."""
    a = Image.open(io.BytesIO(actual)).convert("RGBA")
    b = Image.open(io.BytesIO(baseline)).convert("RGBA")
    if a.size != b.size:  # size mismatch is always a fail; diff = the actual
        return False, actual
    diff = Image.new("RGBA", a.size)
    # includeAA=False -> anti-aliased pixels are detected and IGNORED (not counted
    # as diffs); critical for robustness against font/subpixel noise.
    n = pixelmatch(a, b, diff, includeAA=False, threshold=0.1)
    ok = n <= max_diff_ratio * (a.size[0] * a.size[1])
    buf = io.BytesIO()
    diff.save(buf, format="PNG")
    return ok, buf.getvalue()


def goto_and_settle(page, url: str) -> None:
    """Navigate and wait until Streamlit has finished its script run."""
    page.goto(url, wait_until="networkidle")
    page.wait_for_selector("text=The Market Report", timeout=30_000)
    # Streamlit shows a "Running..." status while a script runs; wait it out.
    page.wait_for_selector('[data-testid="stStatusWidget"]', state="detached",
                           timeout=30_000)
    # Re-assert animation kill (survives reruns) and let layout settle.
    page.add_style_tag(content="*{animation:none!important;transition:none!important}")
    page.wait_for_timeout(600)


def assert_snapshot(page, name: str, *, mask: list | None = None) -> None:
    """Compare a full-page screenshot against baselines/<name>.png, or write it
    when VISUAL_UPDATE=1."""
    BASELINE_DIR.mkdir(exist_ok=True)
    actual = page.screenshot(full_page=True, animations="disabled",
                             mask=mask or [], scale="css", type="png")
    baseline_path = BASELINE_DIR / f"{name}.png"
    if os.environ.get("VISUAL_UPDATE") == "1" or not baseline_path.exists():
        baseline_path.write_bytes(actual)
        return
    ok, diff = compare_png(actual, baseline_path.read_bytes())
    if not ok:
        DIFF_DIR.mkdir(exist_ok=True)
        (DIFF_DIR / f"{name}.actual.png").write_bytes(actual)
        (DIFF_DIR / f"{name}.diff.png").write_bytes(diff)
        raise AssertionError(
            f"Visual diff for '{name}'. See tests/visual/_diffs/{name}.diff.png. "
            f"If intentional, regenerate with `make visual-update`."
        )
