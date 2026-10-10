"""The next earnings print as a fact — the Watchlist's Earnings column and drawer.

Reads both report shapes (MarketReport spec 2026-10-01-info-only-watchlist §3):

* **post-cutover** — the plain ``next_earnings{date, days_until, status}`` field,
  status ``scheduled`` / ``released_overnight`` / ``unavailable``;
* **pre-cutover** — no such field. The date is the pre-earnings band's
  ``earnings_date`` when the print is ≤ 14 days out, otherwise
  ``meta.report_date + accumulate_gates.earnings_days_until``. That sum is exact
  by construction: the pipeline computes ``days_until`` as the earnings date minus
  the run date in calendar days (``pipeline/earnings.py``), and the run date is
  the report date. "Unavailable" is the g5 abstention the pipeline writes when
  the Yahoo calendar could not be read.

A print is a date, not a verdict: nothing here carries a colour.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import NamedTuple

#: The release has happened (reported after the last US close).
REPORTED = "reported"
#: The calendar could not be read; proximity is unknown, not "none".
UNAVAILABLE = "unavailable"
TODAY = "today"
SCHEDULED = "scheduled"


class NextEarnings(NamedTuple):
    when: date | None
    days_until: int | None
    status: str
    #: Yahoo itself marks the date an estimate: the company has not announced it
    #: (``next_earnings.date_estimated``, MarketReport 2026-10-10).
    estimated: bool = False
    #: The date comes from the company's own notice, not Yahoo
    #: (``next_earnings.date_source == "confirmed"``, MarketReport 2026-10-10).
    confirmed: bool = False


def _parse_date(v) -> date | None:
    try:
        return date.fromisoformat(str(v)[:10])
    except (TypeError, ValueError):
        return None


def _int(v) -> int | None:
    return int(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def _status_for(days: int | None, released: bool) -> str:
    if released or (days is not None and days < 0):
        return REPORTED
    if days == 0:
        return TODAY
    return SCHEDULED


def next_earnings(d: dict, report_date: str | None) -> NextEarnings | None:
    """The name's next (or just-released) print, or ``None`` when the report
    names no date for it at all."""
    ne = d.get("next_earnings")
    if isinstance(ne, dict) and ne:
        days = _int(ne.get("days_until"))
        if ne.get("status") == "unavailable":
            return NextEarnings(None, None, UNAVAILABLE)
        when = _parse_date(ne.get("date"))
        if when is None and days is None:
            return None
        return NextEarnings(when, days,
                            _status_for(days, ne.get("status") == "released_overnight"),
                            estimated=ne.get("date_estimated") is True,
                            confirmed=ne.get("date_source") == "confirmed")

    band = d.get("pre_earnings_band") or {}
    gates = d.get("accumulate_gates") or {}
    days = _int(band.get("days_until"))
    if days is None:
        days = _int(gates.get("earnings_days_until"))
    when = _parse_date(band.get("earnings_date"))
    if when is None and days is not None:
        base = _parse_date(report_date)
        when = base + timedelta(days=days) if base else None
    if when is None and days is None:
        abstained = gates.get("abstained") or []
        if any(isinstance(a, dict) and a.get("gate") == "g5_no_earnings_7d"
               and "unavailable" in str(a.get("reason", "")) for a in abstained):
            return NextEarnings(None, None, UNAVAILABLE)
        return None
    released = band.get("temporal_status") == "released_overnight"
    return NextEarnings(when, days, _status_for(days, released))


def short_date(when: date | None) -> str:
    """``17 Nov`` — the masthead's day-month grammar, no leading zero."""
    return f"{when.day} {when:%b}" if when else "—"


def days_phrase(ne: NextEarnings) -> str:
    """The second line of the Earnings cell: ``in 47 d`` / ``today`` /
    ``reported`` / ``no calendar``; ``est. · in 19 d`` when the date is Yahoo's
    estimate."""
    if ne.status == UNAVAILABLE:
        return "no calendar"
    if ne.status in (REPORTED, TODAY):
        return ne.status
    if ne.days_until is None:
        return ""
    # Yahoo's own estimate, said where the date is read (no colour: a fact).
    return f"est. · in {ne.days_until} d" if ne.estimated else f"in {ne.days_until} d"
