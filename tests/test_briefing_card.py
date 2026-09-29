"""Briefing · Daily briefing card + the null-safety a data-only report needs.

The card renders MarketReport's hand-written daily briefing (``data/briefings.json``,
``scripts/briefing.py publish``). Pins: silent when absent, sections in reading order,
sources linked, staleness stated, escaping.
"""
from __future__ import annotations

from components.briefing.daily_briefing import briefing_card_html


def _payload(**over):
    latest = {
        "id": "20260925T010000Z", "ts_sgt": "2026-09-25T13:10:00+08:00", "data_date": "2026-09-25",
        "what_matters": ["10-year yield 5.16% (+5bp).", "Micron reports Wed 30 Sep after the close."],
        "sections": {"data_notes": "Coverage 33/33.", "overnight": "META +4.5% (1.7 sigma).",
                     "earnings": "None out.", "extra_bit": "An unlisted section."},
        "sources": [{"title": "Yahoo Finance live", "url": "https://finance.yahoo.com/x", "date": "2026-09-24"},
                    {"title": "Shipped report", "url": "file:market_data/morning_report_2026-09-25.json"}],
    }
    latest.update(over)
    return {"schema": 1, "latest": latest, "recent": []}


def test_silent_when_nothing_published():
    assert briefing_card_html({}) == ""
    assert briefing_card_html({"latest": {"what_matters": [], "sections": {}}}) == ""


def test_sections_render_in_reading_order_with_sources():
    html = briefing_card_html(_payload(), "2026-09-25")
    assert "DAILY BRIEFING · 2026-09-25" in html and "TODAY" in html and "STALE" not in html
    order = [html.index(s) for s in ("What matters", "Overnight", "Earnings", "Data notes", "Extra bit")]
    assert order == sorted(order)
    assert 'href="https://finance.yahoo.com/x"' in html
    assert "Shipped report" in html and 'href="file:' not in html        # repo paths are not links
    assert "Information, not advice" in html


def test_staleness_is_stated_not_implied():
    html = briefing_card_html(_payload(), "2026-09-28")
    assert "STALE" in html and "older than the report on screen (2026-09-28)" in html
    assert 'data-stale="1"' in html


def test_revision_is_marked():
    assert "revised" in briefing_card_html(_payload(revises="20260925T000000Z"), "2026-09-25")


def test_text_is_escaped():
    html = briefing_card_html(_payload(what_matters=["<script>alert(1)</script>"]), "2026-09-25")
    assert "<script>" not in html


def test_terminology_leads_with_the_model_off_notice_only_after_a_data_only_report():
    from components.terminology import mechanical_since, page_html, sections_for
    model = {"2026-09-25": {"meta": {"llm_enabled": True}}, "2026-09-24": {"meta": {}}}
    assert mechanical_since(model) is None and sections_for(model)[0]["id"] != "report-model-off"
    both = dict(model, **{"2026-09-30": {"meta": {"llm_enabled": False}},
                          "2026-10-01": {"meta": {"llm_enabled": False}}})
    secs = sections_for(both)
    assert mechanical_since(both) == "2026-09-30" and secs[0]["id"] == "report-model-off"
    html = page_html(secs, {s["id"] for s in secs})
    assert "Report model switched off" in html and "From 2026-09-30" in html


# ── record v2 (MarketReport spec 2026-09-28-briefing-card-v2.md) ─────────────

def _v2(**over):
    latest = {
        "schema": 2, "id": "20260928T044233Z", "ts_sgt": "2026-09-28T12:42:33+08:00", "data_date": "2026-09-28",
        "as_of": [{"label": "US prices", "when": "Fri 25 Sep close", "note": "Every US move"}],
        "what_matters": [{"kind": "earnings", "tag_note": "in 2 days", "head": "Micron reports Thu 1 Oct.",
                          "detail": "Consensus under Earnings."},
                         {"kind": "after", "head": "Hormuz headline.", "detail": "Not in Friday's prices.", "src": [1]}],
        "after_data": [{"lead": "Oil Monday:", "text": "Brent +1.8%.", "src": [1]}],
        "tape_note": "Quiet tape.",
        "movers": [{"key": "MSFT", "why": "Copilot overhaul.", "why_state": "found", "src": [1]},
                   {"key": "U11_SI", "why": "No reported cause found.", "why_state": "none_found"},
                   {"key": "000660_KS", "why": "Holiday catch-up.", "why_state": "found", "size_note": "size not comparable"}],
        "group_notes": {"KRX": "vs the 23 Sep close"},
        "tonight": "No scheduled US release.",
        "calendar": [{"sgt": "2026-09-29T22:00", "kind": "macro", "what": "JOLTS (Aug)", "impact": "medium"},
                     {"sgt": "2026-10-01T04:05", "kind": "earnings", "what": "Micron FQ4", "impact": "high"}],
        "rechecks": [{"date": "2026-10-01", "items": [{"name": "Palantir", "q": "Maven by 30 Sep?"}]}],
        "earnings": {"coming": [{"key": "MU", "period": "fiscal Q4", "when_sgt": "2026-10-01T04:05",
                                 "revenue": {"consensus": 51.2, "guide_low": 49.0, "guide_high": 51.0,
                                             "range_low": 46.9, "range_high": 59.8, "analysts": 35}}]},
        "chart_facts": {"names": ["BE", "AVGO"], "note": "Plain note."},
        "data_notes": "Clean day.",
        "sources": [{"title": "Report", "url": "file:market_data/morning_report_2026-09-28.json"},
                    {"title": "Oil story (CNBC)", "url": "https://www.cnbc.com/x", "date": "2026-09-28"}],
        "numbers": {
            "tape": [{"name": "SPY", "chg_pct": 0.54, "5d_pct": 1.3, "x_usual": 0.8, "level": None, "bp": None},
                     {"name": "US10Y", "chg_pct": 0.43, "5d_pct": 3.7, "x_usual": 0.5, "level": 5.18, "bp": 2}],
            "movers": {"MSFT": {"name": "Microsoft", "market": "US", "chg_pct": 3.66, "x_usual": 2.1, "vol_ratio": 1.6},
                       "U11_SI": {"name": "UOB", "market": "SGX", "chg_pct": 2.14, "x_usual": 2.0, "vol_ratio": 0.72},
                       "000660_KS": {"name": "SK Hynix", "market": "KRX", "chg_pct": -4.1, "x_usual": 0.5,
                                     "vol_ratio": 0.67}},
            "also_moved": [{"key": "WRD", "name": "WeRide", "chg_pct": -4.49, "x_usual": 1.4, "vol_ratio": 1.27}],
            "chart": {"BE": {"name": "Bloom Energy", "vs_sma50_pct": 25.7, "rsi": 62.8},
                      "AVGO": {"name": "Broadcom", "vs_sma50_pct": -6.2, "rsi": 44.0}},
            "names": {"MU": "Micron"},
            "further_out": [{"date": "2026-10-14", "kind": "macro", "what": "CPI Report (September)", "later": False},
                            {"date": "2026-10-14", "kind": "earnings", "key": "ASML", "what": "ASML", "later": False},
                            {"date": "2026-10-28", "kind": "macro", "what": "FOMC Rate Decision", "later": False},
                            {"date": "2026-10-12", "kind": "event", "what": "OCP Global Summit 2026",
                             "end_date": "2026-10-15", "later": False},
                            {"date": "2026-10-20", "kind": "earnings", "what": "Oracle", "later": False,
                             "read_across": ["Nvidia", "CoreWeave"]},
                            {"date": "2026-11-03", "kind": "earnings", "key": "AMD", "what": "AMD", "later": True},
                            {"date": "2026-11-17", "kind": "earnings", "key": "NVDA", "what": "Nvidia", "later": True}],
            "health": {"fetched": 33, "expected": 33, "stale_tickers": [], "latch_active": False,
                       "last_us_session": "2026-09-25", "holes": []},
        },
    }
    latest.update(over)
    return {"schema": 1, "latest": latest, "recent": []}


def test_v2_renders_in_reading_order():
    html = briefing_card_html(_v2(), "2026-09-28")
    heads = [f"<h3>{s}</h3>" for s in ("What matters", "After the data", "The tape", "Names that moved",
                                        "Week ahead", "Earnings", "Further out", "Chart facts", "Data notes",
                                        "All sources")]
    order = [html.index(s) for s in ["Monday 28 September", *heads, "Information, not advice"]]
    assert order == sorted(order)
    assert "Overnight" not in html                                     # not the v1 renderer


def test_v2_movers_group_by_market_and_keep_searched_apart_from_not_looked_up():
    html = briefing_card_html(_v2(), "2026-09-28")
    assert html.index("US · Fri 25 Sep close") < html.index("Singapore") < html.index("Korea")
    assert "vs the 23 Sep close" in html and "size not comparable" in html and "2.1× usual" in html
    assert 'class="bf-why bf-none"' in html                           # searched, nothing found
    assert "Also moved, not looked up:" in html and "WeRide" in html  # never searched
    assert "−4.10%" in html                                           # true minus, no hue


def test_v2_sources_are_chips_where_used_and_repo_paths_are_not_links():
    html = briefing_card_html(_v2(), "2026-09-28")
    assert html.count('class="bf-src" href="https://www.cnbc.com/x"') >= 2
    assert ">CNBC <sup>28 Sep</sup>" in html
    assert 'href="file:' not in html


def test_v2_week_and_earnings_and_chart():
    html = briefing_card_html(_v2(), "2026-09-28")
    assert "Tonight" in html and "No scheduled US release." in html and "JOLTS (Aug)" in html
    assert '<span data-kind="event">Conference</span>' in html                # legend names the new kind
    assert "Catalyst rechecks due:</b> 1 item across 1 date" in html
    assert "~$51.2B" in html and "$50.0B ± 1.0" in html and "consensus 51.2" in html
    assert "+25.7%" in html and "−6.2%" in html and "RSI" in html
    assert "all clear" in html and "bf-fault" not in html


def test_v2_further_out_groups_by_date_and_names_the_estimate_caveat():
    html = briefing_card_html(_v2(), "2026-09-28")
    far = html[html.index("<h3>Further out</h3>"):html.index("<h3>Chart facts</h3>")]
    soon, later = far.split('<div class="bf-later">')
    assert soon.count("<li>") == 4 and "Wed 14 Oct" in soon and "Wed 28 Oct" in soon
    assert '<b data-kind="event">OCP Global Summit 2026<small>to Thu 15 Oct</small></b>' in soon
    assert "Oracle earnings<small>not held · moves Nvidia, CoreWeave</small>" in soon
    assert "Later · 31–60 days · less certain" in later and "often estimates" in later
    assert "Nvidia earnings" in later and "AMD" not in soon
    assert "<details" not in far                                      # static: visible without a click
    assert '<b data-kind="earnings">ASML earnings</b>' in far and '<b data-kind="macro">FOMC Rate Decision</b>' in far
    assert "some are its estimates" in far
    none = _v2()
    none["latest"]["numbers"].pop("further_out")
    assert "Further out" not in briefing_card_html(none, "2026-09-28")   # older records: section absent


def test_v2_flags_a_real_data_fault_only():
    bad = _v2()
    bad["latest"]["numbers"]["health"].update(stale_tickers=["D05_SI"], latch_active=True)
    html = briefing_card_html(bad, "2026-09-28")
    assert html.count("bf-ok bf-fault") == 2 and "2 to check" in html


def test_v2_staleness_and_escaping():
    html = briefing_card_html(_v2(what_matters=[{"kind": "move", "head": "<script>x</script>"}]), "2026-09-30")
    assert "<script>" not in html
    assert 'data-stale="1"' in html and "older than the report on screen (2026-09-30)" in html


def test_v2_card_css_never_puts_a_verdict_colour_on_this_surface():
    # Colour is a claim: no .bf- rule may reference a good/bad token; --stress is the
    # data-fault chip's alone.
    import pathlib
    import re

    css = (pathlib.Path(__file__).resolve().parents[1] / "assets" / "theme.css").read_text(encoding="utf-8")
    rules = re.findall(r"([^{}]*\.bf\b[^{}]*)\{([^}]*)\}", css)     # .bf-x and the .bf-scoped kind hues
    assert rules, "briefing v2 CSS not found"
    banned = ("--up", "--down", "--buy", "--accumulate", "--watch", "--caution", "--avoid",
              "#22c55e", "#ef4444", "#4ade80", "#f87171")
    for selector, body in rules:
        for token in banned:
            assert token not in body, f"{selector.strip()} uses {token}"
        if "--stress" in body:
            assert "bf-fault" in selector, f"{selector.strip()} uses --stress outside the fault chip"
