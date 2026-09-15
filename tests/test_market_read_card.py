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
from lib.formatters import _escape_dollars

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
            "notes": "No verified headline behind the Hynix move; treated as flow.",
            "headline_context": ["Investing.com - oil tops $100 (Sep 9, 2026)"],
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


# ── the read's own counter-evidence (added 2026-09-09) ───────────────────────

def test_card_renders_the_caveats_and_the_sources():
    # These are the half of the read that argues against its own leans. Both were
    # published-but-unrendered on the first ship; the card cited "a MS downgrade"
    # with the source sitting two lines away in the payload.
    html = market_read_card_html(_payload(), _dt.datetime(2026, 9, 9, 18, 0, tzinfo=UTC))
    assert "Caveats" in html and "No verified headline" in html
    assert "Sources" in html and "oil tops &#36;100" in html


def test_every_published_field_is_either_rendered_or_structural():
    # Guards the defect class rather than the instance: publishing a field the
    # card silently drops is how the sources went missing in the first place.
    structural = {"id", "ts_utc", "ts_et", "revises", "targets", "leans", "summary"}
    html = market_read_card_html(_payload(), _dt.datetime(2026, 9, 9, 18, 0, tzinfo=UTC))
    for key, val in _payload()["latest"].items():
        if key in structural:
            continue
        probe = val[0] if isinstance(val, list) else val
        head = _escape_dollars(str(probe))[:30]
        assert head in html, f"published but not rendered: {key}"


def test_blocks_are_silent_when_their_field_is_absent():
    p = _payload()
    p["latest"].pop("notes")
    p["latest"].pop("headline_context")
    html = market_read_card_html(p, _dt.datetime(2026, 9, 9, 18, 0, tzinfo=UTC))
    assert "Caveats" not in html and "Sources" not in html
    assert "Chips" in html          # the rest of the card is unaffected


# ── structural colour only (owner decision 2026-09-14) ──────────────────────

def test_card_css_never_puts_a_verdict_colour_on_this_surface():
    # The card got section accents on 2026-09-14, drawn from the non-verdict
    # metric palette. Colour lives in theme.css, not the markup, so the guard
    # has to read the stylesheet: no .mr- rule may reference a good/bad token.
    import pathlib
    import re

    css = (pathlib.Path(__file__).resolve().parents[1] / "assets" / "theme.css").read_text(
        encoding="utf-8")
    rules = re.findall(r"([^{}]*\.mr-[^{}]*)\{([^}]*)\}", css)
    assert rules, "market-read CSS not found"
    banned = ("--up", "--down", "--buy", "--accumulate", "--watch", "--caution",
              "--avoid", "--stress", "#22c55e", "#ef4444", "#4ade80", "#f87171")
    for selector, body in rules:
        for token in banned:
            assert token not in body, f"{selector.strip()} uses {token}"


def test_lean_direction_is_a_glyph_not_a_hue():
    html = market_read_card_html(_payload(), _dt.datetime(2026, 9, 9, 18, 0, tzinfo=UTC))
    assert '<i class="mr-arrow" aria-hidden="true">↓</i>slightly down' in html
    assert "data-lean" not in html and "style=" not in html


# ── plain-language summary (2026-09-14) ─────────────────────────────────────
# The card used to show only the logged grading fields — terse, number-dense —
# while the reader understood the read from the plain reply in the session. With
# a summary the card mirrors that reply; the logged fields sit in a drawer.

_NOW = _dt.datetime(2026, 9, 9, 18, 0, tzinfo=UTC)


def _with_summary(**over):
    p = _payload()
    p["latest"]["summary"] = {
        "read_id": p["latest"]["id"],
        "bottom_line": "Hold what the market gives you; do not add before CPI.",
        "where_we_are": "20:58 SGT, US pre-market; CPI tomorrow 20:30 SGT.",
        "macro_attribution": "Oil moved most; the lean depends on it.",
        "what_happened": ["Brent crossed $100 overnight (tape)."],
        "per_group": {"semis": "Flat. The gap is already paid for."},
        "change_my_mind": ["Brent back under $100 flips chips up."],
        "confidence": "The fall is already in the price.",
        "cant_know": "Whether CPI surprises.",
        "the_call": "Down, mildly. Energy holds up best.",
        "sources": [{"title": "Oil tops $100", "url": "https://example.com/oil", "date": "Sep 9"}],
        **over,
    }
    return p


def test_summary_sections_render_in_the_order_of_the_plain_reply():
    html = market_read_card_html(_with_summary(), _NOW)
    order = ["Bottom line", "Where we are", "What happened", "What I expect, per group",
             "What would change my mind", "Confidence", "The call", "Sources",
             "Grading notes"]
    idx = [html.index(label) for label in order]
    assert idx == sorted(idx), dict(zip(order, idx, strict=True))


def test_every_summary_field_is_rendered():
    p = _with_summary()
    html = market_read_card_html(p, _NOW)
    for key, val in p["latest"]["summary"].items():
        if key == "read_id":
            continue
        if isinstance(val, dict):
            probe = next(iter(val.values()))
            probe = probe["title"] if isinstance(probe, dict) else probe
        elif isinstance(val, list):
            probe = val[0]["title"] if isinstance(val[0], dict) else val[0]
        else:
            probe = val
        assert _escape_dollars(str(probe))[:25] in html, f"summary field not rendered: {key}"


def test_summary_card_still_carries_the_logged_record_in_the_drawer():
    html = market_read_card_html(_with_summary(), _NOW)
    for logged in ("gap pre-paid", "No verified headline", "oil tops &#36;100", "Brent back under"):
        assert logged in html, logged


def test_lean_chips_come_from_the_logged_record_not_the_summary():
    # The summary supplies sentences only; the graded call is the log's.
    p = _with_summary(per_group={"market": "Slightly up, strongly."})
    html = market_read_card_html(p, _NOW)
    row = html[html.index("Whole market"):]
    assert "slightly down" in row[:400]


def test_summary_source_links_are_http_only():
    p = _with_summary(sources=[{"title": "bad", "url": "javascript:alert(1)"}])
    html = market_read_card_html(p, _NOW)
    assert "javascript:" not in html and ">bad<" in html


def test_a_read_without_a_summary_uses_the_same_structure_minus_summary_only_sections():
    html = market_read_card_html(_payload(), _NOW)
    assert "What I expect, per group" in html and "What would change my mind" in html
    assert 'data-sec="confidence"' in html and 'data-sec="sources"' in html
    assert "Bottom line" not in html and "The call" not in html and "Grading notes" not in html
