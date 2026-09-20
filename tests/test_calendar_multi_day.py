"""Multi-day events show their range and which day of it today is (2026-09-20).

A conference is a week, not a date. The card used to print only a start date,
so a five-day show read as a one-day event — and upstream dropped the row the
morning after it opened, which is when its news actually starts. ECOC 2026
(Sep 20-24) was the case that surfaced it: last shown Sep 18, absent on Sep 21
as its exhibition opened and two days before its AI-networks panel.

`end_date` / `running` / `day_index` / `day_total` are stamped upstream by
`merge._build_events_this_week` against the REPORT date. They are display-lane
only — popped from the model payload, never read by a gate.
"""
from components.briefing.calendar import calendar_card_html

RUNNING = {"date": "2026-09-20", "end_date": "2026-09-24", "running": True,
           "day_index": 2, "day_total": 5, "event": "ECOC 2026",
           "impact": "HIGH", "type": "this_week", "tickers_affected": ["LITE"]}
UPCOMING = {"date": "2026-09-23", "end_date": "2026-09-24", "running": False,
            "event": "Meta Connect 2026", "impact": "MEDIUM",
            "type": "this_week"}
SINGLE = {"date": "2026-09-30", "event": "Micron Earnings", "impact": "HIGH",
          "type": "this_week"}


def test_a_running_event_shows_its_range_and_day_counter():
    html = calendar_card_html([RUNNING])
    assert "SEP 20\u201324" in html, "no date range on a multi-day row"
    assert "DAY 2 OF 5" in html, "reader cannot tell which day of the run it is"


def test_an_upcoming_multi_day_event_shows_the_range_but_no_counter():
    html = calendar_card_html([UPCOMING])
    assert "SEP 23\u201324" in html
    assert "DAY" not in html, "a counter on an event that has not started"


def test_a_single_day_event_gets_no_chip():
    html = calendar_card_html([SINGLE])
    assert "cal-run" not in html


def test_the_range_crossing_a_month_names_the_second_month():
    html = calendar_card_html([dict(RUNNING, date="2026-11-30",
                                    end_date="2026-12-03", day_total=4)])
    assert "NOV 30\u2013DEC 03" in html


def test_a_running_row_without_the_upstream_stamp_still_shows_its_range():
    """Reports written before the stamp existed must not render 'DAY None'."""
    row = {k: v for k, v in RUNNING.items()
           if k not in ("day_index", "day_total")}
    html = calendar_card_html([row])
    assert "SEP 20\u201324" in html
    assert "None" not in html and "DAY" not in html


def test_the_chip_carries_no_verdict_colour():
    """Standing rule: colour is a claim. A date range is a fact — the chip is
    an outline in the timing/ownership register, never a signal tint."""
    html = calendar_card_html([RUNNING])
    for token in ("--up", "--down", "var(--signal", "#22c55e", "#ef4444"):
        assert token not in html


def test_a_malformed_end_date_degrades_to_no_chip():
    for bad in ("not-a-date", "2026-09-20", "2026-09-19", None, ""):
        html = calendar_card_html([dict(RUNNING, end_date=bad)])
        assert "cal-run" not in html, f"end_date={bad!r} rendered a chip"
        assert "ECOC 2026" in html, f"end_date={bad!r} lost the row itself"


def test_a_running_event_files_under_the_day_it_is_on_not_its_start():
    """Sep 22 card: ECOC (started Sep 20, day 3 of 5) must sit under SEP 22,
    not under a past SEP 20 gutter at the top of "WHAT'S COMING"."""
    html = calendar_card_html([dict(RUNNING, day_index=3)])
    assert "Sep 22" in html and "TUE" in html
    assert "Sep 20<" not in html, "running row filed under its past start date"
    assert "SEP 20\u201324" in html, "the range chip must still name the true start"


def test_a_running_event_interleaves_with_that_days_other_rows():
    other = {"date": "2026-09-22", "event": "Micron Taoyuan mediation",
             "impact": "MEDIUM", "type": "this_week"}
    html = calendar_card_html([dict(RUNNING, day_index=3), other])
    assert html.count("Sep 22") == 1, "same day rendered as two gutters"


def test_an_upcoming_multi_day_event_still_files_under_its_start():
    html = calendar_card_html([UPCOMING])
    assert "Sep 23" in html


PROG = [{"date": "2026-09-21", "what": "Exhibition opens · industry awards"},
        {"date": "2026-09-22", "what": "Exhibition"},
        {"date": "2026-09-23", "what": "Exhibition (last day) · AI-networks / Ethernet panel"}]


def test_today_line_names_what_the_event_is_doing_on_the_report_day():
    row = dict(RUNNING, day_index=4, programme=PROG,
               programme_today=PROG[2]["what"])
    html = calendar_card_html([row])
    assert "cal-prog-today" in html
    assert "AI-networks / Ethernet panel" in html
    assert html.index("TODAY") < html.index("AI-networks / Ethernet panel")


def test_no_today_line_when_upstream_did_not_resolve_one():
    """Sep 20 / Sep 24: conference-only days the page does not itemise."""
    row = dict(RUNNING, day_index=1, programme=PROG)
    html = calendar_card_html([row])
    assert "cal-prog-today" not in html
    assert "Day by day" in html, "the drawer must still list the itemised days"


def test_day_by_day_drawer_lists_every_entry_in_date_order_and_marks_today():
    row = dict(RUNNING, day_index=3, programme=list(reversed(PROG)),
               programme_today=PROG[1]["what"])
    html = calendar_card_html([row])
    assert html.count("cal-prog-row") == 3
    assert (html.index("MON SEP 21") < html.index("TUE SEP 22")
            < html.index("WED SEP 23")), "drawer rows not in date order"
    assert html.count('data-today="1"') == 1
    assert "MON SEP 21" in html


def test_no_programme_means_no_drawer_and_no_today_line():
    html = calendar_card_html([RUNNING])
    assert "Day by day" not in html and "cal-prog" not in html


def test_malformed_programme_entries_are_skipped_not_rendered():
    row = dict(RUNNING, programme=[{"date": "2026-09-21"}, "junk", {"what": "x"},
                                   {"date": "2026-09-23", "what": "Panel"}])
    html = calendar_card_html([row])
    assert html.count("cal-prog-row") == 1 and "Panel" in html


def test_programme_carries_no_verdict_colour():
    row = dict(RUNNING, programme=PROG, programme_today=PROG[0]["what"])
    html = calendar_card_html([row])
    for token in ("--up", "--down", "var(--signal", "#22c55e", "#ef4444"):
        assert token not in html
