"""Briefing · Daily briefing card, record v2 (MarketReport spec 2026-09-28-briefing-card-v2).

A v2 record is typed items rather than five prose sections: Claude writes the words and
picks the names; ``scripts/briefing.py publish`` joins the numbers (tape, moves, × usual,
volume, % from the 50-day average, RSI, data health, display names) from the day's
morning report into ``latest.numbers``. This module only lays them out.

Reading order: masthead (date, what each number is as of, next timed events) → what
matters → after the data → tape → names that moved (grouped by the market whose session
the price is from) → week ahead → earnings → chart facts → data notes → sources.

Constraints, all upstream decisions:

1. **Information, not advice.** No directional call, no signal label; the log and publish
   steps refuse both. Nothing here adds a judgment.
2. **Colour is a claim.** No hue on any move — a rise is not "good". Hues encode category
   only (macro teal, earnings violet); ``--stress`` marks a real data fault and nothing else.
3. **No rule lines.** Chart facts draw a zero line only; +5 % / +20 % are gate rules.
4. **Searched ≠ not looked up.** "No reported cause found" and the publish-listed names
   nobody looked up render differently.
5. **Server-side only.** Everything is static HTML + ``.bf-`` CSS in assets/theme.css (no
   script), so it survives ``st.markdown(unsafe_allow_html=True)``.
"""
from __future__ import annotations

import datetime as _dt
import re

from components.briefing.market_read import _txt
from lib.cards import card_container
from lib.formatters import _escape_attr

_MARKET_ORDER = ("US", "SGX", "KRX", "Europe")
_MARKET_LABEL = {"US": "US", "SGX": "Singapore", "KRX": "Korea", "Europe": "Europe"}
_KIND_LABEL = {"earnings": "Earnings", "after": "After the data", "move": "Biggest move",
               "macro": "Macro", "check": "Recheck", "data": "Data"}
_BENCH_LABEL = {"SOXX": "SOXX · semis", "US10Y": "US 10-year", "DXY": "Dollar · DXY",
                "WTI": "Oil · WTI", "Gold": "Gold"}
_MINUS = "−"


# ── formatting ───────────────────────────────────────────────────────────────

def _num(x):
    return x if isinstance(x, (int, float)) and not isinstance(x, bool) else None


def _signed(v, nd: int = 2, unit: str = "%") -> str:
    v = _num(v)
    if v is None:
        return "—"
    sign = "+" if v > 0 else (_MINUS if v < 0 else "")
    return f"{sign}{abs(v):.{nd}f}{unit}"


def _x(v) -> str:
    v = _num(v)
    return "" if v is None else f"{v:.1f}×"


def _date(iso: str, fmt: str = "%a %-d %b") -> str:
    try:
        d = _dt.date.fromisoformat(str(iso)[:10])
    except ValueError:
        return _txt(iso)
    return d.strftime(fmt.replace("%-d", str(d.day)))


def _hm(sgt: str) -> str:
    return str(sgt)[11:16]


def _outlet(src: dict) -> str:
    m = re.search(r"\(([^()]+)\)\s*$", str(src.get("title") or ""))
    if m:
        return m.group(1).replace(".com", "")
    host = re.sub(r"^https?://(www\.)?", "", str(src.get("url") or "")).split("/")[0]
    return host.split(".")[-2] if host.count(".") else host or "source"


def _chips(idx, sources: list) -> str:
    out = ""
    for i in idx or []:
        if not isinstance(i, int) or not 0 <= i < len(sources):
            continue
        s = sources[i] if isinstance(sources[i], dict) else {}
        url = str(s.get("url") or "")
        if not url.startswith(("https://", "http://")):
            continue
        date = f' <sup>{_txt(_date(s["date"], "%-d %b"))}</sup>' if s.get("date") else ""
        out += (f'<a class="bf-src" href="{_escape_attr(url)}" target="_blank" rel="noopener noreferrer">'
                f'{_txt(_outlet(s))}{date}</a>')
    return out


def _sec(title: str, body: str, aside: str = "", cls: str = "", prov: str = "") -> str:
    if not body:
        return ""
    aside_html = f'<span class="bf-aside">{_txt(aside)}</span>' if aside else ""
    prov_html = f'<p class="bf-prov">{_txt(prov)}</p>' if prov else ""
    return (f'<section class="bf-sec {cls}"><div class="bf-sh"><h3>{_txt(title)}</h3>{aside_html}</div>'
            f'{body}{prov_html}</section>')


# ── sections ─────────────────────────────────────────────────────────────────

def _masthead(latest: dict, state: str, when: str) -> str:
    date = _date(latest.get("data_date"), "%A %-d %B")
    rows = ""
    for a in latest.get("as_of") or []:
        if not isinstance(a, dict):
            continue
        note = f'<small>{_txt(a["note"])}</small>' if a.get("note") else ""
        rows += f'<div><dt>{_txt(a.get("label"))}</dt><dd>{_txt(a.get("when"))}{note}</dd></div>'
    asof = f'<dl class="bf-asof">{rows}</dl>' if rows else ""
    written = str(latest.get("ts_sgt") or "")[:16].replace("T", " ")
    upcoming = [c for c in latest.get("calendar") or []
                if isinstance(c, dict) and str(c.get("sgt", "")) > written.replace(" ", "T")][:3]
    nxt = ""
    if upcoming:
        nxt = ('<div class="bf-next"><b>Next</b>'
               + "".join(f'<span><strong>{_txt(c.get("what"))}</strong> {_txt(_date(c["sgt"], "%a"))} '
                         f'{_txt(_hm(c["sgt"]))}</span>' for c in upcoming)
               + '<span class="bf-dim">all SGT</span></div>')
    return (f'<section class="bf-sec bf-mast"><div class="bf-mast-top"><h2 class="bf-date">{_txt(date)}</h2>'
            f'<div class="bf-chips">{state}<span class="bf-chip">{_txt(when)}</span></div></div>'
            f'{asof}{nxt}</section>')


def _what_matters(latest: dict, sources: list) -> str:
    items = ""
    for it in latest.get("what_matters") or []:
        if isinstance(it, str):
            it = {"head": it}
        if not isinstance(it, dict) or not it.get("head"):
            continue
        kind = it.get("kind") or ""
        tag = _KIND_LABEL.get(kind, "")
        note = f'<small>{_txt(it.get("tag_note"))}</small>' if it.get("tag_note") else ""
        det = it.get("detail") or ""
        chips = _chips(it.get("src"), sources)
        det_html = f'<span class="bf-det">{_txt(det)} {chips}</span>' if det or chips else ""
        items += (f'<li data-kind="{_escape_attr(kind)}"><span class="bf-tag">{_txt(tag)}{note}</span>'
                  f'<span class="bf-head">{_txt(it["head"])}</span>{det_html}</li>')
    return _sec("What matters", f'<ul class="bf-wm">{items}</ul>' if items else "")


def _after(latest: dict, sources: list) -> str:
    rows = ""
    for it in latest.get("after_data") or []:
        if not isinstance(it, dict) or not it.get("text"):
            continue
        lead = f'<b>{_txt(it["lead"])}</b> ' if it.get("lead") else ""
        rows += f'<li>{lead}{_txt(it["text"])} {_chips(it.get("src"), sources)}</li>'
    if not rows:
        return ""
    return _sec("After the data", f'<div class="bf-box"><ul>{rows}</ul></div>', "since the US close",
                cls="bf-after", prov="Not in the US prices below. Later sessions (SGX, KRX) may already include it.")


def _tape(latest: dict, nums: dict) -> str:
    tiles = ""
    for r in nums.get("tape") or []:
        name = r.get("name", "")
        if r.get("level") is not None:
            val = f'{r["level"]:.2f}%<small>{_signed(r.get("bp"), 0, "bp")}</small>'
        else:
            val = _signed(r.get("chg_pct"))
        usual = f'{_x(r.get("x_usual"))} usual · ' if r.get("x_usual") is not None else ""
        tiles += (f'<div class="bf-tile"><span class="bf-n">{_txt(_BENCH_LABEL.get(name, name))}</span>'
                  f'<span class="bf-v">{val}</span><span class="bf-s">{usual}5d {_signed(r.get("5d_pct"), 1)}</span>'
                  f'</div>')
    if not tiles:
        return ""
    note = f'<p class="bf-cap">{_txt(latest["tape_note"])}</p>' if latest.get("tape_note") else ""
    last = (nums.get("health") or {}).get("last_us_session")
    return _sec("The tape", f'<div class="bf-tape">{tiles}</div>{note}',
                f"US close {_date(last)}" if last else "", prov="Numbers: morning report")


def _movers(latest: dict, nums: dict, sources: list) -> str:
    mv = nums.get("movers") or {}
    groups: dict = {}
    for it in latest.get("movers") or []:
        if isinstance(it, dict) and it.get("key"):
            groups.setdefault((mv.get(it["key"]) or {}).get("market", "US"), []).append(it)
    last = (nums.get("health") or {}).get("last_us_session")
    notes = latest.get("group_notes") if isinstance(latest.get("group_notes"), dict) else {}
    rows = ""
    for market in sorted(groups, key=lambda m: _MARKET_ORDER.index(m) if m in _MARKET_ORDER else 99):
        label = _MARKET_LABEL.get(market, market)
        if market == "US" and last:
            label += f" · {_date(last)} close"
        note = f'<small>{_txt(notes[market])}</small>' if notes.get(market) else ""
        rows += f'<tr class="bf-grp"><th colspan="3" scope="colgroup">{_txt(label)}{note}</th></tr>'
        for it in groups[market]:
            n = mv.get(it["key"]) or {}
            size = _txt(it["size_note"]) if it.get("size_note") else (
                f'{_x(n.get("x_usual"))} usual' if n.get("x_usual") is not None else "")
            vol = f' · vol {n["vol_ratio"]:.2f}×' if _num(n.get("vol_ratio")) is not None else ""
            none = it.get("why_state") == "none_found"
            why = (f'<td class="bf-why{" bf-none" if none else ""}">{_txt(it.get("why"))} '
                   f'{_chips(it.get("src"), sources)}</td>')
            rows += (f'<tr><td class="bf-nm"><b>{_txt(n.get("name") or it["key"])}</b>'
                     f'<span>{_txt(it["key"].split("_")[0])}</span></td>'
                     f'<td class="bf-mv">{_signed(n.get("chg_pct"))}<small>{size}{vol}</small></td>{why}</tr>')
    if not rows:
        return ""
    table = (f'<table class="bf-movers"><thead><tr><th scope="col">Name</th><th scope="col">Move</th>'
             f'<th scope="col">Why</th></tr></thead><tbody>{rows}</tbody></table>')
    also = [a for a in nums.get("also_moved") or [] if isinstance(a, dict)]
    if also:
        bits = " · ".join(
            f'{_txt(a.get("name") or a.get("key"))} {_signed(a.get("chg_pct"))} ({_x(a.get("x_usual"))}'
            + (f', vol {a["vol_ratio"]:.2f}×' if _num(a.get("vol_ratio")) is not None else "") + ")"
            for a in also)
        table += f'<p class="bf-also"><b>Also moved, not looked up:</b> {bits}</p>'
    return _sec("Names that moved", table, "grouped by when the price was taken",
                prov="× usual = the move divided by the name's typical daily swing (one standard deviation "
                     "over recent reports). Moves of 2× or more are always looked up; smaller ones only when "
                     "tied to a tracked catalyst. Prices: morning report.")


def _week(latest: dict) -> str:
    cal = [c for c in latest.get("calendar") or [] if isinstance(c, dict) and c.get("sgt")]
    today = str(latest.get("ts_sgt") or latest.get("data_date") or "")[:10]
    days: dict = {}
    for c in sorted(cal, key=lambda c: c["sgt"]):
        days.setdefault(c["sgt"][:10], []).append(c)
    cols = ""
    if latest.get("tonight") or today in days:
        evs = "".join(_event(c) for c in days.pop(today, []))
        quiet = f'<div class="bf-quiet">{_txt(latest["tonight"])}</div>' if latest.get("tonight") else ""
        cols += (f'<div class="bf-day bf-today"><div class="bf-dh">Tonight<b>{_txt(_date(today))}</b></div>'
                 f'{quiet}{evs}</div>')
    for day, evs in days.items():
        cols += (f'<div class="bf-day"><div class="bf-dh">{_txt(_date(day, "%a"))}'
                 f'<b>{_txt(_date(day, "%-d %b"))}</b></div>{"".join(_event(c) for c in evs)}</div>')
    body = f'<div class="bf-wk">{cols}</div>' if cols else ""
    rchk = [r for r in latest.get("rechecks") or [] if isinstance(r, dict) and r.get("items")]
    if rchk:
        n = sum(len(r["items"]) for r in rchk)
        li = "".join(
            f'<li><time datetime="{_escape_attr(r.get("date"))}">{_txt(_date(r.get("date")))}</time><span>'
            + " · ".join(f'<b>{_txt(i.get("name"))}</b> {_txt(i.get("q"))}' for i in r["items"] if isinstance(i, dict))
            + '</span></li>' for r in rchk)
        body += (f'<details class="bf-rchk"><summary><b>Catalyst rechecks due:</b> {n} item{"s" if n != 1 else ""} '
                 f'across {len(rchk)} date{"s" if len(rchk) != 1 else ""}</summary><ul>{li}</ul></details>')
    if body:
        body += ('<div class="bf-key"><span data-kind="macro">Macro release</span>'
                 '<span data-kind="earnings">Earnings</span></div>')
    return _sec("Week ahead", body, "all times SGT", prov="Calendar: morning report · Rechecks: catalysts.json")


def _event(c: dict) -> str:
    hi = " bf-hi" if c.get("impact") == "high" else ""
    return (f'<div class="bf-ev{hi}" data-kind="{_escape_attr(c.get("kind"))}">'
            f'<time datetime="{_escape_attr(c["sgt"])}+08:00">{_txt(_hm(c["sgt"]))}</time>'
            f'<span>{_txt(c.get("what"))}</span></div>')


def _range_bar(fig: dict, label: str, unit: str, nd: int) -> str:
    vals = [_num(fig.get(k)) for k in ("consensus", "guide_low", "guide_high", "range_low", "range_high")]
    vals = [v for v in vals if v is not None]
    cons = _num(fig.get("consensus"))
    if cons is None or len(vals) < 2:
        return ""
    lo, hi = min(vals), max(vals)
    pad = (hi - lo) * 0.06 or 1
    lo, hi = lo - pad, hi + pad

    def pos(v):
        return f"{(v - lo) / (hi - lo) * 100:.2f}%"

    parts = '<span class="bf-axis"></span>'
    labels = ""
    rl, rh = _num(fig.get("range_low")), _num(fig.get("range_high"))
    if rl is not None and rh is not None:
        parts += f'<span class="bf-range" style="left:{pos(rl)};width:{(rh - rl) / (hi - lo) * 100:.2f}%"></span>'
        labels += (f'<span class="bf-lab bf-bot bf-c" style="left:{pos(rl)}">{rl:.{nd}f}</span>'
                   f'<span class="bf-lab bf-bot bf-r" style="left:{pos(rh)}">{rh:.{nd}f}</span>')
    gl, gh = _num(fig.get("guide_low")), _num(fig.get("guide_high"))
    if gl is not None and gh is not None:
        parts += f'<span class="bf-guide" style="left:{pos(gl)};width:{(gh - gl) / (hi - lo) * 100:.2f}%"></span>'
        labels += (f'<span class="bf-lab bf-bot bf-c" style="left:{pos((gl + gh) / 2)}">'
                   f'guide {gl:.{nd}f}–{gh:.{nd}f}</span>')
    parts += f'<span class="bf-cons" style="left:{pos(cons)}"></span>'
    labels += f'<span class="bf-lab bf-top bf-c" style="left:{pos(cons)}">consensus {cons:.{nd}f}</span>'
    aria = f"{label}: consensus {cons}" + (f", guide {gl} to {gh}" if gl is not None else "") + (
        f", analyst range {rl} to {rh}" if rl is not None else "")
    return (f'<div class="bf-rng"><div class="bf-rlab"><b>{_txt(label)}</b>, {_txt(unit)}</div>'
            f'<div class="bf-rbar" role="img" aria-label="{_escape_attr(aria)}">{parts}{labels}</div></div>')


def _figures(rev: dict) -> str:
    cells = []
    if _num(rev.get("consensus")) is not None:
        an = f'<small>{rev["analysts"]} analysts</small>' if rev.get("analysts") else ""
        cells.append(("Consensus revenue", f'~${rev["consensus"]:.1f}B{an}'))
    gl, gh = _num(rev.get("guide_low")), _num(rev.get("guide_high"))
    if gl is not None and gh is not None:
        cells.append(("Company guide", f'${(gl + gh) / 2:.1f}B ± {(gh - gl) / 2:.1f}<small>its own</small>'))
    rl, rh = _num(rev.get("range_low")), _num(rev.get("range_high"))
    if rl is not None and rh is not None:
        cells.append(("Analyst range", f'${rl:.1f}–{rh:.1f}B<small>low to high</small>'))
    if not cells:
        return ""
    return '<dl class="bf-nums">' + "".join(f'<div><dt>{_txt(k)}</dt><dd>{v}</dd></div>' for k, v in cells) + "</dl>"


def _earnings(latest: dict, nums: dict, sources: list) -> str:
    earn = latest.get("earnings") if isinstance(latest.get("earnings"), dict) else {}
    names = nums.get("names") or {}
    body = ""
    for e in earn.get("coming") or []:
        if not isinstance(e, dict) or not e.get("key"):
            continue
        rev = e.get("revenue") if isinstance(e.get("revenue"), dict) else {}
        eps = e.get("eps") if isinstance(e.get("eps"), dict) else {}
        sgt = str(e.get("when_sgt") or "")
        period = f'<span>{_txt(e["key"])} · {_txt(e.get("period"))}</span>' if e.get("period") else ""
        when_note = f'<small>{_txt(e["when_note"])}</small>' if e.get("when_note") else ""
        facts = f'<p class="bf-facts">{_txt(e["facts"])} {_chips(e.get("src"), sources)}</p>' if e.get("facts") else ""
        body += (f'<div class="bf-ec"><div class="bf-ec-top"><div class="bf-ec-name">'
                 f'{_txt(names.get(e["key"], e["key"]))}{period}</div>'
                 f'<div class="bf-ec-when"><b><time datetime="{_escape_attr(sgt)}+08:00">'
                 f'{_txt(_date(sgt))} · {_txt(_hm(sgt))} SGT</time></b>{when_note}</div></div>'
                 f'{_figures(rev)}{_range_bar(rev, "Revenue", "US$ billions", 1)}'
                 f'{_range_bar(eps, "EPS", "US$", 2)}{facts}</div>')
    out = [e for e in earn.get("out") or [] if isinstance(e, dict) and e.get("text")]
    if out:
        body += '<ul class="bf-out">' + "".join(
            f'<li><b>{_txt(names.get(e.get("key"), e.get("key")))}</b> {_txt(e["text"])} '
            f'{_chips(e.get("src"), sources)}</li>' for e in out) + "</ul>"
    elif body:
        body += '<p class="bf-cap">Reported since the last run: none.</p>'
    if not body and not earn.get("note"):
        return ""
    return _sec("Earnings", body or '<p class="bf-cap">None reported and none due.</p>', "next 14 days",
                prov=earn.get("note") or "")


def _chart(latest: dict, nums: dict) -> str:
    rows = [(k, v) for k, v in (nums.get("chart") or {}).items()
            if isinstance(v, dict) and _num(v.get("vs_sma50_pct")) is not None]
    if not rows:
        return ""
    rows.sort(key=lambda kv: -kv[1]["vs_sma50_pct"])
    vals = [v["vs_sma50_pct"] for _, v in rows]
    lo = min(-10, int((min(vals) - 1) // 10) * 10)
    hi = max(10, -int(-(max(vals) + 1) // 10) * 10)

    def pos(v):
        return (v - lo) / (hi - lo) * 100

    z = pos(0)
    ticks = "".join(
        f'<span style="left:{pos(t):.2f}%{";transform:none" if t == lo else ";transform:translateX(-100%)" if t == hi else ""}">'
        f'{_signed(t, 0) if t else "0"}</span>' for t in range(lo, hi + 1, 10))
    body = (f'<div class="bf-cfhead" aria-hidden="true"><span>Name</span><div class="bf-ax">{ticks}</div>'
            f'<span>RSI</span></div><ul class="bf-cf" aria-label="Distance from the 50-day average">')
    for k, v in rows:
        val = v["vs_sma50_pct"]
        a = pos(val)
        left, width = min(a, z), abs(a - z)
        if val >= 0 and width > 22:
            lab = f'<span class="bf-val bf-in" style="left:{a:.2f}%">{_signed(val, 1)}</span>'
        elif val >= 0:
            lab = f'<span class="bf-val" style="left:{a + 1.5:.2f}%">{_signed(val, 1)}</span>'
        else:
            lab = f'<span class="bf-val" style="left:{z + 1.5:.2f}%">{_signed(val, 1)}</span>'
        rsi = f'{v["rsi"]:.1f}' if _num(v.get("rsi")) is not None else "—"
        body += (f'<li><span class="bf-nm2">{_txt(v.get("name") or k)}</span><div class="bf-bar">'
                 f'<span class="bf-zero" style="left:{z:.2f}%"></span>'
                 f'<span class="bf-b" style="left:{left:.2f}%;width:{max(width, 0.4):.2f}%"></span>{lab}</div>'
                 f'<span class="bf-rsi">{rsi}</span></li>')
    body += "</ul>"
    note = (latest.get("chart_facts") or {}).get("note")
    if note:
        body += f'<p class="bf-cap">{_txt(note)}</p>'
    last = (nums.get("health") or {}).get("last_us_session")
    return _sec("Chart facts", body, "% from the 50-day average" + (f" · {_date(last)}" if last else ""),
                prov="% from the 50-day moving average and RSI: morning report")


def _health(latest: dict, nums: dict) -> str:
    h = nums.get("health") or {}
    chips = []
    if h.get("expected"):
        chips.append(("Coverage", f'{h.get("fetched")}/{h.get("expected")}', h.get("fetched") != h.get("expected")))
    stale = h.get("stale_tickers") or []
    chips.append(("Stale bars", str(len(stale)), bool(stale)))
    chips.append(("Latch", "ON" if h.get("latch_active") else "off", bool(h.get("latch_active"))))
    if h.get("no_new_us_session"):
        chips.append(("US session", "no new session", True))
    if h.get("holes"):
        chips.append(("History holes", str(len(h["holes"])), True))
    faults = sum(f for _, _, f in chips)
    html = '<div class="bf-dn">' + "".join(
        f'<span class="bf-ok{" bf-fault" if f else ""}">{_txt(k)} <b>{_txt(v)}</b></span>' for k, v, f in chips) + "</div>"
    if latest.get("data_notes"):
        html += f'<p class="bf-dntext">{_txt(latest["data_notes"])}</p>'
    return _sec("Data notes", html, "all clear" if not faults else f"{faults} to check")


def _sources(sources: list) -> str:
    li = ""
    for s in sources:
        if not isinstance(s, dict) or not s.get("title"):
            continue
        url = str(s.get("url") or "")
        title = _txt(s["title"])
        if url.startswith(("https://", "http://")):
            title = (f'<a href="{_escape_attr(url)}" target="_blank" rel="noopener noreferrer">{title}</a>')
        date = f'<span class="bf-dim"> · {_txt(_date(s["date"], "%-d %b"))}</span>' if s.get("date") else ""
        li += f"<li>{title}{date}</li>"
    if not li:
        return ""
    return (f'<section class="bf-sec"><details class="bf-srcs"><summary><h3>All sources</h3>'
            f'<span class="bf-aside">{len(sources)} · each is also linked where it is used</span></summary>'
            f'<ol>{li}</ol></details></section>')


def briefing_v2_html(latest: dict, report_date: str | None = None) -> str:
    sources = latest.get("sources") if isinstance(latest.get("sources"), list) else []
    nums = latest.get("numbers") if isinstance(latest.get("numbers"), dict) else {}
    data_date = str(latest.get("data_date") or "")
    stale = bool(report_date and data_date and data_date < str(report_date))
    stale_attr = ' data-stale="1"' if stale else ""
    state = (f'<span class="bf-chip bf-state" data-stale="1">Stale · older than the report on screen '
             f'({_txt(report_date)})</span>' if stale else '<span class="bf-chip bf-state bf-live">Today</span>')
    if latest.get("revises"):
        state += '<span class="bf-chip">Revised</span>'
    when = f"Written {str(latest.get('ts_sgt') or '')[11:16]} SGT" if latest.get("ts_sgt") else "undated"
    body = (
        _masthead(latest, state, when)
        + _what_matters(latest, sources)
        + _after(latest, sources)
        + _tape(latest, nums)
        + _movers(latest, nums, sources)
        + _week(latest)
        + _earnings(latest, nums, sources)
        + _chart(latest, nums)
        + _health(latest, nums)
        + _sources(sources)
        + '<div class="bf-foot">Information, not advice: no directional call and no signal labels. Written by '
          'Claude in the terminal from the day’s data; every load-bearing fact carries a source. Published '
          'briefings are never edited — a correction is a new, revised entry.</div>'
    )
    return card_container(
        eyebrow="DAILY BRIEFING",
        headline="",
        body_html=f'<div class="bf"{stale_attr}>{body}</div>',
        lane="lede",
    )
