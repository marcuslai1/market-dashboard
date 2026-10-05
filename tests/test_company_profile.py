"""The drill-down's Company profile drawer (MarketReport company_profiles.json, 2026-10-06).

A static, checked card per company: facts with their sources, the date it was last
checked, structural colour only. The same card renders on every report date.
"""
import json
from pathlib import Path

from components.watchlist.company_profile import company_profile_html, profiles_by_key
from components.watchlist.drilldown import render_drilldown_detail_html

DATA = Path(__file__).resolve().parent.parent / "data" / "company_profiles.json"


def _card(**over):
    card = {
        "name": "SiTime Corporation", "listing": "Nasdaq · USD",
        "what_they_do": "SiTime designs timing chips.",
        "revenue_mix": {"period": "FY2025 (12 months to 31 Dec 2025)", "total": "US$326.7 million",
                        "basis": "one segment; end-market split from the calls",
                        "segments": [{"name": "Communications", "pct": 52.6, "plain": "Data-centre gear.",
                                      "src": ["s1"]},
                                     {"name": "Mobile", "pct": 47.4, "plain": "Phones.", "src": ["s1"]}],
                        "src": ["s1"]},
        "geography": {"period": "FY2025", "basis": "by ship-to location",
                      "regions": [{"name": "Hong Kong", "pct": 60.0}, {"name": "Other", "pct": 40.0}],
                      "src": ["s1"]},
        "customers": {"summary": "Arrow was 26% of revenue.",
                      "named": [{"who": "Arrow Electronics", "what": "Distributor.", "share": "26% of FY2025 revenue",
                                 "status": "disclosed", "src": ["s1"]},
                                {"who": "Acme", "what": "Reported: buys oscillators.", "share": None,
                                 "status": "reported", "src": ["s2"]}],
                      "src": ["s1"]},
        "competitors": {"basis": "named in its FY2025 annual report",
                        "named": [{"who": "Abracon", "where": "timing products"},
                                  {"who": "Rakon", "where": "timing products"},
                                  {"who": "Renesas", "where": "clock chips; since acquired"}],
                        "src": ["s1"]},
        "changes": [{"date": "2026-07-01", "what": "Bought Renesas's timing business.", "src": ["s1"]}],
        "sources": [{"id": "s1", "title": "Form 10-K", "url": "https://www.sec.gov/x.htm", "date": "2026-02-11",
                     "kind": "primary"},
                    {"id": "s2", "title": "Trade press", "url": "https://example.com/a", "date": "2026-03-01",
                     "kind": "secondary"}],
        "last_changed": "2026-10-05", "last_checked": "2026-10-06", "check": "",
    }
    card.update(over)
    return card


def test_no_card_no_drawer():
    assert company_profile_html(None) == ""
    assert company_profile_html({}) == ""


def test_drawer_states_when_the_card_was_checked():
    html = company_profile_html(_card())
    assert html.startswith('<details class="dd-drawer"><summary>Company profile · checked 6 Oct 2026</summary>')
    assert "Facts last changed 5 Oct 2026 · checked 6 Oct 2026." in html


def test_reading_order():
    html = company_profile_html(_card())
    order = [html.index(x) for x in ("SiTime designs timing chips.", "Revenue mix — FY2025",
                                     "Revenue by region — FY2025", ">Customers<", ">Competitors<",
                                     "Changes to the business", ">Sources<")]
    assert order == sorted(order)


def test_mix_shows_period_total_share_and_plain_line():
    html = company_profile_html(_card())
    assert "Total US&#36;326.7 million." in html          # $ neutralised for Streamlit
    assert '<span class="cp-pct">52.6%</span>' in html
    assert 'style="width:52.6%"' in html
    assert "Data-centre gear." in html


def test_geography_null_says_not_disclosed():
    html = company_profile_html(_card(geography=None))
    assert "Revenue by region" in html and "Not disclosed by the company." in html


def test_customers_carry_share_and_status():
    html = company_profile_html(_card())
    assert "<b>Arrow Electronics</b> · 26% of FY2025 revenue" in html
    assert '<span class="cp-tag">disclosed</span>' in html
    assert '<span class="cp-tag">reported</span>' in html


def test_competitors_sharing_a_market_share_one_line():
    html = company_profile_html(_card())
    assert "<b>Abracon, Rakon</b>" in html
    assert html.count("Timing products") == 1
    assert "<b>Renesas</b>" in html


def test_changes_are_dated_and_an_empty_list_says_so():
    assert '<span class="cp-date">1 Jul 2026</span>Bought' in company_profile_html(_card())
    html = company_profile_html(_card(changes=[]))
    assert "None found in the 12 months to 6 Oct 2026." in html


def test_source_ids_link_to_their_documents():
    html = company_profile_html(_card())
    assert '<a href="https://www.sec.gov/x.htm" target="_blank" rel="noopener noreferrer" title="Form 10-K">s1</a>' in html
    assert "Form 10-K</a> · 11 Feb 2026 · primary" in html


def test_unsafe_text_and_links_are_neutralised():
    card = _card(what_they_do="<script>x</script> sells $5 chips",
                 sources=[{"id": "s1", "title": 'T" onmouseover="x $1', "url": "https://ok.example/a",
                           "date": "2026-01-01", "kind": "primary"},
                          {"id": "s2", "title": "Bad link", "url": "javascript:alert(1)",
                           "date": "2026-01-01", "kind": "secondary"}])
    html = company_profile_html(card)
    assert "<script>" not in html and "&lt;script&gt;" in html
    assert "&#36;5" in html
    assert "javascript:" not in html
    assert 'title="T&quot; onmouseover=&quot;x &#36;1"' in html     # cannot leave the attribute


def test_structural_colour_only():
    html = company_profile_html(_card())
    for tone in ("--tone-", "--up", "--down", "--stress", "color:"):
        assert tone not in html, tone


def test_keys_match_the_report_and_aliases_share_a_card():
    data = {"_meta": {"aliases": {"SKHY": "000660.KS", "NOPE": "MISSING"}},
            "000660.KS": {"name": "SK hynix"}, "IFX.DE": {"name": "Infineon"}, "NVDA": {"name": "NVIDIA"}}
    by_key = profiles_by_key(data)
    assert set(by_key) == {"000660_KS", "SKHY", "IFX_DE", "NVDA"}
    assert by_key["SKHY"] is by_key["000660_KS"]
    assert profiles_by_key(None) == {} and profiles_by_key([]) == {}


def test_drilldown_puts_the_profile_before_the_earnings_drawer():
    d = {"price": 100.0, "currency": "USD", "chg_pct": 1.0, "next_earnings": {"date": "2026-11-05"}}
    html = render_drilldown_detail_html("SITM", d, report_date="2026-10-06", profile=_card())
    assert html.index("<summary>Company profile") < html.index("<summary>Earnings</summary>")
    assert "<summary>Company profile" not in render_drilldown_detail_html("SITM", d, report_date="2026-10-06")


def test_every_published_card_renders():
    """The real file, when the dashboard carries one: each card renders a drawer with its check date."""
    if not DATA.exists():
        return
    data = json.loads(DATA.read_text(encoding="utf-8"))
    by_key = profiles_by_key(data)
    for key, card in by_key.items():
        html = company_profile_html(card)
        assert html.startswith('<details class="dd-drawer"><summary>Company profile · checked '), key
        assert "\n\n" not in html, key                      # a blank line would end Streamlit's HTML block
