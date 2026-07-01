"""Shared Plotly styling for the dark editorial theme.

Plotly's default template is white, which clashes hard with the ink-on-dark
broadsheet palette. ``style_fig`` stamps every figure with transparent
backgrounds (so the page paper shows through), mono fonts, and hairline
gridlines that read against ``--paper``. ``PLOTLY_CONFIG`` is passed to every
``st.plotly_chart`` call as ``config=`` (the supported keyword — passing chart
options as bare ``**kwargs`` is deprecated in Streamlit ≥1.49).
"""
from __future__ import annotations

# Mirror of the assets/theme.css tokens used inside chart chrome.
_INK = "#F4EFE2"
_INK3 = "#908A7C"
_RULE = "rgba(255, 255, 255, 0.08)"
_RULE_STRONG = "rgba(255, 255, 255, 0.20)"
_MONO = "JetBrains Mono, ui-monospace, monospace"

# Hide the Plotly modebar — the editorial surface has no use for it.
PLOTLY_CONFIG = {"displayModeBar": False, "responsive": True}

# ── Editorial chart palette ──────────────────────────────────────────────────
# Deliberately distinct from the signal tokens (--buy #22c55e / --caution
# #ef4444 / --watch #f59e0b / --accumulate #3498db) so a chart series never
# reads as a signal, and free of the off-brand magenta/indigo (#ec4899 /#6366f1)
# the Plotly defaults introduced. Muted, mid-luminance tones that sit on --paper.
CHART_ACCENT = "#C9A66B"   # warm brass — primary single-series bars/lines
CHART_MUTED = "#5E5A50"    # ink-4 — de-emphasised / historical / "base" series
CHART_LINE = "#908A7C"     # ink-3 — trend / threshold overlays (7d avg, cutover)
CHART_PALETTE = [
    "#7FA8C9",  # muted steel blue
    "#C9A66B",  # warm brass
    "#8FB08A",  # sage
    "#B58AA6",  # dusty mauve
    "#9A9488",  # warm gray
]

_AXIS = dict(
    gridcolor=_RULE,
    zerolinecolor=_RULE_STRONG,
    linecolor=_RULE_STRONG,
    tickfont=dict(color=_INK3, family=_MONO, size=10),
    title_font=dict(color=_INK3, family=_MONO, size=11),
)


def style_fig(fig, **layout_overrides):
    """Apply the dark editorial look to a Plotly figure in place; return it.

    ``update_layout`` merges recursively, so this preserves any titles, height,
    margins, legend orientation, etc. set by the caller — it only fills in the
    theme (backgrounds, fonts, gridlines). Call it right before
    ``st.plotly_chart``.
    """
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family=_MONO, color=_INK3, size=11),
        legend=dict(font=dict(color=_INK3, family=_MONO, size=10)),
        hoverlabel=dict(font=dict(family=_MONO, color=_INK), bgcolor="#1B1B16"),
        xaxis=_AXIS,
        yaxis=_AXIS,
    )
    if layout_overrides:
        fig.update_layout(**layout_overrides)
    return fig
