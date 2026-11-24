"""Briefing · Daily briefing card, record v2 (MarketReport spec 2026-09-28-briefing-card-v2).

A v2 record is typed items rather than five prose sections: Claude writes the words and
picks the names; ``scripts/briefing.py publish`` joins the numbers (tape, moves, × usual,
volume, % from the 50-day average, RSI, data health, display names) from the day's
morning report into ``latest.numbers``. This module only lays them out.

Reading order: masthead (date, what each number is as of, next timed events) → what
matters → after the data → markets → names that moved (grouped by the market whose session
the price is from) → week ahead → earnings → further out (dates only, to two months; the
second month under a "less certain" label) → chart facts → data notes → sources. On a PC
the four "today" sections and the three "coming" sections sit in two columns
(``bf-cols``, layout review 2026-11-24); the order in the markup is the same.

Constraints, all upstream decisions:

1. **Information, not advice.** No directional call, no signal label; the log and publish
   steps refuse both. Nothing here adds a judgment.
2. **Colour is a claim.** Hues encode the kind of item (``data-kind``: macro teal, earnings
   violet, after-the-data brass, price data from the report indigo; rechecks and data
   notes stay ink); ``--stress`` marks a real data fault and nothing else. Since
   2026-11-24 (owner) a figure that is the percentage move of a price takes the
   Watchlist's up / down pair (``_dir``: ``bf-up`` / ``bf-down``): the direction of a
   move, never a verdict. It was one ink for every move until then, and a 10.55% fall
   looked like a 0.09% one. In Markets only the rows in ``_PRICE_TILES`` take it (three
   funds, oil, gold): the VIX, the 10-year yield and the two dollar rows stay ink, so a
   jump in the VIX is never green. The 5-day and 1-month figures, the chart facts and
   every sentence stay as they were.
3. **No rule lines.** Chart facts draw a zero line only; +5 % / +20 % are gate rules.
4. **Searched ≠ not looked up.** "No reported cause found" and the publish-listed names
   nobody looked up render differently.
5. **Server-side only.** Everything is static HTML + ``.bf-`` CSS in assets/theme.css (no
   script), so it survives ``st.markdown(unsafe_allow_html=True)``.
"""
from __future__ import annotations

import datetime as _dt
import math
import re

from components.briefing.sections import _txt
from components.earnings_chart import (
    block_html,
    eps_chart_html,
    eps_currency,
    quarter_series,
    revenue_chart_html,
    revenue_currency,
)
from lib.cards import card_container
from lib.formatters import _escape_attr

_MARKET_ORDER = ("US", "SGX", "KRX", "Europe")
_MARKET_LABEL = {"US": "US", "SGX": "Singapore", "KRX": "Korea", "Europe": "Europe"}
_KIND_LABEL = {"earnings": "Earnings", "after": "After the data", "move": "Biggest move",
               "macro": "Macro", "check": "Recheck", "data": "Data"}
_BENCH_LABEL = {"SOXX": "SOXX · semis", "US10Y": "US 10-year", "DXY": "Dollar · DXY",
                "USDSGD": "US$ vs S$ · USD/SGD", "WTI": "Oil · WTI", "Gold": "Gold"}
_MINUS = "−"
# Tiles whose headline is the LEVEL, with the day's change beside it (decimals shown). Owner 2026-11-20: the
# VIX at 28.44, up 70% in a month, was on the card as "+15.80%"; a change alone does not say whether the level
# is high. The 10-year yield has always shown its level (`level` / `bp`).
_LEVEL_TILES = {"VIX": 2, "USDSGD": 4}
# The Markets rows whose figure is coloured by direction: the price of something a reader can hold (three
# funds, oil, gold). Every other row stays ink, whatever its figure shows: a gauge (the VIX), a rate (the
# 10-year yield) and the two dollar rows (the index and USD/SGD), where a rise is not a gain. A list of the
# rows that ARE coloured, so a row added later is ink until someone puts it here (outside review of the
# build, 2026-11-24: a list of exceptions coloured the dollar index and would have coloured any new rate).
_PRICE_TILES = {"SPY", "QQQ", "SOXX", "WTI", "Gold"}


# ── formatting ───────────────────────────────────────────────────────────────

def _num(x):
    # A NaN is not a figure: it printed "nan%" and compared false both ways.
    return x if isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x) else None


def _signed(v, nd: int = 2, unit: str = "%") -> str:
    v = _num(v)
    if v is None:
        return "—"
    sign = "+" if v > 0 else (_MINUS if v < 0 else "")
    return f"{sign}{abs(v):.{nd}f}{unit}"


def _dir(v) -> str:
    """The class for a price's percentage move: `` bf-up`` for a rise, `` bf-down`` for a
    fall, nothing for no figure or for a move that prints as 0.00 (a move of 0.004% is
    not a green figure)."""
    v = _num(v)
    v = round(v, 2) if v is not None else 0
    if not v:
        return ""
    return " bf-up" if v > 0 else " bf-down"


def _vol(n: dict) -> str:
    """The mover's volume ratio. On a market still trading when the report ran
    (SGX / KRX at 12:05 SGT, MarketReport 2026-10-10) it is against the usual
    volume at that time of day, so it reads "so far"."""
    v = f'{n["vol_ratio"]:.2f}×'
    return f"{v} usual so far" if n.get("vol_basis") == "same_time_of_day" else v

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


#: Words that end in a full stop without ending a sentence ("3:30 p.m. Central", "Sec. 232",
#: "J.P. Morgan"): known abbreviations, and a single capital letter (an initial, "D.C.").
_NOT_AN_END = re.compile(r"\b(?:p\.m|a\.m|e\.g|i\.e|vs|approx|est|incl|Inc|Corp|Co|Ltd|St|No|Mr|Ms|Mrs|Dr|Sec|Fig"
                         r"|Sen|Rep|Gov|Pres|Prof|U\.S|U\.K|[A-Z])\.$")
#: A month cut short is not an end when a day number follows ("Dec. 9"); before a capital it
#: usually is one ("... shut Friday 9 Oct. Intel has not ...", the usual form in these notes).
_MONTH_DAY = re.compile(r"\b(?:Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)\.$")
_SENTENCE_END = re.compile(r"""[.!?]["'”’)\]]*\s+(?=[A-Z0-9“"'‘(\[])""")
#: A note of this many sentences or more is set as a list, one sentence a line.
_POINTS_FROM = 3
# A calendar row whose clock time is a stand-in (the usual release time, or the time it
# is due by): the briefing's writer says so in the row's text, by its instructions with
# the words "time not announced". Of the 186 "Next" items in the 66 briefings logged to
# 2026-11-23, 55 say it that way and 5 say "time not set" or "usual release time, not
# confirmed". The other 126 were searched for words such as "time", "usual", "expected"
# and "about": none of the 20 different rows found says its time is a stand-in.
# "time TBC", "time TBA", "time TBD" and "time not yet announced" are matched too; none is in the log.
_NO_TIME = re.compile(r"\btime[,:]?\s+(?:not\s+(?:yet\s+)?(?:announced|set|confirmed|given|known)|unannounced|tbc|tba|tbd)\b", re.IGNORECASE)


def _sentences(text) -> list:
    """``text`` cut into its sentences. A sentence ends at ``. `` / ``! `` / ``? `` before a
    capital, a digit, a quote or a bracket, unless the word before it is a known
    abbreviation or initial. It never loses or changes a word; a wrong cut costs a line
    break in the wrong place. Tried on the notes of the 66 briefings logged to 23 Nov 2026
    (tests/test_readable_text.py says what was counted)."""
    text = " ".join(str(text or "").split())     # one space for any run of spaces or line breaks
    parts, start = [], 0
    for m in _SENTENCE_END.finditer(text):
        head = text[start:m.end()].rstrip()
        if _NOT_AN_END.search(head) or (_MONTH_DAY.search(head) and text[m.end():m.end() + 1].isdigit()):
            continue
        parts.append(head)
        start = m.end()
    if text[start:].strip():
        parts.append(text[start:].strip())
    return parts


def _lines(text) -> list:
    """The writer's own points: the text's non-empty lines, when it has more than one.
    The briefing's writer is to be told to put each separate point of a markets note or
    a data note on a line of its own once this page is published (no briefing is
    written that way as of 2026-11-24); a point may be more than one sentence. One
    line, or a record written as one block, gives ``[]``. Blank lines between points
    are dropped. The lines are taken as points only when every one of them ends a
    sentence: a stray line break in the middle of a sentence gives ``[]``, and the note
    is cut by sentence like a note written as one block."""
    parts = [" ".join(ln.split()) for ln in str(text or "").splitlines() if ln.strip()]
    if len(parts) < 2 or not all(re.search(r"""[.!?]["'”’)\]]*$""", ln) for ln in parts):
        return []
    return parts


def _points(text, cls: str) -> str:
    """A writer's note: a paragraph when it is short, a list when it is long. The list is
    the writer's own lines when the note has them (``_lines``); a note written as one
    block is cut at its sentences. Set as one paragraph, a nine-sentence data note ran 14
    lines on a phone with nothing to hold the eye (owner 2026-11-24: "text dumps with no
    structuring"). The words are not changed, only where the lines break. ``cls`` is the
    class the paragraph has always had; the list keeps it."""
    parts = _lines(text)
    if not parts:
        parts = _sentences(text)
        if len(parts) < _POINTS_FROM:
            # The sentences joined again, not the text as it came: a line break in the
            # text would reach the page's HTML. One line break changes nothing there, but
            # a blank line splits the paragraph, and the half after it is set as a plain
            # <p> without this class (one test page, 2026-11-24, Streamlit 1.58; the
            # sections after it were unchanged in that test).
            return f'<p class="{cls}">{_txt(" ".join(parts))}</p>' if parts else ""
    return f'<ul class="{cls} bf-pts">' + "".join(f"<li>{_txt(x)}</li>" for x in parts) + "</ul>"


def _sec(title: str, body: str, aside: str = "", cls: str = "", prov="", kind: str = "") -> str:
    """One card section. ``kind`` tags a section that holds one kind of item (its heading
    marker takes that kind's hue); mixed sections leave it empty and stay ink. ``prov`` (the
    small source note under the section) is a sentence, or a list of ``(lead, text)`` rows
    when the note covers several kinds of row; the lead is the row's own first words, set
    bold."""
    if not body:
        return ""
    aside_html = f'<span class="bf-aside">{_txt(aside)}</span>' if aside else ""
    if isinstance(prov, (list, tuple)):
        prov_html = '<ul class="bf-prov bf-prov-list">' + "".join(
            f'<li><b>{_txt(lead)}</b> {_txt(text)}</li>' for lead, text in prov) + "</ul>"
    else:
        prov_html = f'<p class="bf-prov">{_txt(prov)}</p>' if prov else ""
    kind_attr = f' data-kind="{_escape_attr(kind)}"' if kind else ""
    return (f'<section class="bf-sec {cls}"{kind_attr}><div class="bf-sh"><h3>{_txt(title)}</h3>{aside_html}</div>'
            f'{body}{prov_html}</section>')


# ── sections ─────────────────────────────────────────────────────────────────

def _masthead(latest: dict, state: str, when: str) -> str:
    date = _date(latest.get("data_date"), "%A %-d %B")
    rows = ""
    short = ""
    for a in latest.get("as_of") or []:
        if not isinstance(a, dict):
            continue
        note = f'<small>{_txt(a["note"])}</small>' if a.get("note") else ""
        rows += f'<div><dt>{_txt(a.get("label"))}</dt><dd>{_txt(a.get("when"))}{note}</dd></div>'
        # The folded line keeps every entry's label and its time as written; only the
        # note stays behind the tap. (A first version dropped a closing bracket such as
        # "(New York)"; it would have dropped "(preliminary)" just the same.)
        short += f'<span><b>{_txt(a.get("label"))}</b> {_txt(a.get("when")) or "—"}</span>'
    # Two copies of the same lines: the boxes as they always were, and a folded form
    # for a phone, where the four boxes pushed "What matters" off the first screen
    # (layout review 2026-11-24, P4). The stylesheet shows one of the two by window
    # width. A <details> cannot be opened by a stylesheet, hence the second copy.
    asof = (f'<dl class="bf-asof bf-asof-wide">{rows}</dl>'
            f'<details class="bf-asof-fold"><summary><i>As of</i>{short}</summary>'
            f'<dl class="bf-asof">{rows}</dl></details>') if rows else ""
    written = str(latest.get("ts_sgt") or "")[:16].replace("T", " ")
    upcoming = [c for c in latest.get("calendar") or []
                if isinstance(c, dict) and str(c.get("sgt", "")) > written.replace(" ", "T")][:3]
    # On a narrow card the stylesheet sets each item on one line, its time first and its
    # text cut with an ellipsis: three wrapped items were 201px on a phone and kept "What
    # matters" off the first screen. Nothing is lost, Week ahead prints the same rows in
    # full. A row whose time is a stand-in says so in its text ("time not announced",
    # the briefing skill's wording, at the end of the text), and the end is the part
    # the cut drops, so such a row is marked and its one-line form shows the day
    # without the clock.
    nxt = ""
    if upcoming:
        nxt = ('<div class="bf-next"><b>Next<small>SGT</small></b><div class="bf-next-list">'
               + "".join(f'<span data-kind="{_escape_attr(c.get("kind"))}"'
                         f'{" data-notime" if _NO_TIME.search(str(c.get("what") or "")) else ""}>'
                         f'<strong>{_txt(c.get("what"))}</strong> '
                         f'<time datetime="{_escape_attr(c["sgt"])}+08:00">{_txt(_date(c["sgt"], "%a"))} '
                         f'<span class="bf-next-hm">{_txt(_hm(c["sgt"]))}</span></time></span>' for c in upcoming)
               + '</div></div>')
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
                cls="bf-after", kind="after", prov="Not in the US prices below. Later sessions (SGX, KRX) may already include it.")


def _mark(m) -> str:
    """"Highest since the 31 Mar report": the level against this site's own stored reports (MarketReport
    `bench_extreme_facts`, 20 or more earlier reports). A fact about the level; it takes no colour."""
    if not isinstance(m, dict) or m.get("word") not in ("highest", "lowest"):
        return ""
    if m.get("since"):
        text = f'{m["word"]} since the {_date(m["since"], "%-d %b")} report'
    elif m.get("basis_from"):
        text = f'{m["word"]} in {m.get("reports")} reports, back to {_date(m["basis_from"], "%-d %b")}'
    else:
        text = f'{m["word"]} in the {m.get("reports")} reports before it'
    return f'<span class="bf-s bf-mark">{_txt(text[:1].upper() + text[1:])}</span>'


def _tape(latest: dict, nums: dict, sources: list | None = None) -> str:
    tiles = ""
    for r in nums.get("tape") or []:
        name = r.get("name", "")
        price = _num(r.get("price"))
        moved = ""
        level = _num(r.get("level"))
        if level is not None:
            val = f'{level:.2f}%<small>{_signed(r.get("bp"), 0, "bp")}</small>'
        elif name in _LEVEL_TILES and price is not None:
            val = f'{price:.{_LEVEL_TILES[name]}f}<small>{_signed(r.get("chg_pct"))}</small>'
        else:
            val = _signed(r.get("chg_pct"))
            moved = _dir(r.get("chg_pct")) if name in _PRICE_TILES else ""
        # Each figure with its label is one unbreakable piece: on a phone five of nine
        # tiles broke "1mo" from its figure (outside review, 2026-11-24).
        parts = ([f'{_x(r.get("x_usual"))} usual'] if _num(r.get("x_usual")) is not None else []) + [
            f'5d {_signed(r.get("5d_pct"), 1)}'] + (
            [f'1mo {_signed(r.get("mo_pct"), 1)}'] if _num(r.get("mo_pct")) is not None else [])
        sub = " · ".join(f'<span class="bf-nw">{p}</span>' for p in parts)
        tiles += (f'<div class="bf-tile"><span class="bf-n">{_txt(_BENCH_LABEL.get(name, name))}</span>'
                  f'<span class="bf-v{moved}">{val}</span><span class="bf-s">{sub}</span>'
                  f'{_mark(r.get("mark"))}</div>')
    if not tiles:
        return ""
    note = _points(latest.get("tape_note"), "bf-cap")
    vix = latest.get("vix_note")
    if isinstance(vix, dict) and str(vix.get("text") or "").strip():
        # The writer's short note: what the VIX is, where it stands and what the day's reports tie the move to.
        note += (f'<div class="bf-vix"><b>The VIX</b><p>{_txt(vix["text"])} '
                 f'{_chips(vix.get("src"), sources or [])}</p></div>')
    last = (nums.get("health") or {}).get("last_us_session")
    # "Markets", not "The tape" (owner 2026-09-29: trader shorthand a reader should not need).
    aside = "stocks, rates, dollar, oil, gold" + (f" · US close {_date(last)}" if last else "")
    # Only when a tile carries the marker, and with no start month: the rows' stored series differ in length
    # (USD/SGD joined in September 2026), and each marker already says how far back it looks.
    marked = any(isinstance(r.get("mark"), dict) for r in nums.get("tape") or [])
    prov = "Numbers: morning report" + (
        ". “Highest” / “lowest” compares the level with this site’s own earlier daily reports, not with all "
        "history." if marked else "")
    return _sec("Markets", f'<div class="bf-tape">{tiles}</div>{note}', aside, prov=prov, kind="price")


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
                f'{_x(n.get("x_usual"))} usual' if _num(n.get("x_usual")) is not None else "")
            vol = f' · vol {_vol(n)}' if _num(n.get("vol_ratio")) is not None else ""
            none = it.get("why_state") == "none_found"
            # The inner block carries the line cap: `max-width` does not bind on a table cell,
            # and at 768 to 1024px a reason ran about 86 characters a line.
            why = (f'<td class="bf-why{" bf-none" if none else ""}"><div class="bf-why-in">{_txt(it.get("why"))} '
                   f'{_chips(it.get("src"), sources)}</div></td>')
            rows += (f'<tr><td class="bf-nm"><b>{_txt(n.get("name") or it["key"])}</b>'
                     f'<span>{_txt(it["key"].split("_")[0])}</span></td>'
                     f'<td class="bf-mv{_dir(n.get("chg_pct"))}">{_signed(n.get("chg_pct"))}'
                     f'<small>{size}{vol}</small></td>{why}</tr>')
    if not rows:
        return ""
    table = (f'<table class="bf-movers"><thead><tr><th scope="col">Name</th><th scope="col">Move</th>'
             f'<th scope="col">Why</th></tr></thead><tbody>{rows}</tbody></table>')
    also = [a for a in nums.get("also_moved") or [] if isinstance(a, dict)]
    if also:
        # One row a name (name, move, size against its usual day, volume). It was one
        # sentence of names joined by middots: fourteen of them ran 14 lines on a phone.
        # A size or a volume that is not a figure is left out: "usual" alone said nothing.
        rows = "".join(
            f'<li><span class="bf-also-n">{_txt(a.get("name") or a.get("key"))}</span>'
            f'<span class="bf-also-m{_dir(a.get("chg_pct"))}">{_signed(a.get("chg_pct"))}</span>'
            f'<span class="bf-also-x">' + " · ".join(
                ([f'{_x(a.get("x_usual"))} usual'] if _num(a.get("x_usual")) is not None else [])
                + ([f'vol {_vol(a)}'] if _num(a.get("vol_ratio")) is not None else [])) + '</span></li>'
            for a in also)
        table += f'<div class="bf-also"><b>Also moved, not looked up:</b><ul>{rows}</ul></div>'
    return _sec("Names that moved", table, "grouped by when the price was taken", kind="price",
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
            + "".join(f'<span class="bf-rq"><b>{_txt(i.get("name"))}</b> {_txt(i.get("q"))}</span>'
                      for i in r["items"] if isinstance(i, dict))
            + '</span></li>' for r in rchk)
        body += (f'<details class="bf-rchk"><summary><b>Catalyst rechecks due:</b> {n} item{"s" if n != 1 else ""} '
                 f'across {len(rchk)} date{"s" if len(rchk) != 1 else ""}</summary><ul>{li}</ul></details>')
    if body:
        body += ('<div class="bf-key"><span data-kind="macro">Macro release</span>'
                 '<span data-kind="earnings">Earnings</span><span data-kind="event">Conference</span></div>')
    return _sec("Week ahead", body, "all times SGT", cls="bf-cal",
                prov="Calendar: morning report · Rechecks: catalysts.json")


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

    def lab(v, text: str, row: str) -> str:
        # One label per row (consensus above, range ends below, guide under those), so
        # labels never collide; one near an edge anchors inward instead of centring
        # (~1.4 % of a phone-width bar per character, half of it each side).
        p = (v - lo) / (hi - lo) * 100
        half = len(text) * 0.7
        align = "" if p < half else " bf-r" if p > 100 - half else " bf-c"
        return f'<span class="bf-lab {row}{align}" style="left:{p:.2f}%">{_txt(text)}</span>'

    parts = '<span class="bf-axis"></span>'
    labels = ""
    rl, rh = _num(fig.get("range_low")), _num(fig.get("range_high"))
    if rl is not None and rh is not None:
        parts += f'<span class="bf-range" style="left:{pos(rl)};width:{(rh - rl) / (hi - lo) * 100:.2f}%"></span>'
        labels += (f'<span class="bf-lab bf-bot" style="left:{pos(rl)}">{rl:.{nd}f}</span>'
                   f'<span class="bf-lab bf-bot bf-r" style="left:{pos(rh)}">{rh:.{nd}f}</span>')
    gl, gh = _num(fig.get("guide_low")), _num(fig.get("guide_high"))
    if gl is not None and gh is not None:
        parts += f'<span class="bf-guide" style="left:{pos(gl)};width:{(gh - gl) / (hi - lo) * 100:.2f}%"></span>'
        labels += lab((gl + gh) / 2, f"company {gl:.{nd}f}–{gh:.{nd}f}", "bf-gd")
    parts += f'<span class="bf-cons" style="left:{pos(cons)}"></span>'
    labels += lab(cons, f"analysts {cons:.{nd}f}", "bf-top")    # whose number, not "expected" (reads as ours)
    aria = f"{label}: analysts expect {cons}" + (f", company forecast {gl} to {gh}" if gl is not None else "") + (
        f", analyst estimates {rl} to {rh}" if rl is not None else "")
    return (f'<div class="bf-rng"><div class="bf-rlab"><b>{_txt(label)}</b>, {_txt(unit)}</div>'
            f'<div class="bf-rbar" role="img" aria-label="{_escape_attr(aria)}">{parts}{labels}</div></div>')


def _figures(rev: dict) -> str:
    # Plain labels, not analyst shorthand (owner 2026-09-29, after "the tape"): "consensus" →
    # what analysts expect, "guide" → the company's own forecast, "range" → lowest to highest.
    cells = []
    if _num(rev.get("consensus")) is not None:
        an = f'<small>average of {rev["analysts"]}</small>' if rev.get("analysts") else ""
        cells.append(("Analysts expect", f'~${rev["consensus"]:.1f}B{an}'))
    gl, gh = _num(rev.get("guide_low")), _num(rev.get("guide_high"))
    if gl is not None and gh is not None:
        cells.append(("Company forecast", f'${(gl + gh) / 2:.1f}B ± {(gh - gl) / 2:.1f}<small>its own guidance</small>'))
    rl, rh = _num(rev.get("range_low")), _num(rev.get("range_high"))
    if rl is not None and rh is not None:
        cells.append(("Analyst estimates", f'${rl:.1f}–{rh:.1f}B<small>lowest to highest</small>'))
    if not cells:
        return ""
    return '<dl class="bf-nums">' + "".join(f'<div><dt>{_txt(k)}</dt><dd>{v}</dd></div>' for k, v in cells) + "</dl>"


def _b(fig: dict, *keys) -> tuple | None:
    """(low, high) in full units from a record figure given in billions, or None."""
    vals = [_num(fig.get(k)) for k in keys]
    return None if None in vals else tuple(v * 1e9 for v in vals)


def _detail_charts(key: str, rev: dict, eps: dict, earnings: dict) -> str:
    """Revenue + EPS charts for a written-up name; "" when the history is not on file.
    The coming bar uses the briefing's own consensus so the chart and the figures above agree."""
    s = quarter_series(earnings.get(key) or [])
    if s.get("coming") and _num(rev.get("consensus")) is not None and revenue_currency(key) == "US$":
        s["coming"] = dict(s["coming"], rev_est=rev["consensus"] * 1e9)
    company = _b(rev, "guide_low", "guide_high") if revenue_currency(key) == "US$" else None
    whisker = _b(rev, "range_low", "range_high") if revenue_currency(key) == "US$" else None
    eps_co = (_num(eps.get("guide_low")), _num(eps.get("guide_high")))
    charts = (revenue_chart_html(s, revenue_currency(key), company=company, whisker=whisker)
              + eps_chart_html(s, eps_currency(key), company=eps_co if None not in eps_co else None))
    return block_html(charts, company=bool(company))


def _week_grid(latest: dict, nums: dict, earnings: dict, skip: set) -> str:
    """Small revenue charts for every name reporting in the next 7 days (not already written up)."""
    try:
        start = _dt.date.fromisoformat(str(latest.get("data_date"))[:10])
    except ValueError:
        return ""
    names = nums.get("names") or {}
    rows = []
    for key, recs in earnings.items():
        if key in skip:
            continue
        # A quarter not yet reported has NaN for its actual in the loaded earnings file (None in a
        # hand-built record). `_num` reads both as "no figure", which is what this needs: testing
        # for None alone would find no coming quarter on the live site.
        nxt = next((r for r in recs if _num(r.get("eps_actual")) is None and r.get("announce_date")
                    and (_num(r.get("revenue_estimate")) is not None or _num(r.get("eps_estimate")) is not None)), None)
        if not nxt:
            continue
        try:
            when = _dt.date.fromisoformat(str(nxt["announce_date"])[:10])
        except ValueError:
            continue
        if 0 <= (when - start).days <= 7:
            rows.append((when, key))
    cells = ""
    for when, key in sorted(rows):
        chart = revenue_chart_html(quarter_series(earnings[key]), revenue_currency(key), mini=True)
        cells += (f'<div class="bf-eg"><div class="bf-eg-h"><b>{_txt(names.get(key, key))}</b>'
                  f'<time datetime="{when.isoformat()}">{_txt(_date(when.isoformat()))}</time></div>'
                  f'{chart or "<p class=ec-note>Not enough reported quarters on file.</p>"}</div>')
    if not cells:
        return ""
    return ('<p class="bf-eg-t">Reporting in the next 7 days · revenue by quarter, own currency · '
            'full charts on the Watchlist tab</p><div class="bf-egrid">' + cells + '</div>')


def _earnings(latest: dict, nums: dict, sources: list, earnings: dict | None = None) -> str:
    earnings = earnings or {}
    earn = latest.get("earnings") if isinstance(latest.get("earnings"), dict) else {}
    names = nums.get("names") or {}
    body = ""
    written = set()
    for e in earn.get("coming") or []:
        if not isinstance(e, dict) or not e.get("key"):
            continue
        rev = e.get("revenue") if isinstance(e.get("revenue"), dict) else {}
        eps = e.get("eps") if isinstance(e.get("eps"), dict) else {}
        sgt = str(e.get("when_sgt") or "")
        period = f'<span>{_txt(e["key"])} · {_txt(e.get("period"))}</span>' if e.get("period") else ""
        when_note = f'<small>{_txt(e["when_note"])}</small>' if e.get("when_note") else ""
        facts = f'<p class="bf-facts">{_txt(e["facts"])} {_chips(e.get("src"), sources)}</p>' if e.get("facts") else ""
        written.add(e["key"])
        charts = _detail_charts(e["key"], rev, eps, earnings)
        bars = charts or (_range_bar(rev, "Revenue", "US$ billions", 1)
                          + _range_bar(eps, "Earnings per share", "US$", 2))
        body += (f'<div class="bf-ec"><div class="bf-ec-top"><div class="bf-ec-name">'
                 f'{_txt(names.get(e["key"], e["key"]))}{period}</div>'
                 f'<div class="bf-ec-when"><b><time datetime="{_escape_attr(sgt)}+08:00">'
                 f'{_txt(_date(sgt))} · {_txt(_hm(sgt))} SGT</time></b>{when_note}</div></div>'
                 f'{_figures(rev)}{bars}{facts}</div>')
    body += _week_grid(latest, nums, earnings, written)
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
                prov=earn.get("note") or "", kind="earnings")


def _far_item(r: dict) -> str:
    """One further-out row: a conference carries its last day, a read-across print
    (a company off the watchlist) says it is not held and which names it moves."""
    extra = ""
    if r.get("end_date"):
        extra = f'<small>to {_txt(_date(r["end_date"]))}</small>'
    elif isinstance(r.get("read_across"), list):
        moves = ", ".join(str(m) for m in r["read_across"][:4])
        extra = f'<small>not held{" · moves " + _txt(moves) if moves else ""}</small>'
    # A hand-pinned row (2026-11-23) carries its whole text: "Samsung preliminary results", not "... earnings".
    suffix = " earnings" if r.get("kind") == "earnings" and not r.get("pinned") else ""
    return f'<b data-kind="{_escape_attr(r.get("kind"))}">{_txt(r["what"])}{suffix}{extra}</b>'


def _far_list(rows: list) -> str:
    days: dict = {}
    for r in rows:
        days.setdefault(str(r["date"])[:10], []).append(r)
    return '<ul class="bf-far">' + "".join(
        f'<li><time datetime="{_escape_attr(d)}">{_txt(_date(d))}</time><span>'
        + "".join(_far_item(r) for r in evs)
        + '</span></li>' for d, evs in sorted(days.items())) + "</ul>"


def _further(nums: dict) -> str:
    """Dated events past the week-ahead and 14-day earnings windows, out to two months (owner
    2026-09-29; 60 days = the earnings feed's reach). publish joins them from the data into
    ``numbers.further_out``; dates only. The second month (``later``) shows open under a
    "less certain" label (owner 09-29: visible at once, not a fold): more of its earnings dates
    are the feed's estimates. Its earnings rows take a dashed edge — a line style, not a hue.
    Headed "Upcoming events" since 2026-09-30 (owner: "Further out" named the distance, not what
    is in it); the data key stays ``further_out``."""
    rows = [r for r in nums.get("further_out") or [] if isinstance(r, dict) and r.get("date") and r.get("what")]
    if not rows:
        return ""
    soon = [r for r in rows if not r.get("later")]
    later = [r for r in rows if r.get("later")]
    body = _far_list(soon) if soon else ""
    if later:
        body += ('<div class="bf-later"><p class="bf-later-h"><b>Later · 31–60 days · less certain</b> '
                 'Earnings dates this far out are often estimates and may move. A policy date can be moved or renewed.</p>'
                 f'{_far_list(later)}</div>')
    return _sec("Upcoming events", body, "to two months · dates only", cls="bf-cal",
                # The same words as before 2026-11-24, one row for each kind of date instead of
                # one 700-character paragraph; the leads are the note's own.
                prov=[("Earnings dates", "past 14 days are the exchange's local date. Most come from Yahoo "
                                         "Finance's calendar: “estimated date” marks one Yahoo itself calls an "
                                         "estimate, and an unmarked one can still move. “date confirmed” marks a "
                                         "date the project took from the company's own announcement."),
                      ("Macro:", "high-impact releases only, dated in New York time, so a Singapore-morning "
                                 "release (MAS) shows the day before."),
                      ("Policy dates", "(a tariff taking effect, a deadline) and company releases the calendar "
                                       "feed does not carry: entered by hand from the official notice, in that "
                                       "authority's own date."),
                      ("Conferences:", "the pipeline's tech-events list."),
                      ("Not held:", "results from a company off the watchlist that move names on it (looked up "
                                    "21 days ahead).")])


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
    ticks = ""
    for t in range(lo, hi + 1, 10):
        minor = "" if t in (lo, 0, hi) else ' class="bf-minor"'       # dropped on a narrow card
        # An end label less than a quarter of the axis from "0" prints on top of it, or
        # touches it, on a phone-width card (all bars one side of zero: "0" and "+10%"
        # read "+010%"); the stylesheet drops that end label there. A fifth was the
        # first figure: at exactly a fifth the two still touched on a 360px phone. The
        # scale itself does not change.
        if t in (lo, hi) and abs(pos(t) - z) < 25:
            minor = ' class="bf-near"'
        align = ";transform:none" if t == lo else ";transform:translateX(-100%)" if t == hi else ""
        ticks += f'<span{minor} style="left:{pos(t):.2f}%{align}">{_signed(t, 0) if t else "0"}</span>'
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
        elif 100 - z < 25 and width > 36:
            # Bars below zero carry their figure right of the zero line. With every bar
            # below zero the line sits near the axis's right end (85.7% on 23 Nov 2026) and
            # the figure ran into the RSI column on a 320px phone ("−10.7%20.5"; 4px clear
            # at 360px). With under a quarter of the axis right of zero the figure goes
            # inside a long bar, at its zero end (36% of the narrowest axis, 121px, holds
            # it), and left of a short one (outside review, 2026-11-24).
            lab = f'<span class="bf-val bf-in" style="left:{z:.2f}%">{_signed(val, 1)}</span>'
        elif 100 - z < 25:
            lab = f'<span class="bf-val bf-beside" style="left:{a:.2f}%">{_signed(val, 1)}</span>'
        else:
            lab = f'<span class="bf-val" style="left:{z + 1.5:.2f}%">{_signed(val, 1)}</span>'
        rsi = f'{v["rsi"]:.1f}' if _num(v.get("rsi")) is not None else "—"
        body += (f'<li><span class="bf-nm2">{_txt(v.get("name") or k)}</span><div class="bf-bar">'
                 f'<span class="bf-zero" style="left:{z:.2f}%"></span>'
                 f'<span class="bf-b" style="left:{left:.2f}%;width:{max(width, 0.4):.2f}%"></span>{lab}</div>'
                 f'<span class="bf-rsi">{rsi}</span></li>')
    body += "</ul>"
    body += _points((latest.get("chart_facts") or {}).get("note"), "bf-cap")
    last = (nums.get("health") or {}).get("last_us_session")
    return _sec("Chart facts", body, "% from the 50-day average" + (f" · {_date(last)}" if last else ""),
                prov="% from the 50-day moving average and RSI: morning report", kind="price")


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
    html += _points(latest.get("data_notes"), "bf-dntext")
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


def briefing_v2_html(latest: dict, report_date: str | None = None, earnings: dict | None = None) -> str:
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
    # Two groups in the reading order: what happened (what matters, after the data,
    # markets, names that moved) and what is coming (week ahead, earnings, upcoming
    # events). On a PC the stylesheet sets them side by side, today left and the
    # coming dates right (layout review 2026-11-24, P5: the card's right half was
    # empty beside capped text, and the coming dates sat three screens down). Below
    # that width the two wrappers take no box and the sections stack as before. A
    # day with only one of the two groups gets no wrappers.
    today = (_what_matters(latest, sources) + _after(latest, sources)
             + _tape(latest, nums, sources) + _movers(latest, nums, sources))
    coming = _week(latest) + _earnings(latest, nums, sources, earnings or {}) + _further(nums)
    if today and coming:
        middle = (f'<div class="bf-cols"><div class="bf-col bf-col-today">{today}</div>'
                  f'<div class="bf-col bf-col-coming">{coming}</div></div>')
    else:
        middle = today + coming
    body = (
        _masthead(latest, state, when)
        + middle
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
