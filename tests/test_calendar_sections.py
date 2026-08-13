"""Section partitioning in the catalysts card (upstream CAL-01).

The card renders three classes below their own hairlines — this-week, forward
catalysts, and read-across prints by companies the book does NOT hold. The
partition has to be an explicit allow-list: the previous "anything that isn't
forward_catalyst is this-week" rule would have swept read-across rows straight
into the reader's own week.
"""
from components.briefing.calendar import calendar_card_html

THIS_WEEK = {"date": "2026-08-14", "event": "DBS Earnings", "impact": "HIGH",
             "type": "this_week"}
FORWARD = {"date": "2026-09-23", "event": "Micron Earnings", "impact": "MEDIUM",
           "type": "forward_catalyst"}
READ_ACROSS = {
    "date": "2026-08-18", "event": "Applied Materials Earnings",
    "impact": "MEDIUM", "type": "read_across",
    "tickers_affected": ["ASML", "TSM"],
    "why": "Deposition orders lead foundry capex by a quarter.",
}


def _section(html: str, label: str) -> str:
    """Body text after ``label``'s sub-head, up to the next sub-head."""
    tail = html.split(label, 1)[1]
    for nxt in ("Forward Catalysts", "Read-Across"):
        if nxt in tail:
            tail = tail.split(nxt, 1)[0]
    return tail


def test_read_across_is_not_swept_into_this_week():
    html = calendar_card_html([THIS_WEEK, READ_ACROSS])
    assert "Read-Across" in html
    # The this-week block is everything before the first sub-head
    lead = html.split("Read-Across", 1)[0]
    assert "DBS Earnings" in lead
    assert "Applied Materials" not in lead


def test_three_sections_each_hold_only_their_own_class():
    html = calendar_card_html([THIS_WEEK, FORWARD, READ_ACROSS])
    lead = html.split("Forward Catalysts", 1)[0]
    assert "DBS Earnings" in lead
    fwd = _section(html, "Forward Catalysts")
    assert "Micron Earnings" in fwd and "Applied Materials" not in fwd
    ra = _section(html, "Read-Across")
    assert "Applied Materials" in ra and "Micron Earnings" not in ra


def test_read_across_row_shows_why_and_affected_tickers():
    """The rationale and the affected holdings are the row's entire claim on a
    slot in a card about the reader's own book."""
    html = calendar_card_html([READ_ACROSS])
    assert "Deposition orders lead foundry capex by a quarter." in html
    assert "cal-why" in html
    assert "ASML" in html and "TSM" in html


def test_read_across_label_says_not_held():
    html = calendar_card_html([READ_ACROSS])
    assert "not held" in html


def test_read_across_rows_are_not_muted():
    """Muting would conflate 'far away' with 'not yours' — these are near-term."""
    html = calendar_card_html([READ_ACROSS])
    ra = _section(html, "Read-Across")
    assert "opacity:0.72" not in ra


def test_forward_section_stays_muted():
    html = calendar_card_html([FORWARD])
    assert "opacity:0.72" in html


def test_sections_absent_when_their_class_is_absent():
    html = calendar_card_html([THIS_WEEK])
    assert "Forward Catalysts" not in html
    assert "Read-Across" not in html


def test_untyped_events_still_read_as_this_week():
    """Legacy reports predate the `type` field entirely."""
    html = calendar_card_html([{"date": "2026-08-14", "event": "CPI Report",
                                "impact": "HIGH"}])
    assert "CPI Report" in html
    assert "Forward Catalysts" not in html and "Read-Across" not in html


def test_eyebrow_does_not_promise_a_week():
    """The card routinely lists events six weeks out; the old THE WEEK AHEAD
    eyebrow contradicted its own body."""
    for events in ([], [THIS_WEEK, FORWARD]):
        html = calendar_card_html(events)
        assert "THE WEEK AHEAD" not in html
        assert "WHAT'S COMING" in html


def test_why_line_absent_for_ordinary_events():
    assert "cal-why" not in calendar_card_html([THIS_WEEK, FORWARD])
