"""Briefing · shared section primitives for the daily briefing card.

Accented sub-panels, bullet lists, collapsed drawers and source links. They came from
the market-read card (EXPERIMENTAL, 2026-09-09), which was removed on 2026-10-03 when
MarketReport retired the `/market-read` skill at its 20-session exit review
(MarketReport PIPELINE_FEATURES §121); the daily briefing card kept using them, so they
moved here verbatim. The CSS keeps the ``.mr-`` class names from that card. That CSS
carries structural colour only — no verdict hue — pinned by
``tests/test_briefing_sections.py``.
"""
from __future__ import annotations

from lib.formatters import _escape_attr, _escape_dollars


def _txt(s) -> str:
    """Escape prose for the card; markdown emphasis from the reply is dropped."""
    return _escape_dollars(str(s or "").replace("**", ""))


def _section(kind: str, label: str, inner: str, aside: str = "") -> str:
    """One accented sub-panel. ``kind`` picks the structural hue in CSS."""
    return (
        f'<div class="mr-sec" data-sec="{_escape_attr(kind)}">'
        f'<div class="mr-sec-lab">{_txt(label)}{aside}</div>'
        f'{inner}</div>'
    )


def _bullets(items: list, limit: int) -> str:
    rows = "".join(f"<li>{_txt(i)}</li>" for i in (items or [])[:limit] if i)
    return f'<ul class="mr-list">{rows}</ul>' if rows else ""


def _list_block(kind: str, label: str, items: list, limit: int) -> str:
    """A labelled bullet-list section, or ``""`` when there is nothing to show."""
    body = _bullets(items, limit)
    return _section(kind, label, body) if body else ""


def _drawer(kind: str, label: str, inner: str, count: int | None = None) -> str:
    """A collapsed sub-panel — secondary material one click away, not a wall."""
    if not inner:
        return ""
    badge = f'<span class="mr-count">{count}</span>' if count else ""
    return (
        f'<details class="mr-sec mr-drawer" data-sec="{_escape_attr(kind)}">'
        f'<summary class="mr-sec-lab">{_txt(label)}{badge}</summary>{inner}</details>'
    )


def _source_links(sources: list, limit: int = 8) -> str:
    rows = ""
    for src in (sources or [])[:limit]:
        if not isinstance(src, dict) or not src.get("title"):
            continue
        url = str(src.get("url") or "")
        title = _txt(src["title"])
        if url.startswith(("https://", "http://")):
            title = (f'<a class="mr-link" href="{_escape_attr(url)}" target="_blank" '
                     f'rel="noopener noreferrer">{title}</a>')
        date = f' <span class="mr-date">{_txt(src["date"])}</span>' if src.get("date") else ""
        rows += f"<li>{title}{date}</li>"
    return f'<ul class="mr-list">{rows}</ul>' if rows else ""
