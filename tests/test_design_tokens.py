"""Design-system guards: HTML-safety of report text + palette single-source sync.

These lock two things the design layer relied on but never enforced:

1. ``_escape_dollars`` must neutralize HTML metacharacters, not just ``$``.
   Report prose is injected through ``unsafe_allow_html``; a stray ``<`` or
   ``&`` in LLM copy (``"P/E < 15"``, ``"R&D"``) used to break the markup.
2. The signal palette in ``assets/theme.css`` (``--buy`` … ``--caution``) is a
   hand-mirror of the canonical values in ``assets/catalog.json``. This test
   fails the moment the two drift, since there is no build step to sync them.
"""
import re
from pathlib import Path

from lib.catalog import SIGNAL_COLORS, SIGNAL_TINTS
from lib.formatters import _escape_dollars

_THEME_CSS = (Path(__file__).resolve().parent.parent / "assets" / "theme.css").read_text(
    encoding="utf-8"
)


def test_escape_dollars_neutralizes_html_metacharacters():
    """< > & must become entities so prose can't break the injected markup."""
    out = _escape_dollars('P/E < 15 & margins > 20%')
    assert "<" not in out
    assert ">" not in out
    assert "&lt;" in out and "&gt;" in out
    # A bare & becomes &amp; (and must not be left raw to mis-parse as an entity).
    assert "&amp;" in out


def test_escape_dollars_still_neutralizes_dollar_for_latex():
    assert "$" not in _escape_dollars("Target $500")
    assert "&#36;" in _escape_dollars("Target $500")


def test_escape_dollars_does_not_double_escape_its_own_dollar_entity():
    """The $ → &#36; step must run after HTML-escaping, so the & it introduces
    is not itself turned into &amp;#36;."""
    assert _escape_dollars("$") == "&#36;"


def test_escape_dollars_handles_empty_and_none():
    assert _escape_dollars("") == ""
    assert _escape_dollars(None) in (None, "")


def _theme_token(name: str) -> str:
    m = re.search(rf"{re.escape(name)}\s*:\s*([^;]+);", _THEME_CSS)
    assert m, f"{name} not found in theme.css"
    return m.group(1).strip()


def test_theme_signal_colors_match_catalog():
    for sig, var in [
        ("BUY", "--buy"),
        ("ACCUMULATE", "--accumulate"),
        ("WATCH", "--watch"),
        ("HOLD", "--hold"),
        ("CAUTION", "--caution"),
        ("AVOID", "--avoid"),
    ]:
        assert _theme_token(var).lower() == SIGNAL_COLORS[sig].lower(), (
            f"{var} in theme.css drifted from catalog.json {sig}"
        )


def test_theme_signal_tints_match_catalog():
    for sig, var in [
        ("BUY", "--buy-tint"),
        ("ACCUMULATE", "--accumulate-tint"),
        ("WATCH", "--watch-tint"),
        ("HOLD", "--hold-tint"),
        ("CAUTION", "--caution-tint"),
    ]:
        want = SIGNAL_TINTS[sig].replace(" ", "")
        got = _theme_token(var).replace(" ", "")
        assert got == want, f"{var} in theme.css drifted from catalog.json {sig} tint"
