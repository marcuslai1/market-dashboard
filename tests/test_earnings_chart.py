"""components/earnings_chart.py — revenue / EPS trajectory charts (owner 2026-09-29)."""
from __future__ import annotations

import re

from components.earnings_chart import (
    eps_chart_html,
    key_html,
    period_label,
    quarter_series,
    revenue_chart_html,
)


def _row(qe, rev=None, rev_est=None, eps=None, eps_est=None):
    return {"quarter_end": qe, "revenue_actual": rev, "revenue_estimate": rev_est,
            "eps_actual": eps, "eps_estimate": eps_est}


MU = [_row("2025-05-31", 9.301e9, eps=1.91, eps_est=1.59), _row("2025-08-31", 11.315e9, eps=3.03, eps_est=2.86),
      _row("2025-11-30", 13.643e9, eps=4.78, eps_est=3.96), _row("2026-02-28", 23.86e9, eps=12.2, eps_est=9.16),
      _row("2026-05-31", 41.456e9, eps=25.11, eps_est=20.69), _row("2026-08-31", rev_est=51.34992584e9, eps_est=31.71)]


def _notes(html_):
    return re.findall(r'<p class="ec-note">(.*?)</p>', html_)


def test_period_label_names_the_three_months():
    assert period_label("2026-05-31") == ("Mar–May", "2026")
    assert period_label("2026-02-28") == ("Dec–Feb", "2026")


def test_series_orders_past_and_finds_the_coming_quarter():
    s = quarter_series(list(reversed(MU)))
    assert [q["qe"] for q in s["past"]] == ["2025-05-31", "2025-08-31", "2025-11-30", "2026-02-28", "2026-05-31"]
    assert s["coming"]["qe"] == "2026-08-31" and s["coming"]["rev_est"] == 51.34992584e9


def test_csv_estimate_wins_over_backfill_and_backfill_fills_gaps():
    rows = [_row("2026-02-28", 23.86e9, rev_est=22.0e9), _row("2026-05-31", 41.456e9)]
    bf = {"2026-02-28": {"revenue_estimate": 1.0}, "2026-05-31": {"revenue_estimate": 40.0e9, "provider": "LSEG"}}
    s = quarter_series(rows, bf)
    assert s["past"][0]["rev_est"] == 22.0e9 and "pipeline snapshot" in s["past"][0]["rev_est_src"]
    assert s["past"][1]["rev_est"] == 40.0e9 and s["past"][1]["rev_est_src"] == "LSEG"
    s2 = quarter_series([_row("2026-02-28", 23.86e9)], {"2026-05-31": {"revenue_actual": 41.456e9}})
    assert [q["rev"] for q in s2["past"]] == [23.86e9, 41.456e9]          # a backfilled actual adds the quarter


def test_revenue_chart_multipliers_year_on_year_and_the_coming_note():
    html_ = revenue_chart_html(quarter_series(MU), "US$", company=(49.0e9, 51.0e9), whisker=(46.9e9, 59.8e9))
    cells = re.findall(r'<span class="ec-rc">(.*?)</span>', html_)
    assert cells[:6] == ["", "1.2×", "1.2×", "1.7×", "1.7×", "~1.2×"]
    notes = _notes(html_)
    assert "Latest quarter vs a year earlier: 4.5×" in notes
    assert "Coming quarter vs the last: analysts ~1.24× · company forecast ~1.21×" in notes
    assert 'class="ec-est"' in html_ and 'class="ec-band"' in html_ and 'class="ec-whisker"' in html_
    assert "~51.4" not in html_ and "~51.3" in html_                        # 51.35 rounds as a number, not a story


def test_no_multiplier_across_a_missing_quarter():
    rows = [_row("2025-06-30", 1.0e9), _row("2025-09-30", 1.2e9), _row("2025-12-31", 1.3e9),
            _row("2026-03-31", 1.1e9), _row("2026-06-30", eps=0.5), _row("2026-09-30", rev_est=2.0e9)]
    s = quarter_series(rows)
    html_ = revenue_chart_html(s, mini=True)
    assert '<span class="ec-miss">·</span>' in html_ and html_.count('class="ec-miss"') == 1   # a dot; words only on hover
    assert _notes(html_) == ["Last quarter not on file"]                        # never "2.0e9 / 1.1e9" across the gap
    full = revenue_chart_html(s)
    assert "not on file" in full and "~1.8×" not in full


def test_shrinking_quarter_spells_out_the_drop():
    rows = [_row("2025-12-31", 213.39e9), _row("2026-03-31", 181.52e9)]
    html_ = revenue_chart_html(quarter_series(rows))
    assert "0.9× (−15%)" in html_


def test_eps_chart_draws_from_zero_and_handles_negatives():
    rows = [_row("2025-03-31", eps=-0.06, eps_est=-0.05), _row("2025-06-30", eps=0.10, eps_est=0.02),
            _row("2025-09-30", eps=0.15, eps_est=0.10)]
    html_ = eps_chart_html(quarter_series(rows))
    assert "ec-neg" in html_ and "−0.06" in html_
    assert re.findall(r'<span class="ec-rc">(.*?)</span>', html_) == ["", "+400%", "+50%"]   # no % on a negative base


def test_charts_are_escaped_and_silent_without_history():
    assert revenue_chart_html(quarter_series([_row("2026-03-31", 1e9)])) == ""
    html_ = revenue_chart_html(quarter_series(MU), currency="<b>X</b>")
    assert "<b>X</b>" not in html_
    assert "what analysts expected beforehand" in key_html() and "company's own forecast" in key_html(company=True)


def test_chart_css_carries_no_verdict_colour():
    import pathlib
    css = (pathlib.Path(__file__).resolve().parents[1] / "assets" / "theme.css").read_text(encoding="utf-8")
    rules = re.findall(r"([^{}]*\.ec[-\s{][^{}]*)\{([^}]*)\}", css)
    assert rules
    for selector, body in rules:
        for token in ("--up", "--down", "--buy", "--caution", "--avoid", "--stress", "#22c55e", "#ef4444"):
            assert token not in body, f"{selector.strip()} uses {token}"
