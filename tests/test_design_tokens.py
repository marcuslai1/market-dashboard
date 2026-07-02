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


# ── P6-1: components must not carry raw hex literals ──
# The palette pass routed every inline hex through lib/charts constants (or
# SIGNAL_COLORS). terminology.py is the one sanctioned exception — its colors
# live inside a large static HTML/CSS block where f-string conversion would
# fight the CSS braces — so its literals are drift-checked instead.
_COMPONENTS_DIR = Path(__file__).resolve().parent.parent / "components"
_HEX_RE = re.compile(r"#[0-9a-fA-F]{6}\b")


def _sanctioned_palette() -> set:
    import lib.charts as charts

    sanctioned = {v.lower() for v in SIGNAL_COLORS.values()}
    sanctioned |= {
        v.lower()
        for name in dir(charts)
        if isinstance((v := getattr(charts, name)), str) and _HEX_RE.fullmatch(v)
    }
    return sanctioned


def test_no_raw_hex_literals_in_components():
    offenders = []
    for py in _COMPONENTS_DIR.rglob("*.py"):
        if py.name == "terminology.py":
            continue
        for i, line in enumerate(py.read_text(encoding="utf-8").splitlines(), 1):
            if _HEX_RE.search(line):
                offenders.append(f"{py.relative_to(_COMPONENTS_DIR)}:{i}: {line.strip()}")
    assert not offenders, "raw hex literals crept back in:\n" + "\n".join(offenders)


def test_terminology_hex_literals_match_sanctioned_palette():
    """terminology.py keeps inline hexes (static HTML block) — they must stay
    byte-identical to the canonical palette so the reference page can't drift."""
    src = (_COMPONENTS_DIR / "terminology.py").read_text(encoding="utf-8")
    used = {m.group(0).lower() for m in _HEX_RE.finditer(src)}
    assert used, "expected terminology.py to carry its static palette hexes"
    unsanctioned = used - _sanctioned_palette()
    assert not unsanctioned, f"terminology.py colors drifted from the palette: {unsanctioned}"
