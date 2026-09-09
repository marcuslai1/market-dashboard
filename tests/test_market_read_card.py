"""Briefing · Market Read card (experimental adviser surface).

Pins the three constraints the card exists under (owner decisions 2026-09-09):
no score, no colour, and staleness stated rather than implied. The freshness
state machine is the part with real logic — a read whose US legs have closed
while its SGX leg has not is neither live nor history, and the header must not
claim either.
"""
from __future__ import annotations

import datetime as _dt

from components.briefing.market_read import (
    STALE_AFTER_DAYS,
    market_read_card_html,
    read_state,
)

UTC = _dt.timezone.utc


def _payload(**over):
    base = {
        "schema": 1,
        "sessions_read": 4,
        "reads_logged": 6,
        "exit_review_at": 20,
        "scored": False,
        "latest": {
            "id": "20260909T125842Z",
            "ts_utc": "2026-09-09T12:58:42Z",
            "ts_sgt": "2026-09-09 20:58",
            "confidence": "low",
            "confidence_why": "the fall is already in the price",
            "tells": ["Brent back under $100 flips chips up"],
            "leans": {
                "market": {"lean": "soft", "guidance": "dont_add", "why": "oil into CPI"},
                "semis": {"lean": "neutral", "guidance": "hold", "why": "gap pre-paid"},
            },
            "targets": {
                "market": {"benchmark": "SPY", "target_session": "2026-09-09",
                           "target_close_utc": "2026-09-09T20:00:00Z"},
                "semis": {"benchmark": "SOXX", "target_session": "2026-09-09",
                          "target_close_utc": "2026-09-09T20:00:00Z"},
                "sg_banks": {"benchmark": "^STI", "target_session": "2026-09-10",
                             "target_close_utc": "2026-09-10T09:00:00Z"},
            },
        },
    }
    base.update(over)
    return base


# ── freshness ────────────────────────────────────────────────────────────────

def test_state_is_live_while_every_target_close_is_ahead():
    st = read_state(_payload(), _dt.datetime(2026, 9, 9, 18, 0, tzinfo=UTC))
    assert st["state"] == "live" and st["stale"] is False


def test_state_is_in_play_when_the_us_legs_closed_but_the_sgx_leg_has_not():
    # The honest middle state: claiming "live" would overstate it and "matured"
    # would hide that the SG banks lean is still unresolved.
    st = read_state(_payload(), _dt.datetime(2026, 9, 9, 21, 0, tzinfo=UTC))
    assert st["state"] == "in_play"


def test_state_matures_once_the_last_target_close_passes():
    assert read_state(_payload(), _dt.datetime(2026, 9, 10, 12, 0, tzinfo=UTC))["state"] == "matured"


def test_a_matured_read_goes_stale_and_the_header_stops_implying_currency():
    now = _dt.datetime(2026, 9, 9, 13, tzinfo=UTC) + _dt.timedelta(days=STALE_AFTER_DAYS + 1)
    st = read_state(_payload(), now)
    assert st["state"] == "matured" and st["stale"] is True
    html = market_read_card_html(_payload(), now)
    assert "no read since" in html
    assert 'data-stale="1"' in html


def test_state_is_unknown_rather_than_live_when_targets_are_missing():
    p = _payload()
    p["latest"]["targets"] = {}
    assert read_state(p, _dt.datetime(2026, 9, 9, 18, 0, tzinfo=UTC))["state"] == "unknown"


# ── the three constraints ────────────────────────────────────────────────────

def test_card_shows_the_progress_counter_and_never_a_hit_rate():
    # market-dashboard CLAUDE.md: never reintroduce a local hit-rate headline.
    html = market_read_card_html(_payload(), _dt.datetime(2026, 9, 9, 18, 0, tzinfo=UTC))
    assert "session 4 of 20" in html and "not yet scored" in html
    for banned in ("hit-rate", "hit rate", "hit_rate", "62.5", "always-firm", "signed ret"):
        assert banned not in html, banned


def test_card_labels_itself_experimental():
    html = market_read_card_html(_payload(), _dt.datetime(2026, 9, 9, 18, 0, tzinfo=UTC))
    assert "EXPERIMENTAL" in html


def test_card_carries_no_signal_colour():
    # Unproven ⇒ neutral ink only. No signal palette hex, no green/red tokens.
    html = market_read_card_html(_payload(), _dt.datetime(2026, 9, 9, 18, 0, tzinfo=UTC))
    for banned in ("#22c55e", "#ef4444", "var(--buy", "var(--caution", "var(--avoid"):
        assert banned not in html, banned


def test_card_states_its_independence_from_the_report():
    html = market_read_card_html(_payload(), _dt.datetime(2026, 9, 9, 18, 0, tzinfo=UTC))
    assert "independent of the morning report" in html


# ── rendering ────────────────────────────────────────────────────────────────

def test_leans_render_as_words_not_enum_values():
    html = market_read_card_html(_payload(), _dt.datetime(2026, 9, 9, 18, 0, tzinfo=UTC))
    assert "slightly down" in html
    assert ("don't add" in html) or ("don&#39;t add" in html)
    assert ">soft<" not in html and ">dont_add<" not in html


def test_clusters_render_in_the_skills_reading_order():
    html = market_read_card_html(_payload(), _dt.datetime(2026, 9, 9, 18, 0, tzinfo=UTC))
    assert html.index("Chips") < html.index("Whole market")


def test_prose_is_html_escaped_so_a_tape_comparison_cannot_break_markup():
    p = _payload()
    p["latest"]["leans"]["semis"]["why"] = "SOXX <b>gapped</b> on oil>$100 & rates"
    html = market_read_card_html(p, _dt.datetime(2026, 9, 9, 18, 0, tzinfo=UTC))
    assert "<b>gapped</b>" not in html
    assert "oil&gt;&#36;100 &amp; rates" in html


def test_card_is_silent_when_nothing_has_been_published():
    # On-demand instrument: "never published" is normal, not an error state.
    assert market_read_card_html({}) == ""
    assert market_read_card_html({"latest": None}) == ""
    assert market_read_card_html(_payload(latest={"leans": {}})) == ""
