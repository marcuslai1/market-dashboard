"""The drill-down's Company profile drawer: what the company does, how it makes its money, who buys from it.

Pure HTML-string generation — no Streamlit calls. The cards come from MarketReport's
``company_profiles.json`` (spec 2026-10-05-company-profiles; copied into ``data/`` by
``scripts/company_profiles.py publish``), one facts-only card per company, each written by
one agent and checked by another against the company's filings.

The card is static reference, not the report: every report date shows the same card, and the
drawer says when the card was last checked. Structural colour only — a revenue share is a
proportion, not a verdict, so its bar is neutral ink.
"""
from __future__ import annotations

import re
from datetime import date

from components.watchlist.drilldown_drawers import _drawer
from lib.formatters import _escape_attr, _escape_dollars, _fmt_num, _safe_href


def profiles_by_key(data: dict) -> dict:
    """``{report watchlist key: card}``. The file keys cards by the pipeline ticker
    (``000660.KS``); the report keys its watchlist with non-alphanumerics as ``_``
    (``000660_KS``). ``_meta.aliases`` maps a second listing onto a card (``SKHY``)."""
    if not isinstance(data, dict):
        return {}
    cards = {k: v for k, v in data.items() if not k.startswith("_") and isinstance(v, dict)}
    out = {re.sub(r"[^0-9A-Za-z]", "_", k): v for k, v in cards.items()}
    aliases = (data.get("_meta") or {}).get("aliases") or {}
    for alias, target in aliases.items():
        if target in cards:
            out[re.sub(r"[^0-9A-Za-z]", "_", alias)] = cards[target]
    return out


def _day(iso) -> str:
    """``6 Oct 2026`` from ``YYYY-MM-DD``; anything else verbatim."""
    raw = str(iso or "").strip()
    try:
        d = date.fromisoformat(raw[:10])
    except ValueError:
        return _escape_dollars(raw)
    return f"{d.day} {d:%b} {d.year}"


def _title_attr(text) -> str:
    """An attribute value: quotes escaped, ``$`` neutralised so Streamlit never reads math."""
    return _escape_attr(text).replace("$", "&#36;")


def _src_html(ids, sources: dict) -> str:
    """The source ids a fact rests on, each linked to its document."""
    links = []
    for sid in ids or []:
        s = sources.get(sid)
        if not s:
            continue
        href = _safe_href(s.get("url"))
        label = _escape_dollars(sid)
        links.append(
            f'<a href="{href}" target="_blank" rel="noopener noreferrer" '
            f'title="{_title_attr(s.get("title"))}">{label}</a>' if href else label
        )
    return f' <span class="cp-src">{" ".join(links)}</span>' if links else ""


def _share_rows(parts: list, label_key: str, plain_key: str | None, sources: dict) -> str:
    """Percentage rows with a neutral bar, in the card's own order."""
    rows = []
    for p in parts or []:
        pct = p.get("pct")
        width = max(0.0, min(100.0, float(pct))) if isinstance(pct, (int, float)) else 0.0
        plain = (f'<div class="cp-plain">{_escape_dollars(p.get(plain_key))}</div>'
                 if plain_key and p.get(plain_key) else "")
        rows.append(
            '<div class="cp-share">'
            f'<span class="cp-pct">{_fmt_num(pct, 1)}%</span>'
            '<div class="cp-share-body">'
            f'<div class="cp-name">{_escape_dollars(p.get(label_key))}{_src_html(p.get("src"), sources)}</div>'
            f'<span class="cp-bar"><span style="width:{width:.1f}%"></span></span>'
            f'{plain}</div></div>'
        )
    return "".join(rows)


def _caption(text) -> str:
    return f'<div class="cp-caption">{_escape_dollars(text)}</div>' if text else ""


def _section(title: str) -> str:
    return f'<div class="dd-section">{title}</div>'


def _mix_html(mix: dict, sources: dict) -> str:
    if not isinstance(mix, dict):
        return ""
    head = "Revenue mix" + (f" — {_escape_dollars(mix['period'])}" if mix.get("period") else "")
    total = f"Total {mix['total']}." if mix.get("total") else ""
    caption = " ".join(t for t in (total, mix.get("basis") or "") if t)
    return (_section(head) + _caption(caption)
            + _share_rows(mix.get("segments"), "name", "plain", sources))


def _geo_html(geo, sources: dict) -> str:
    if geo is None:
        return _section("Revenue by region") + _caption("Not disclosed by the company.")
    if not isinstance(geo, dict):
        return ""
    head = "Revenue by region" + (f" — {_escape_dollars(geo['period'])}" if geo.get("period") else "")
    caption = (geo.get("basis") or "")
    return (_section(head) + _caption(caption[:1].upper() + caption[1:])
            + _share_rows(geo.get("regions"), "name", None, sources)
            + (f'<div class="cp-caption">Source{_src_html(geo.get("src"), sources)}</div>'
               if geo.get("src") else ""))


def _customers_html(cust: dict, sources: dict) -> str:
    if not isinstance(cust, dict):
        return ""
    items = []
    for c in cust.get("named") or []:
        share = f' · {_escape_dollars(c["share"])}' if c.get("share") else ""
        status = c.get("status")
        tag = f' <span class="cp-tag">{_escape_dollars(status)}</span>' if status else ""
        items.append(
            f'<div class="cp-item"><b>{_escape_dollars(c.get("who"))}</b>{share}{tag}'
            f'<div class="cp-plain">{_escape_dollars(c.get("what"))}{_src_html(c.get("src"), sources)}</div>'
            '</div>'
        )
    summary = cust.get("summary")
    return (_section("Customers")
            + (f'<div class="dd-line">{_escape_dollars(summary)}{_src_html(cust.get("src"), sources)}</div>'
               if summary else "")
            + "".join(items))


def _competitors_html(comp: dict, sources: dict) -> str:
    """Competitors grouped by where they compete, so one line carries a filing's
    unsplit list instead of repeating the same phrase under every name."""
    if not isinstance(comp, dict) or not comp.get("named"):
        return ""
    groups: dict[str, list[str]] = {}
    for c in comp["named"]:
        groups.setdefault(str(c.get("where") or ""), []).append(str(c.get("who") or ""))
    lines = "".join(
        f'<div class="cp-item"><b>{_escape_dollars(", ".join(names))}</b>'
        + (f'<div class="cp-plain">{_escape_dollars(where[:1].upper() + where[1:])}</div>' if where else "")
        + '</div>'
        for where, names in groups.items()
    )
    basis = comp.get("basis") or ""
    return (_section("Competitors")
            + (f'<div class="cp-caption">{_escape_dollars(basis[:1].upper() + basis[1:])}'
               f'{_src_html(comp.get("src"), sources)}</div>' if basis else "")
            + lines)


def _changes_html(changes, last_checked, sources: dict) -> str:
    """Material changes to the business in the 12 months to the card's check, newest first."""
    head = _section("Changes to the business — last 12 months")
    if not changes:
        return head + _caption(f"None found in the 12 months to {_day(last_checked)}.")
    return head + "".join(
        f'<div class="cp-item"><span class="cp-date">{_day(c.get("date"))}</span>'
        f'{_escape_dollars(c.get("what"))}{_src_html(c.get("src"), sources)}</div>'
        for c in changes if isinstance(c, dict)
    )


def _sources_html(sources: list) -> str:
    rows = []
    for s in sources or []:
        href = _safe_href(s.get("url"))
        title = _escape_dollars(s.get("title"))
        title_html = (f'<a href="{href}" target="_blank" rel="noopener noreferrer">{title}</a>'
                      if href else title)
        kind = s.get("kind")
        rows.append(
            f'<div class="cp-source"><span class="cp-sid">{_escape_dollars(s.get("id"))}</span>'
            f'<span>{title_html} · {_day(s.get("date"))}'
            + (f' · {_escape_dollars(kind)}' if kind else "")
            + '</span></div>'
        )
    return (_section("Sources") + "".join(rows)) if rows else ""


def company_profile_html(card) -> str:
    """The Company profile drawer, or "" when the name has no card."""
    if not isinstance(card, dict) or not card.get("what_they_do"):
        return ""
    srcs = {s.get("id"): s for s in card.get("sources") or [] if isinstance(s, dict)}
    ident = " · ".join(_escape_dollars(x) for x in (card.get("name"), card.get("listing")) if x)
    body = (
        (f'<div class="cp-caption">{ident}</div>' if ident else "")
        + f'<div class="dd-line cp-what">{_escape_dollars(card["what_they_do"])}</div>'
        + _mix_html(card.get("revenue_mix"), srcs)
        + _geo_html(card.get("geography"), srcs)
        + _customers_html(card.get("customers"), srcs)
        + _competitors_html(card.get("competitors"), srcs)
        + _changes_html(card.get("changes"), card.get("last_checked"), srcs)
        + _sources_html(card.get("sources"))
        + '<div class="cp-foot">Facts only, from the company\'s own filings and releases; '
          '<b>reported</b> marks a customer only a secondary source names. '
          f'Facts last changed {_day(card.get("last_changed"))} · '
          f'checked {_day(card.get("last_checked"))}.</div>'
    )
    checked = card.get("last_checked")
    summary = "Company profile" + (f" · checked {_day(checked)}" if checked else "")
    return _drawer(summary, body)
