"""Watchlist grid builders — pure HTML, no Streamlit.

Everything the dense grid needs except the row itself: the filter chips' option
set, the filter and grouping logic, the column header, the group headers, the
single wrapper blob, and the two pieces of footnote copy.

Two constructions here are load-bearing and easy to break:

1. **One blob.** The column header, every group header and every row are emitted
   in ONE string, because a ``<div>`` opened in one ``st.markdown`` and closed in
   another does not wrap sibling Streamlit blocks — the browser auto-closes it,
   and ``.tk-scroll`` stops containing the rows.
2. **Python-side filtering.** Rows are filtered *before* rendering rather than
   hidden with CSS, so a filtered view never leaves an empty group header behind
   and every header's count is the honest count within that filter.
"""
from __future__ import annotations

from collections.abc import Callable

from lib.catalog import SIGNAL_COLORS, SIGNAL_SORT_RANK

FILTER_ALL = "all"
FILTER_CHANGED = "changed"

#: (label, alignment). Order is the grid's own.
#: Signal sits second because it is the row's verdict — you should never read
#: four numbers before learning what the call is. The gauge column centres,
#: because its bar is centred on zero.
_COLUMNS: list[tuple[str, str]] = [
    ("Ticker", "left"),
    ("Signal", "left"),
    ("Last · Δ", "right"),
    ("1 mo", "right"),
    ("vs 50-day", "center"),
    ("RSI", "right"),
    ("R:R", "right"),
]

_RANK_LAST = len(SIGNAL_SORT_RANK)


def _signal_of(d: dict) -> str:
    return d.get("signal", "HOLD")


def _signals_present(items) -> list[str]:
    """Signals actually in this book, in rank order."""
    seen = {_signal_of(d) for _, d in items}
    return sorted(seen, key=lambda s: SIGNAL_SORT_RANK.get(s, _RANK_LAST))


def build_filter_options(items, changed_tickers) -> tuple[list[str], dict[str, str]]:
    """``(keys, labels)`` for the Show chips.

    The counts are themselves information — the bar doubles as the "shape of the
    book" readout the Briefing's signal-count grid used to provide — so they are
    derived from the data every run. A day with only CAUTION names shows two
    chips; a day with nothing changed shows no Changed chip at all rather than a
    dead ``· 0``.
    """
    # Intersect with the rendered book: a retired name whose signal moved must
    # not inflate a count for a chip that can never show it.
    changed = {tk for tk, _ in items if tk in (changed_tickers or set())}
    keys: list[str] = [FILTER_ALL]
    labels: dict[str, str] = {FILTER_ALL: f"All · {len(items)}"}
    if changed:
        keys.append(FILTER_CHANGED)
        # The leading ● mirrors the row marker, so the connection needs no legend.
        labels[FILTER_CHANGED] = f"● Changed · {len(changed)}"
    for sig in _signals_present(items):
        n = sum(1 for _, d in items if _signal_of(d) == sig)
        keys.append(sig)
        labels[sig] = f"{sig.title()} · {n}"
    return keys, labels


def filter_items(items, changed_tickers, selected):
    """Apply one chip.

    Anything unrecognised — including the ``None`` a chip clicked off returns —
    falls back to the whole book.

    A signal is only honoured when it is actually present. Yesterday's selection
    survives in session state, so a reader who filtered to BUY on a day that had
    BUY names would otherwise land on an empty page today; the whole book is the
    better answer than a blank one.
    """
    if selected == FILTER_CHANGED:
        changed = changed_tickers or set()
        return [(tk, d) for tk, d in items if tk in changed]
    if selected in _signals_present(items):
        return [(tk, d) for tk, d in items if _signal_of(d) == selected]
    return list(items)


def group_items(items):
    """``[(signal, rows), …]`` in rank order, preserving each group's row order.

    A sort is only legible if you already know the rank order. Explicit groups
    with counts make the ordering self-documenting, let a reader skip 21 CAUTION
    names outright, and give the eye rest points in a long scroll.
    """
    out: list[tuple[str, list]] = []
    for sig in _signals_present(items):
        rows = [(tk, d) for tk, d in items if _signal_of(d) == sig]
        if rows:
            out.append((sig, rows))
    return out


def column_header_html() -> str:
    """The column labels.

    Two rule weights, on purpose (see ``.tk-row.tk-head`` in theme.css): a
    strong top rule opens the data zone, a faint bottom rule only separates
    labels from rows.
    """
    cells = "".join(
        f'<div role="columnheader" class="tk-h-{align}">{label}</div>'
        for label, align in _COLUMNS
    )
    return f'<div class="tk-row tk-head" role="row">{cells}</div>'


def group_header_html(signal: str, count: int) -> str:
    """Dot + name + count + a hairline that fills the rest of the width.

    11px uppercase, not a real heading size: these are dividers inside ONE table,
    not sections of a document — sizing them up would fragment the page into
    three tables. The dot and name take the signal palette because the group *is*
    a signal; this is the only coloured text at heading scale on the page.
    """
    # An unrecognised signal falls back to metadata grey, not to a borrowed
    # signal hue — a group whose rating we can't name must not look like one.
    color = SIGNAL_COLORS.get(signal, "var(--color-text-3)")
    return (
        f'<div class="tk-group" style="--sig:{color};" role="row">'
        f'<span class="tk-group-dot"></span>'
        f'<span class="tk-group-name">{signal}</span>'
        f'<span class="tk-group-count">{count}</span>'
        f'<span class="tk-group-rule"></span>'
        f'</div>'
    )


def build_grid_html(
    items,
    changed_tickers,
    earnings_map: dict,
    row_builder: Callable[..., str],
) -> str:
    """The whole table as one string: wrapper, column header, groups, rows."""
    changed = changed_tickers or set()
    parts = [column_header_html()]
    for sig, rows in group_items(items):
        parts.append(group_header_html(sig, len(rows)))
        parts.extend(
            row_builder(
                tk,
                d,
                signal_changed=(tk in changed),
                earnings_hist=(earnings_map or {}).get(tk),
            )
            for tk, d in rows
        )
    return (
        '<div class="tk-scroll" role="table" '
        'aria-label="Watchlist — click a row to expand">'
        f'{"".join(parts)}</div>'
    )


def method_note_html() -> str:
    """The three pieces of encoding a reader cannot infer from looking.

    Bolding is by what breaks comprehension if missed, never by keyword
    importance — which is exactly why the bold count is three and no more.
    """
    return (
        '<div class="tk-method">'
        'Extension is measured against the 50-day average, and the pipeline '
        'blocks entries past <b>±10%</b> — the point where the gauge turns '
        'terracotta. <b>R:R is the tight-stop-corrected ratio</b>, the same '
        'figure the writeup cites, not the raw headline. RSI turns terracotta '
        'past <b>70 and 30</b>, the overbought and oversold thresholds.'
        '</div>'
    )


def footer_html(n_shown: int, n_total: int) -> str:
    """The page's own legend, placed where a confused reader would look."""
    return (
        '<div class="tk-foot">'
        f'Showing {n_shown} of {n_total} names · '
        '<span class="tk-changed tk-changed-legend"></span> '
        'a steel dot marks a signal that changed since the prior report.'
        '</div>'
    )
