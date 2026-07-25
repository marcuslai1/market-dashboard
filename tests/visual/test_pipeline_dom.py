"""Live-DOM assertions for the Pipeline health page (spec 2026-07-25).

A snapshot would freeze a broken render as the baseline, so the things that can
break silently are asserted against computed style instead:

  * the sparkline endpoint dot stays CIRCULAR and inside its cell at any cell
    width — it is an HTML element precisely because an SVG <circle> inside a
    preserveAspectRatio:none viewBox stretches into an oval and paints past the
    cell edge into the grid divider;
  * the five metric hues actually resolve, and resolve differently, so the strip
    reads as five identities rather than five near-identical tiles;
  * the threshold line is not the faintest text in its cell — it is the payload
    of the whole feature.
"""
import pytest

from tests.visual.harness import SETTLE_TIMEOUT_MS


def _settle(page, url: str) -> None:
    page.goto(url, wait_until="networkidle")
    page.wait_for_selector("text=The Market Report", timeout=SETTLE_TIMEOUT_MS)
    page.wait_for_selector('[data-testid="stStatusWidget"]', state="detached",
                           timeout=SETTLE_TIMEOUT_MS)
    page.wait_for_selector(".pm-strip", timeout=SETTLE_TIMEOUT_MS)


@pytest.mark.visual
@pytest.mark.parametrize("width", [1440, 1180])
def test_endpoint_dot_stays_round_and_inside_its_cell(streamlit_server, vpage, width):
    vpage.set_viewport_size({"width": width, "height": 900})
    _settle(vpage, f"{streamlit_server}/pipeline-stats")

    dots = vpage.evaluate("""() => [...document.querySelectorAll('.pm-cell')]
      .map(cell => {
        const dot = cell.querySelector('.pm-dot');
        if (!dot) return null;
        const d = dot.getBoundingClientRect(), c = cell.getBoundingClientRect();
        return {metric: cell.dataset.metric, w: d.width, h: d.height,
                overflowRight: d.right - c.right, overflowLeft: c.left - d.left};
      }).filter(Boolean)""")

    assert dots, "no endpoint dots rendered"
    for d in dots:
        assert abs(d["w"] - d["h"]) < 0.5, (
            f"{d['metric']} dot is {d['w']}x{d['h']} — it stretched into an oval"
        )
        assert d["overflowRight"] <= 0.5, (
            f"{d['metric']} dot crosses the cell's right edge by "
            f"{d['overflowRight']:.1f}px into the grid divider"
        )
        assert d["overflowLeft"] <= 0.5, f"{d['metric']} dot escapes left"


@pytest.mark.visual
def test_each_metric_cell_wears_its_own_hue(streamlit_server, vpage):
    """Hue is the cell's identity. If two resolve the same, the strip is back to
    five near-identical tiles and the palette bought nothing."""
    _settle(vpage, f"{streamlit_server}/pipeline-stats")

    rails = vpage.evaluate("""() => [...document.querySelectorAll('.pm-cell')]
      .map(c => [c.dataset.metric, getComputedStyle(c).borderTopColor])""")
    assert len(rails) == 5, f"expected 5 metric cells, saw {len(rails)}"
    colours = [c for _m, c in rails]
    assert len(set(colours)) == 5, f"metric hues collided: {rails}"
    for metric, colour in rails:
        assert colour not in ("rgba(0, 0, 0, 0)", "transparent"), \
            f"{metric} rail did not resolve its token"


@pytest.mark.visual
def test_threshold_line_is_not_the_faintest_text_in_the_cell(streamlit_server, vpage):
    """It states the budget every reading is judged against, so it must be
    legible — it was 8.5px/40% in the first pass, fainter than the metadata."""
    _settle(vpage, f"{streamlit_server}/pipeline-stats")

    got = vpage.evaluate("""() => {
      const t = document.querySelector('.pm-cell .pm-threshold');
      const b = document.querySelector('.pm-cell .pm-basis');
      const cs = getComputedStyle(t);
      return {size: parseFloat(cs.fontSize), opacity: parseFloat(cs.opacity),
              colour: cs.color, basisColour: getComputedStyle(b).color,
              text: t.textContent.trim()};
    }""")
    assert got["size"] >= 9.5, f"threshold set at {got['size']}px"
    assert got["opacity"] >= 0.7, f"threshold at {got['opacity']} opacity"
    assert got["colour"] != got["basisColour"], \
        "threshold is the same ramp as the metadata beside it"
    assert any(w in got["text"].lower() for w in ("ceiling", "floor")), got["text"]


@pytest.mark.visual
def test_prompt_bands_are_readable_without_matching_colours(streamlit_server, vpage):
    """The redundant encoding is the fix, not the hue tuning: printed shares and
    per-row bar lengths must both be present, so a reader never has to tell two
    blues apart."""
    _settle(vpage, f"{streamlit_server}/pipeline-stats")

    got = vpage.evaluate("""() => ({
      printed: document.querySelectorAll('.pm-seg-pct').length,
      rows: document.querySelectorAll('.pm-crow').length,
      bars: [...document.querySelectorAll('.pm-cbar > span')]
              .map(s => s.getBoundingClientRect().width),
    })""")
    assert got["rows"] == 5, f"expected 5 composition rows, saw {got['rows']}"
    assert got["printed"] >= 2, "no shares printed inside the stacked bar"
    # Descending, and genuinely different lengths — the comparison the rows exist
    # to make.
    assert got["bars"] == sorted(got["bars"], reverse=True), got["bars"]
    assert got["bars"][0] > got["bars"][-1] + 5
