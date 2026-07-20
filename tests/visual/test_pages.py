import pytest

from tests.visual.harness import assert_snapshot, goto_and_settle

# Real per-page URLs. Briefing is the default page at "/" (Streamlit's st.Page
# default=True) — "/briefing" 404s. The rest use their url_path from dashboard.py.
PAGES = [
    ("briefing", "/"),
    ("watchlist", "/watchlist"),
    ("signal-tracker", "/signal-tracker"),
    ("retrospective", "/retrospective"),
    ("pipeline-stats", "/pipeline-stats"),
    ("scenario-log", "/scenario-log"),
    ("report-comparison", "/report-comparison"),
    ("terminology", "/terminology"),
]

# ── Masks: hide ONLY genuinely wall-clock-derived regions ──
# Grepping `date.today()` / `datetime.now()` across the app finds exactly three
# clock sources that reach the DOM:
#   1. dashboard.py  date.today()  → the sidebar st.date_input default range
#      (today-30 … today). The *widget* is masked here; the *filtering* it drives
#      (Signal Tracker / Pipeline / Scenario Log / Report Comparison all clip to
#      that window) changes which reports render — that is a cross-DATE baseline
#      concern owned by the frozen-clock Docker baseline (Task 6), not a
#      run-to-run flake, so it is not (and cannot be) masked away.
#   2. live_prices  datetime.now() → the "LIVE · HH:MM" caption on Briefing /
#      Watchlist. Under the harness's dead-proxy the fetch fails, so it renders
#      the static "FETCH FAILED — showing snapshot", but it is masked for
#      correctness (it is clock-derived whenever the fetch succeeds).
#   3. capex_pulse  date.today() → the "CURATION OVERDUE — Nd old" staleness
#      banner on the Briefing (age in days).
# Everything else that looks date-stamped (masthead long-date, table dates,
# episode durations, days-until-earnings, scenario day headers) is a STATIC
# report-JSON value, not wall-clock — verified by tracing each to its source —
# so it stays UNMASKED to keep real regressions visible.

# The sidebar renders on every page, so its today-anchored date_input is global.
GLOBAL_MASKS = ['[data-testid="stDateInput"]']

PAGE_MASKS = {
    "briefing": [
        "text=/LIVE ·|FETCH FAILED/",  # live-price caption (lib/pills.py)
        "text=/CURATION OVERDUE/",     # capex staleness banner (capex_pulse.py)
    ],
    "watchlist": [
        "text=/LIVE ·|FETCH FAILED/",  # live-price caption (watchlist body)
    ],
    # signal-tracker / pipeline-stats / scenario-log / report-comparison /
    # terminology carry no body-level clock text — only the global date_input.
}


@pytest.mark.visual
@pytest.mark.parametrize("name,path", PAGES, ids=[p[0] for p in PAGES])
def test_page_snapshot(streamlit_server, vpage, name, path):
    goto_and_settle(vpage, f"{streamlit_server}{path}")
    selectors = GLOBAL_MASKS + PAGE_MASKS.get(name, [])
    mask = [vpage.locator(s) for s in selectors]
    assert_snapshot(vpage, name, mask=mask)
