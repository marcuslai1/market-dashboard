"""The Watchlist extension gauge — the page's one visual.

``vs 50-day`` is the mechanical block criterion: the pipeline refuses entries on
names too far extended above the average. Every other column on the grid is an
input to judgment; this one is a rule. A signed number makes the reader compare
+14.3% against a threshold they have to remember; a centred bar makes "too far
right" a shape.

Design decisions worth not re-litigating (spec 2026-07-25 §8):

* **Centred, not left-anchored.** The quantity is signed and zero is meaningful
  — the 50-day *is* the reference. A left-anchored bar would imply a magnitude
  scale where "small" is the left end, which is wrong: below the average is the
  interesting other direction.
* **One fixed scale for every row.** A per-row scale would make the bars
  incomparable, which is the only reason to draw them at all.
* **Clamping is accepted.** −17.5% and a hypothetical −40% look identical. Past
  the threshold, how far past stops changing the decision — and the exact value
  is printed beneath regardless, so nothing is hidden.
* **Brass then terracotta, never green/red.** A green/red gauge would read as
  "good/bad", which is wrong in both directions: −17.5% is not "bad", it is "not
  extended, but broken". Brass is the data axis; terracotta marks the crossing.
  Neither is a signal colour — critical, because the gauge sits three columns
  from the signal pill and the two must not be confused.

Plain divs rather than an SVG: it is two rectangles and a rule.
"""
from __future__ import annotations

from lib.formatters import _delta_class, _fmt_num, _sign

#: Full-scale extension, in percent. Bars clamp here.
EXT_MAX = 20.0
#: Where the pipeline's entry block bites — the brass → terracotta switch.
EXT_THRESHOLD = 10.0


def extension_gauge_html(vs50: float | None) -> str:
    """One row's extension gauge: track, zero line, fill, signed number.

    ``None`` renders a bare em-dash with no track — never "—%", the absent-value
    bug guarded by ``tests/test_watchlist_row.py``.
    """
    if vs50 is None:
        return '<div class="tk-ext tk-ext-empty">—</div>'
    frac = min(abs(vs50), EXT_MAX) / EXT_MAX
    # Half the track is one side of zero, so full scale is a 50% fill.
    width = frac * 50.0
    side = "left" if vs50 > 0 else "right"
    tone = "over" if abs(vs50) >= EXT_THRESHOLD else "under"
    return (
        '<div class="tk-ext">'
        '<div class="tk-ext-track">'
        '<div class="tk-ext-zero"></div>'
        f'<div class="tk-ext-fill" data-tone="{tone}" '
        f'style="{side}:50%;width:{width:.2f}%;"></div>'
        '</div>'
        f'<div class="tk-ext-num {_delta_class(vs50)}">'
        f'{_sign(vs50)}{_fmt_num(vs50, 1)}%</div>'
        '</div>'
    )
