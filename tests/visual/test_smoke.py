import pytest


@pytest.mark.visual
def test_app_boots_and_renders_masthead(streamlit_server, vpage):
    vpage.goto(f"{streamlit_server}/", wait_until="networkidle")
    vpage.wait_for_selector("text=The Market Report", timeout=30_000)
    assert "MarketReport" in vpage.title()
