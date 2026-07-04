"""Visual-regression snapshots of KEY INTERACTIVE states — the ones that only
exist after a click, where real display bugs have hidden: the watchlist row
drill-down and the signal-tracker by-name episode ledger.

Both drill-downs are native HTML ``<details>`` blocks emitted inside a single
``st.markdown(unsafe_allow_html=True)`` (watchlist: ``components/watchlist``;
tracker: ``components/signal_tracker._name_ledger_html``). Clicking a
``<summary>`` toggles the ``open`` attribute entirely client-side — there is NO
Streamlit rerun (verified: no ``stStatusWidget`` appears after the click), so a
short fixed settle is correct here (a rerun-style ``stStatusWidget``-detached
wait would race on an event that never fires).

The crux of this file: ``goto_and_settle`` grows the viewport to the DEFAULT
content height BEFORE the click, so the freshly-revealed drill-down would be
truncated by that already-fixed viewport. We therefore call
``grow_viewport_to_content`` AGAIN after the expand so the full-page screenshot
captures the newly-added height — which is also what makes each snapshot differ
from its Task-4 default-page counterpart.
"""
import pytest

from tests.visual.harness import (
    assert_snapshot,
    goto_and_settle,
    grow_viewport_to_content,
)

# Same masks as the Task-4 page snapshots (tests/visual/test_pages.py), applied
# to both states for consistency: the sidebar's today-anchored date_input
# (rendered on every page) and the live-price caption. Frozen TEST_DATE already
# makes both deterministic; masking only keeps these interactive baselines
# pixel-consistent with the page baselines. The live-price locator simply
# matches nothing on Signal Tracker (harmless).
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

    # The NVDA row is the one <details class="tk-details"> whose summary carries
    # the ticker cell with exact text "NVDA" (verified unique: 1 of 29 rows).
    nvda = vpage.locator(
        "details.tk-details", has=vpage.get_by_text("NVDA", exact=True)
    )
    nvda.locator("summary").click()

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
def test_signal_tracker_ledger(streamlit_server, vpage):
    """Expand the first by-name ledger row and snapshot its episode drill-down.

    The default page renders the ledger with every ``<details class=led-details>``
    COLLAPSED, so a plain scroll-into-view would be pixel-identical to the Task-4
    ``signal-tracker`` snapshot. Opening a row reveals its per-name episode table
    — content the default page never shows — so this baseline genuinely differs.
    """
    goto_and_settle(vpage, f"{streamlit_server}/signal-tracker")

    # The by-name ledger now lives inside a COLLAPSED st.expander (added in
    # 7eab190 "simplify to one plain scorecard" — the page leads with the
    # scorecard and tucks the per-name history into a drawer). Its
    # <details class=led-details> rows are in the DOM but hidden until the
    # expander is opened, so open it first. Streamlit expanders are native
    # <details>/<summary> that toggle client-side (no rerun), same as the
    # ledger rows. has_text disambiguates it from the "Signal changes" expander;
    # .first picks the expander's OWN summary, which precedes the 29 nested
    # ledger-row <summary>s in DOM order (without it, strict mode sees 30).
    vpage.locator(
        '[data-testid="stExpander"]', has_text="By name"
    ).locator("summary").first.click()

    # Open the top ledger row (deterministic: the ledger is sorted scored-names-
    # first by win-rate, so row 0 is stable under the frozen corpus). Any row
    # exposes its episode table; the first is the simplest deterministic target.
    row = vpage.locator("details.led-details").first
    row.locator("summary").click()

    assert row.evaluate("el => el.open") is True, "ledger row did not open"
    assert row.locator(".tk-drilldown").is_visible(), "episode drill-down not revealed"
    assert row.locator("table.ep-table").count() > 0, "episode table missing"

    vpage.wait_for_timeout(400)
    grow_viewport_to_content(vpage)

    assert_snapshot(vpage, "signal-tracker-ledger", mask=_masks(vpage))
