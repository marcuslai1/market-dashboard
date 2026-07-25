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

The Retrospective month state is the exception to the "no rerun" note above: its
month picker is an ``st.radio``, so clicking a segment DOES trigger a Streamlit
rerun and that test waits for the status widget to detach instead of using a
fixed settle.
"""
import pytest

from tests.visual.harness import (
    SETTLE_TIMEOUT_MS,
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

    # The NVDA row is the one <details class="tk-details"> whose SUMMARY's ticker
    # cell reads exactly "NVDA". Both halves of that are load-bearing since the
    # 2026-07-25 redesign: the ticker now also appears in the drill-down card's
    # own header, and the drill-down carries three nested <details class=
    # "dd-drawer"> — so a bare get_by_text("NVDA") can match twice per row and a
    # bare .locator("summary") resolves to four elements and trips strict mode.
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


@pytest.mark.visual
def test_retrospective_resolved_month(streamlit_server, vpage):
    """Switch the Retrospective to the newest CLOSED month and snapshot it.

    This state is not a nice-to-have: the default page lands on the newest month,
    whose calls are all inside their 20-session windows, so it can only ever show
    the pending case — a dash where the hit rate goes, one grey bar, and ⏳ rails
    down the whole list. The page's actual design (a brass percentage, a green/red
    composition bar, and ✓/✗ rails carrying an outcome beside a signal pill
    carrying a rating) exists ONLY on a resolved month, and would otherwise have
    zero pixel coverage.

    Clicking the segment is a real widget interaction, so unlike the two
    <details> states above this triggers a Streamlit rerun — hence the
    status-widget wait rather than a fixed settle.
    """
    goto_and_settle(vpage, f"{streamlit_server}/retrospective")

    # The SECOND segment, not a hardcoded month: segments run newest-first, so
    # index 1 is always the most recently closed month — the one guaranteed to
    # carry resolved calls as the archive grows.
    segments = vpage.locator('.st-key-retro_month [role="radiogroup"] > label')
    assert segments.count() >= 2, "need at least two months in the archive"
    segments.nth(1).click()

    vpage.wait_for_selector('[data-testid="stStatusWidget"]', state="detached",
                            timeout=SETTLE_TIMEOUT_MS)
    vpage.add_style_tag(content="*{animation:none!important;transition:none!important}")
    vpage.wait_for_timeout(600)

    # Verify we actually landed on a resolved month — otherwise this baseline
    # would silently duplicate the default page's pending-only coverage.
    assert "%" in vpage.locator(".rb-hit").inner_text(), "no hit rate on this month"
    assert vpage.locator('.retro-item[data-bucket="worked"]').count() > 0
    assert vpage.locator('.retro-item[data-bucket="failed"]').count() > 0

    grow_viewport_to_content(vpage)
    assert_snapshot(vpage, "retrospective-resolved-month", mask=_masks(vpage))
