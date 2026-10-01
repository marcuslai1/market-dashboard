"""The Watchlist "vs 50-day" gauge — the page's one visual.

The distance from the 50-day average, drawn as a bar centred on zero, with the
signed figure beneath. A fact about where the price sits, not a rule: the gauge
used to turn terracotta at ±10 % — the point where the pipeline's entry block
bit — and its number wore the up/down palette. Both went on 2026-10-01 with the
labels (MarketReport spec 2026-10-01-info-only-watchlist §8; tag
``pre-label-removal``): one neutral fill, an uncoloured number.

Design decisions worth not re-litigating (spec 2026-07-25 §8):

* **Centred, not left-anchored.** The quantity is signed and zero is meaningful
  — the 50-day *is* the reference. A left-anchored bar would imply a magnitude
  scale where "small" is the left end, which is wrong: below the average is the
  interesting other direction.
* **One fixed scale for every row.** A per-row scale would make the bars
  incomparable, which is the only reason to draw them at all.
* **Clamping is accepted.** −17.5% and a hypothetical −40% look identical; the
  exact value is printed beneath regardless, so nothing is hidden.

Plain divs rather than an SVG: it is two rectangles and a rule.
"""
from __future__ import annotations

from lib.formatters import _fmt_num, _sign

#: Full-scale distance, in percent. Bars clamp here.
EXT_MAX = 20.0


def extension_gauge_html(vs50: float | None) -> str:
    """One row's gauge: track, zero line, fill, signed number.

    ``None`` renders a bare em-dash with no track — never "—%", the absent-value
    bug guarded by ``tests/test_watchlist_row.py``.
    """
    if vs50 is None:
        return '<div class="tk-ext tk-ext-empty">—</div>'
    frac = min(abs(vs50), EXT_MAX) / EXT_MAX
    # Half the track is one side of zero, so full scale is a 50% fill.
    width = frac * 50.0
    side = "left" if vs50 > 0 else "right"
    return (
        '<div class="tk-ext">'
        '<div class="tk-ext-track">'
        '<div class="tk-ext-zero"></div>'
        f'<div class="tk-ext-fill" style="{side}:50%;width:{width:.2f}%;"></div>'
        '</div>'
        f'<div class="tk-ext-num">{_sign(vs50)}{_fmt_num(vs50, 1)}%</div>'
        '</div>'
    )
