import pytest

from tests.visual.harness import assert_snapshot, goto_and_settle


@pytest.mark.visual
def test_briefing_snapshot(streamlit_server, vpage):
    goto_and_settle(vpage, f"{streamlit_server}/")
    mask = [
        vpage.locator("text=/LIVE ·|FETCH FAILED/"),  # live-price caption (pills.py)
        vpage.locator("text=/CURATION OVERDUE/"),      # capex staleness banner
        vpage.locator('[data-testid="stDateInput"]'),  # sidebar today-anchored range
    ]
    assert_snapshot(vpage, "briefing", mask=mask)
