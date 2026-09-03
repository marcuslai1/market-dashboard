"""Layout of the catalysts card (upstream CAL-01 classes, chronological render).

The pipeline ships three classes — this-week, forward catalysts, and
read-across prints by companies the book does NOT hold. The card renders TWO
sections (this-week, then muted Forward Catalysts below a hairline) and
interleaves read-across rows by date with a NOT HELD chip (2026-09-03; they
used to have a third section below the forward horizon, which put a print 8
days out under one 6 weeks out). The this-week partition is still an explicit
allow-list on type, so an untyped legacy row reads as this-week and nothing
else does.
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
READ_ACROSS_FAR = dict(READ_ACROSS, date="2026-10-01", event="Oracle Earnings")


def _split(html: str) -> tuple[str, str]:
    """(above the Forward Catalysts hairline, below it)."""
    if "Forward Catalysts" not in html:
        return html, ""
    lead, fwd = html.split("Forward Catalysts", 1)
    return lead, fwd


def test_read_across_before_the_horizon_sits_in_date_order_up_top():
    html = calendar_card_html([THIS_WEEK, FORWARD, READ_ACROSS])
    lead, fwd = _split(html)
    assert "DBS Earnings" in lead and "Applied Materials" in lead
    assert "Micron Earnings" in fwd and "Applied Materials" not in fwd
    # Chronological within the top group: Aug 14 before Aug 18
    assert lead.index("DBS Earnings") < lead.index("Applied Materials")


def test_read_across_after_the_horizon_sits_below_the_hairline():
    html = calendar_card_html([THIS_WEEK, FORWARD, READ_ACROSS_FAR])
    lead, fwd = _split(html)
    assert "Oracle Earnings" not in lead
    assert "Oracle Earnings" in fwd
    assert fwd.index("Micron Earnings") < fwd.index("Oracle Earnings")


def test_no_separate_read_across_section():
    html = calendar_card_html([THIS_WEEK, FORWARD, READ_ACROSS])
    assert "Read-Across" not in html


def test_read_across_row_shows_why_and_affected_tickers():
    """The rationale and the affected holdings are the row's entire claim on a
    slot in a card about the reader's own book."""
    html = calendar_card_html([READ_ACROSS])
    assert "Deposition orders lead foundry capex by a quarter." in html
    assert "cal-why" in html
    assert "ASML" in html and "TSM" in html


def test_read_across_row_carries_not_held_chip():
    html = calendar_card_html([THIS_WEEK, READ_ACROSS])
    assert html.count("cal-notheld") == 1
    assert "NOT HELD" in html
    # The chip belongs to the read-across row, not the holding's row
    assert html.index("DBS Earnings") < html.index("cal-notheld") \
        < html.index("Applied Materials") + 200


def test_holdings_rows_carry_no_chip():
    assert "cal-notheld" not in calendar_card_html([THIS_WEEK, FORWARD])


def test_read_across_rows_are_not_muted_even_below_the_hairline():
    """Muting would conflate 'far away' with 'not yours' — the chip says the
    latter, so a read-across row keeps full ink wherever it lands."""
    html = calendar_card_html([FORWARD, READ_ACROSS_FAR])
    _, fwd = _split(html)
    micron = fwd.split("Micron Earnings", 1)[0]
    oracle = fwd.split("Micron Earnings", 1)[1].split("Oracle Earnings", 1)[0]
    assert "opacity:0.72" in micron
    assert "opacity:0.72" not in oracle


def test_forward_section_stays_muted():
    html = calendar_card_html([FORWARD])
    assert "opacity:0.72" in html


def test_read_across_alone_renders_up_top_unmuted():
    html = calendar_card_html([READ_ACROSS])
    assert "Forward Catalysts" not in html
    assert "opacity:0.72" not in html
    assert "NOT HELD" in html


def test_forward_section_absent_when_class_is_absent():
    html = calendar_card_html([THIS_WEEK])
    assert "Forward Catalysts" not in html


def test_untyped_events_still_read_as_this_week():
    """Legacy reports predate the `type` field entirely."""
    html = calendar_card_html([{"date": "2026-08-14", "event": "CPI Report",
                                "impact": "HIGH"}])
    assert "CPI Report" in html
    assert "Forward Catalysts" not in html and "cal-notheld" not in html


def test_eyebrow_does_not_promise_a_week():
    """The card routinely lists events six weeks out; the old THE WEEK AHEAD
    eyebrow contradicted its own body."""
    for events in ([], [THIS_WEEK, FORWARD]):
        html = calendar_card_html(events)
        assert "THE WEEK AHEAD" not in html
        assert "WHAT'S COMING" in html


def test_why_line_absent_for_ordinary_events():
    assert "cal-why" not in calendar_card_html([THIS_WEEK, FORWARD])
