"""Design-system guards: HTML-safety of report text + palette single-source sync.

These lock two things the design layer relied on but never enforced:

1. ``_escape_dollars`` must neutralize HTML metacharacters, not just ``$``.
   Report prose is injected through ``unsafe_allow_html``; a stray ``<`` or
   ``&`` in LLM copy (``"P/E < 15"``, ``"R&D"``) used to break the markup.
2. The tone palette in ``assets/theme.css`` (``--tone-pos`` … ``--tone-neg-deep``)
   is a hand-mirror of the canonical values in ``assets/catalog.json``. This test
   fails the moment the two drift, since there is no build step to sync them.
   (The tones were the signal palette until the labels left on 2026-10-01; the
   colours stayed under neutral role names.)
"""
import re
from pathlib import Path

from lib.catalog import TONE_COLORS, TONE_TINTS
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


_TONE_VARS = {
    "pos": "--tone-pos", "info": "--tone-info", "warn": "--tone-warn",
    "muted": "--tone-muted", "neg": "--tone-neg", "neg_deep": "--tone-neg-deep",
}


def test_theme_tone_colors_match_catalog():
    for tone, var in _TONE_VARS.items():
        assert _theme_token(var).lower() == TONE_COLORS[tone].lower(), (
            f"{var} in theme.css drifted from catalog.json tones.{tone}"
        )


def test_theme_tone_tints_match_catalog():
    # neg_deep is excluded on purpose: its CSS tint (0.16) and catalog tint (0.20)
    # already differed when it was the AVOID tint, and nothing paints with it.
    for tone in ("pos", "info", "warn", "muted", "neg"):
        want = TONE_TINTS[tone].replace(" ", "")
        got = _theme_token(f"{_TONE_VARS[tone]}-tint").replace(" ", "")
        assert got == want, f"{_TONE_VARS[tone]}-tint drifted from catalog.json"


def test_no_signal_named_token_or_selector_survives():
    """The labels left the site on 2026-10-01: no CSS token is named after a
    signal and no rule keys on a row's signal."""
    import re as _re

    assert not _re.search(r"--(buy|accumulate|watch|hold|caution|avoid)(?![a-z])", _THEME_CSS)
    assert "data-signal" not in _THEME_CSS
    assert "sig-pill" not in _THEME_CSS


# ── P6-1: components must not carry raw hex literals ──
# The palette pass routed every inline hex through lib/charts constants (or
# SIGNAL_COLORS). terminology.py used to be the one sanctioned exception — its
# colors sat inside a large static HTML/CSS block where f-string conversion
# would have fought the CSS braces. The 2026-07-25 redesign moved that block's
# CSS into theme.css and its pills onto _signal_pill_html, so the exemption is
# gone and the rule is now universal.
_COMPONENTS_DIR = Path(__file__).resolve().parent.parent / "components"
_HEX_RE = re.compile(r"#[0-9a-fA-F]{6}\b")


def _sanctioned_palette() -> set:
    import lib.charts as charts

    sanctioned = {v.lower() for v in TONE_COLORS.values()}
    sanctioned |= {
        v.lower()
        for name in dir(charts)
        if isinstance((v := getattr(charts, name)), str) and _HEX_RE.fullmatch(v)
    }
    return sanctioned


def test_no_raw_hex_literals_in_components():
    offenders = []
    for py in _COMPONENTS_DIR.rglob("*.py"):
        for i, line in enumerate(py.read_text(encoding="utf-8").splitlines(), 1):
            if _HEX_RE.search(line):
                offenders.append(f"{py.relative_to(_COMPONENTS_DIR)}:{i}: {line.strip()}")
    assert not offenders, "raw hex literals crept back in:\n" + "\n".join(offenders)


def test_metric_family_tokens_match_the_chart_map():
    """The Pipeline page paints its five hues from CSS (cells, rails, swatches)
    and from Plotly (the cost bars). Two sources for one palette is a drift
    risk, so they are asserted equal — the CSS dark value is the canonical one
    because that is the theme the app actually ships."""
    from lib.charts import METRIC_COLORS

    for key, want in METRIC_COLORS.items():
        got = _theme_token(f"--metric-{key}-dark")
        assert got.lower() == want.lower(), (
            f"--metric-{key}-dark is {got} but lib.charts says {want}"
        )
    # Every hue also needs a light sibling, like every other token in the file.
    for key in METRIC_COLORS:
        assert _theme_token(f"--metric-{key}-light")


def test_metric_palette_avoids_the_reserved_hues():
    """The metric palette is only legal because it cannot be mistaken for a
    signal rating or a price move. If a metric hue ever collides with one of
    those, that argument collapses."""
    from lib.charts import METRIC_COLORS, STATUS_NEG, STATUS_POS, STATUS_WARN

    reserved = {c.lower() for c in TONE_COLORS.values()}
    reserved |= {STATUS_POS.lower(), STATUS_NEG.lower(), STATUS_WARN.lower()}
    clash = {k: v for k, v in METRIC_COLORS.items() if v.lower() in reserved}
    assert not clash, f"metric hues collide with a reserved palette: {clash}"


# ── Shared devices ──

def test_hairline_grid_device_is_single_sourced():
    """The FRED prints grid declares the shared hairline-grid device (the
    Tracker's tiles used it too until 2026-10-01), so 'a grid of cells' always
    means 'peer measurements, compare across'."""
    assert ".hair-grid, .fp-grid" in _THEME_CSS
    assert ".hair-grid > *, .fp-cell" in _THEME_CSS


def test_masthead_section_head_is_the_two_px_rule():
    block = _THEME_CSS.split(".section-head.masthead {", 1)[1].split("}", 1)[0]
    assert "border-bottom: 2px solid var(--color-text)" in block
