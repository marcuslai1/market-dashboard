"""Visual-regression snapshots of KEY INTERACTIVE states — the ones that only
exist after a click, where real display bugs have hidden: the watchlist row
drill-down, twice: as revealed, and again with its Earnings drawer opened. (The
signal-tracker ledger and Retrospective month states went 2026-10-01 with those
pages — MarketReport spec 2026-10-01-info-only-watchlist O7.)

The drill-down is a native HTML ``<details>`` block emitted inside a single
``st.markdown(unsafe_allow_html=True)`` (``components/watchlist``). Clicking a
``<summary>`` toggles the ``open`` attribute entirely client-side — there is NO
Streamlit rerun (verified: no ``stStatusWidget`` appears after the click), so a
short fixed settle is correct here (a rerun-style ``stStatusWidget``-detached
wait would race on an event that never fires).

The crux of this file: ``goto_and_settle`` grows the viewport to the DEFAULT
content height BEFORE the click, so the freshly-revealed drill-down would be
truncated by that already-fixed viewport. We therefore call
``grow_viewport_to_content`` AGAIN after the expand so the full-page screenshot
captures the newly-added height — which is also what makes each snapshot differ
from its Task-4 default-page counterpart. The same applies one level deeper: the
drill-down's own ``dd-drawer`` details start closed, so anything inside them
needs its own state to be captured at all.
"""
import pytest

from tests.visual.harness import (
    assert_snapshot,
    goto_and_settle,
    grow_viewport_to_content,
)

# Same masks as the page snapshots (tests/visual/test_pages.py), applied to both
# states for consistency: the sidebar date_input (gone since 2026-10-01; a no-op
# guard) and the live-price caption.
MASKS = [
    '[data-testid="stDateInput"]',   # sidebar date range (global, every page)
    "text=/LIVE ·|FETCH FAILED/",    # live-price caption (watchlist body)
]


def _masks(page):
    return [page.locator(s) for s in MASKS]


@pytest.mark.visual
def test_watchlist_nvda_drilldown(streamlit_server, vpage):
    """Expand the NVDA watchlist row and snapshot its revealed drill-down."""
    goto_and_settle(vpage, f"{streamlit_server}/watchlist")

    # The NVDA row is the one <details class="tk-details"> whose SUMMARY's ticker
    # cell reads exactly "NVDA". Both halves of that are load-bearing since the
    # 2026-07-25 redesign: the ticker now also appears in the drill-down card's
    # own header, and the drill-down carries a nested <details class="dd-drawer">
    # (one since 2026-10-01, three before) — so a bare get_by_text("NVDA") can
    # match twice per row and a bare .locator("summary") trips strict mode.
    nvda = vpage.locator(
        'details.tk-details:has(> summary .tk-tick-tk:text-is("NVDA"))'
    )
    nvda.locator("> summary").click()

    # Verify the expansion actually happened before snapshotting: the native
    # <details> is now open and its drill-down body is visible (collapsed rows
    # hide every child except the summary, so is_visible() is a true toggle).
    assert nvda.evaluate("el => el.open") is True, "NVDA row did not open"
    assert nvda.locator(".tk-drilldown").is_visible(), "drill-down body not revealed"

    # Native toggle → instant, no rerun. Let layout reflow, then RE-GROW so the
    # ~1000px of newly-revealed drill-down isn't clipped by the pre-click viewport.
    vpage.wait_for_timeout(400)
    grow_viewport_to_content(vpage)

    assert_snapshot(vpage, "watchlist-nvda-drilldown", mask=_masks(vpage))


@pytest.mark.visual
def test_watchlist_nvda_earnings_drawer(streamlit_server, vpage):
    """Open NVDA's drill-down AND its Earnings drawer — the only pixel coverage
    of the quarter-on-quarter earnings-history table.

    That table and its reported-EPS sparkline (`components/watchlist/
    earnings_history.py`, pipeline side PIPELINE_FEATURES §52) sit TWO
    ``<details>`` deep: the row drill-down, and then a ``dd-drawer`` that stays
    CLOSED when the row opens. ``test_watchlist_nvda_drilldown`` above stops at
    the first level, so without this state the table renders in production and
    appears in no baseline at all — a whole component with zero pixel coverage.

    NVDA is not an arbitrary pick: under the frozen corpus it is the ticker that
    exercises every branch of the table at once — eight reported quarters (all
    beats, so the ▲ prefix and `.eps-beat`), a coming 2026-Q3 row (blue tint,
    "upcoming" chip, est-marked forward revenue), one row carrying Rev YoY, and
    four older rows whose absent margins must render as em-dashes.
    """
    goto_and_settle(vpage, f"{streamlit_server}/watchlist")

    nvda = vpage.locator(
        'details.tk-details:has(> summary .tk-tick-tk:text-is("NVDA"))'
    )
    nvda.locator("> summary").click()
    assert nvda.evaluate("el => el.open") is True, "NVDA row did not open"

    # The one drawer summary is "Earnings" (the "Risk & reward detail" and
    # "Pipeline detail" drawers went 2026-10-01). :text-is() is EXACT and the
    # `> summary` child combinator is load-bearing: the drawer body itself carries
    # "Past earnings reactions" and "Earnings history" section heads, so a substring match or an unanchored
    # descendant search would resolve to more than one node and trip strict mode.
    drawer = nvda.locator('details.dd-drawer:has(> summary:text-is("Earnings"))')
    drawer.locator("> summary").click()
    assert drawer.evaluate("el => el.open") is True, "Earnings drawer did not open"

    # Assert the §52 content specifically, not just that something opened: an
    # empty-but-open drawer would snapshot perfectly cleanly and quietly lock a
    # regression (the table is silent by design when the ticker has no rows, so
    # a data-loading break degrades to a blank drawer rather than an error).
    assert drawer.locator("table.ep-table").is_visible(), "earnings-history table missing"
    assert drawer.locator('table.ep-table td:has-text("upcoming")').count() == 1, \
        "coming-quarter row missing"

    # Both toggles are native <details> — no Streamlit rerun (see module
    # docstring) — so a fixed settle is correct. Then RE-GROW a second time: the
    # two reveals together add ~1500px that the pre-click viewport would clip.
    vpage.wait_for_timeout(400)
    grow_viewport_to_content(vpage)

    assert_snapshot(vpage, "watchlist-nvda-earnings-drawer", mask=_masks(vpage))
