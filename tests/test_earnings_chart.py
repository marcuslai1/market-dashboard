"""components/earnings_chart.py — revenue / EPS trajectory charts (owner 2026-09-29)."""
from __future__ import annotations

import re

from components.earnings_chart import (
    block_html,
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


BEAT = "what happened: above (+) or below (−) analysts"      # the result-vs-analysts % row


def _notes(html_):
    return re.findall(r'<p class="ec-note">(.*?)</p>', html_)


def _rows(html_):
    """{row label: [cell text, ...]} for the table under the axis ("" = a dash cell)."""
    out = {}
    for label, cells in re.findall(r'<div class="ec-row[^"]*"><span class="ec-rh">(.*?)</span>(.*?)</div>', html_):
        out[label] = [("" if "ec-na" in cls else v) for cls, v in
                      re.findall(r'<span class="(ec-rc[^"]*)">(.*?)</span>', cells)]
    return out


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


def test_revenue_chart_growth_year_on_year_and_the_coming_note():
    html_ = revenue_chart_html(quarter_series(MU), "US$", company=(49.0e9, 51.0e9), whisker=(46.9e9, 59.8e9))
    # a % to one decimal (owner 2026-09-29), not the first ship's 1.2× / 1.7×
    assert _rows(html_)["vs previous quarter"] == ["", "+21.7%", "+20.6%", "+74.9%", "+73.7%", "~+23.9%"]
    notes = _notes(html_)
    assert "Latest quarter vs a year earlier: +345.7%" in notes
    assert "Coming quarter vs the last: analysts ~+23.9% · company forecast ~+20.6%" in notes
    assert "×" not in html_
    assert _notes(revenue_chart_html(quarter_series(MU), mini=True)) == [
        "Last quarter: +73.7% vs the one before · +345.7% vs a year ago", "Next: ~+23.9% (analysts)"]
    assert 'class="ec-est"' in html_ and 'class="ec-band"' in html_ and 'class="ec-whisker"' in html_
    assert "~51.35" in html_                                                # the data's own precision, not a story


def test_no_multiplier_across_a_missing_quarter():
    rows = [_row("2025-06-30", 1.0e9), _row("2025-09-30", 1.2e9), _row("2025-12-31", 1.3e9),
            _row("2026-03-31", 1.1e9), _row("2026-06-30", eps=0.5), _row("2026-09-30", rev_est=2.0e9)]
    s = quarter_series(rows)
    html_ = revenue_chart_html(s, mini=True)
    assert '<span class="ec-miss">·</span>' in html_ and html_.count('class="ec-miss"') == 1   # a dot; words only on hover
    assert _notes(html_) == ["Last quarter not on file"]                        # never "2.0e9 / 1.1e9" across the gap
    full = revenue_chart_html(s)
    assert "not on file" in full and "~+81.8%" not in full


def test_shrinking_quarter_reads_as_a_minus():
    rows = [_row("2025-12-31", 213.39e9), _row("2026-03-31", 181.52e9)]
    html_ = revenue_chart_html(quarter_series(rows))
    assert _rows(html_)["vs previous quarter"] == ["", "−14.9%"]


def test_eps_chart_draws_from_zero_and_handles_negatives():
    rows = [_row("2025-03-31", eps=-0.06, eps_est=-0.05), _row("2025-06-30", eps=0.10, eps_est=0.02),
            _row("2025-09-30", eps=0.15, eps_est=0.10)]
    html_ = eps_chart_html(quarter_series(rows))
    assert "ec-neg" in html_ and "−0.06" in html_
    assert _rows(html_)[BEAT] == ["", "+400.0%", "+50.0%"]   # no % on a negative base


def test_empty_table_cells_are_dashes_not_holes():
    """Owner 2026-09-29: blank cells under the chart read as a broken table — a dash says 'none'."""
    html_ = revenue_chart_html(quarter_series(MU))
    assert '<span class="ec-rc ec-na">–</span>' in html_
    assert '<span class="ec-rc"></span>' not in html_


def test_analysts_estimate_number_sits_beside_its_line():
    """Owner 2026-09-29: the estimate's number on the chart, not just its position. On a narrow
    chart the same numbers ride in a 'what analysts expected' row (CSS shows one or the other)."""
    mu = [dict(r) for r in MU]
    mu[4]["revenue_estimate"] = 35.84e9
    html_ = revenue_chart_html(quarter_series(mu))
    assert re.findall(r'<span class="ec-tv"[^>]*>([^<]*)', html_) == ["35.84"]
    assert _rows(html_)["what analysts expected"] == ["", "", "", "", "35.84", ""]
    assert 'class="ec-row ec-row-narrow"><span class="ec-rh">what analysts expected' in html_
    eps = eps_chart_html(quarter_series(MU))
    assert re.findall(r'<span class="ec-tv"[^>]*>([^<]*)', eps) == ["1.59", "2.86", "3.96", "9.16", "20.69"]
    assert "ec-tv" not in revenue_chart_html(quarter_series(mu), mini=True)     # no marks on a thumbnail


def test_roomy_chart_puts_both_comparisons_on_the_plot():
    """Owner 2026-09-29: the result-vs-analysts % sits beside the analysts' number (12.8 +6.6%),
    and growth sits between the two quarters it compares; their table rows are marked so CSS
    drops them where the plot carries the numbers (and keeps them on a phone)."""
    mu = [dict(r) for r in MU]
    mu[2]["revenue_estimate"] = 12.8e9
    html_ = revenue_chart_html(quarter_series(mu), company=(49.0e9, 51.0e9))
    assert '12.8<b class="ec-tvb">+6.6%</b>' in html_
    assert re.findall(r'<span class="ec-g"[^>]*>([^<]*)', html_) == ["+21.7%", "+20.6%", "+74.9%", "+73.7%", "~+23.9%"]
    assert 'title="Sep–Nov 2025 → Dec–Feb 2026: +74.9%"' in html_
    assert 'title="Mar–May 2026 → Jun–Aug 2026 (analysts expect): +23.9%"' in html_
    assert 'class="ec-row ec-row-onplot"><span class="ec-rh">vs previous quarter' in html_
    assert f'class="ec-row ec-row-onplot"><span class="ec-rh">{BEAT}' in html_
    eps = eps_chart_html(quarter_series(MU))
    assert '9.16<b class="ec-tvb">+33.2%</b>' in eps and "ec-g" not in eps     # EPS has no growth labels
    drop = revenue_chart_html(quarter_series([_row("2025-12-31", 213.39e9), _row("2026-03-31", 181.52e9)]))
    assert '<span class="ec-g" title="Oct–Dec 2025 → Jan–Mar 2026: −14.9%">−14.9%</span>' in drop
    assert "ec-g" not in revenue_chart_html(quarter_series(MU), mini=True)
    gap = [_row("2025-06-30", 1.0e9), _row("2025-09-30", 1.2e9), _row("2025-12-31", 1.3e9),
           _row("2026-03-31", 1.1e9), _row("2026-06-30", eps=0.5), _row("2026-09-30", rev_est=2.0e9)]
    assert re.findall(r'<span class="ec-g"[^>]*>([^<]*)', revenue_chart_html(quarter_series(gap))) == [
        "+20.0%", "+8.3%", "−15.4%"]                                                  # never across the missing quarter


def test_key_explains_the_on_plot_numbers_only_when_drawn():
    key = block_html(revenue_chart_html(quarter_series(MU)) + eps_chart_html(quarter_series(MU)))
    assert "beside the line: what happened, above (+) or below (−) analysts" in key
    assert "between quarters: revenue vs the quarter before" in key
    bare = block_html(eps_chart_html(quarter_series([_row("2025-03-31", eps=1.0), _row("2025-06-30", eps=1.2)])))
    assert "above (+) or below (−) analysts" not in bare and "revenue vs the quarter before" not in bare


def test_the_result_row_is_not_worded_as_a_second_analysts_row():
    """Owner 2026-09-30: 'what analysts expected' over 'vs what analysts expected' read as
    analysts against analysts. The % row is the result against them and says so, naming
    analysts itself (a 600–860px chart shows it without the estimate row above it)."""
    rows = _rows(revenue_chart_html(quarter_series([dict(r, revenue_estimate=r["revenue_actual"])
                                                    for r in MU])))
    assert list(rows) == ["vs previous quarter", "what analysts expected", BEAT]
    assert BEAT.startswith("what happened") and "analysts" in BEAT and "vs what analysts" not in BEAT


def test_title_sits_inside_the_chart_so_a_wide_chart_can_gutter_it():
    html_ = revenue_chart_html(quarter_series(MU))
    assert html_.index('class="ec-h"') > html_.index('class="ec"') and html_.index('class="ec-h"') < html_.index('class="ec-cols"')
    assert '<b>Revenue</b><span class="ec-hc">, </span><span class="ec-hu">US$ billions</span>' in html_


def test_tick_is_a_hairline_without_a_halo():
    """Owner 2026-09-29: the tick's paper halo cut a dark band through the reported bar."""
    import pathlib
    css = (pathlib.Path(__file__).resolve().parents[1] / "assets" / "theme.css").read_text(encoding="utf-8")
    body = re.search(r"\n\.ec-tick \{([^}]*)\}", css).group(1)
    assert "box-shadow" not in body and "height: 1.5px" in body


def test_charts_are_escaped_and_silent_without_history():
    assert revenue_chart_html(quarter_series([_row("2026-03-31", 1e9)])) == ""
    html_ = revenue_chart_html(quarter_series(MU), currency="<b>X</b>")
    assert "<b>X</b>" not in html_
    assert "what analysts expected beforehand" in key_html() and "company's own forecast" in key_html(company=True)
    assert block_html("") == ""


def test_key_sits_above_the_charts_on_both_surfaces():
    """Owner 2026-09-29: the key goes on top, so the marks are explained before they are read."""
    from components.briefing.daily_briefing_v2 import _detail_charts
    from components.watchlist.drilldown_drawers import _earnings_body_html
    recs = [dict(r, ticker="MU") for r in MU]
    for html_ in (_detail_charts("MU", {}, {}, {"MU": recs}), _earnings_body_html({}, str, recs)):
        assert 'class="ec-key"' in html_ and 'class="ec-h"' in html_
        assert html_.index('class="ec-key"') < html_.index('class="ec-h"')
        assert '<div class="ec-block">' in html_       # scoped rules outrank Streamlit's p reset


def test_chart_css_carries_no_verdict_colour():
    import pathlib
    css = (pathlib.Path(__file__).resolve().parents[1] / "assets" / "theme.css").read_text(encoding="utf-8")
    rules = re.findall(r"([^{}]*\.ec[-\s{][^{}]*)\{([^}]*)\}", css)
    assert rules
    for selector, body in rules:
        for token in ("--up", "--down", "--buy", "--caution", "--avoid", "--stress", "#22c55e", "#ef4444"):
            assert token not in body, f"{selector.strip()} uses {token}"


def _f(label: str) -> float:
    return float(label.lstrip("~+").replace("−", "-").replace(",", "").rstrip("%"))


def test_every_percentage_checks_out_against_the_printed_numbers():
    """Owner 2026-09-29, "11.2 to 11.3 is 0.8?": 11.315 vs 11.22 printed as 11.3 vs 11.2, which
    reads +0.9%. Labels now carry the data's own precision and each % is worked from them."""
    mu = [dict(r) for r in MU]
    for r, est in zip(mu[:5], (8.87e9, 11.22e9, 12.84e9, 20.07e9, 35.84e9), strict=True):
        r["revenue_estimate"] = est
    html_ = revenue_chart_html(quarter_series(mu), company=(49.0e9, 51.0e9))
    vals = re.findall(r'class="ec-val[^"]*"[^>]*>([^<]*)', html_)
    assert vals == ["9.301", "11.315", "13.643", "23.86", "41.456", "~51.35"]
    beats = re.findall(r'class="ec-tv"[^>]*>([^<]*)<b class="ec-tvb">([^<]*)', html_)
    assert beats[1] == ("11.22", "+0.8%")
    for v, (est, pct) in zip(vals[:5], beats, strict=True):
        assert f"{(_f(v) / _f(est) - 1) * 100:+.1f}%" == pct.replace("−", "-")
    grows = re.findall(r'<span class="ec-g"[^>]*>([^<]*)', html_)
    for a, b, g in zip(vals[:-1], vals[1:], grows, strict=True):
        assert f"{(_f(b) / _f(a) - 1) * 100:+.1f}%" == g.lstrip("~").replace("−", "-")
    eps = eps_chart_html(quarter_series(MU))
    for v, (est, pct) in zip(re.findall(r'class="ec-val"[^>]*>([^<]*)', eps),
                             re.findall(r'class="ec-tv"[^>]*>([^<]*)<b class="ec-tvb">([^<]*)', eps), strict=True):
        assert f"{(_f(v) / _f(est) - 1) * 100:+.1f}%" == pct.replace("−", "-")
