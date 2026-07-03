# AI Capex Pulse — Legibility Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the AI Capex Pulse band legible — add an auto-derived verdict line, rework the coverage gap into one dated number plus a forward note (removing the −18.6pp-vs-+16pp contradiction), and unify color so it always means health while arrows carry direction — without changing the underlying data or the five signals shown.

**Architecture:** Pure computations stay in `lib/capex.py` (no Streamlit imports, trivially unit-testable); the Streamlit band in `components/briefing/capex_pulse.py` only renders. We add computation (`pulse_verdict`, `compute_verdict`, `forward_revenue_note`) and chip metadata (`tone`/`arrow`/`sub`) first while keeping the old fields alive, then cut the component over, then delete the dead code — so every commit leaves the app runnable and the test suite green.

**Tech Stack:** Python, Streamlit, pandas, Plotly, pytest. Tests use plain functions with hand-built dict/DataFrame fixtures (see existing `tests/test_capex.py`).

## Global Constraints

- **pandas floor 1.4.2** (local env is base Anaconda; see memory `local-env-base-anaconda`). Only use pandas APIs available in 1.4.2 — the code here uses `groupby`/`median`/`unstack`/`isin`/`dropna(subset=...)`/`quantile`, all fine.
- **`lib/capex.py` imports no Streamlit** — pure functions only (the `lib/formatters.py` rule).
- **Thresholds and the verdict rule are documented presentation choices, NOT calibrated signals. Nothing here feeds the scenario odds.**
- **All report-derived text is injected through `_escape_dollars`** (HTML-escapes `& < >`, neutralizes `$`) before `unsafe_allow_html`.
- **Chips are always five, in fixed order** `["capex", "gap", "rev", "val", "fragile"]`, and every degraded state has explicit copy — never a silent blank.
- **Color = health (`tone` → dot color), arrow = direction (`arrow` → ▲/▼).** The two are decoupled: "up" must never read as "good" in one chip and "bad" in another.
- **Every commit ends its message with the two standard trailer lines** (`Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>` and the `Claude-Session:` line). Commit only the files listed in each task.
- **Every commit keeps the app runnable.** The transitional `state` field and `current_read` function stay until the component no longer reads them (Task 4), then get deleted (Task 5).

---

### Task 1: Add `tone`/`arrow`/`sub` to every chip (keep `state`)

Give each chip the new display metadata while leaving the existing `state` field intact, so the current component keeps rendering unchanged. Capex tone is **always `neutral`** when it has data — acceleration is direction, not health.

**Files:**
- Modify: `lib/capex.py` (the five `_*_chip` functions)
- Test: `tests/test_capex.py`

**Interfaces:**
- Consumes: existing `core_capex_yoy`, `pending_quarter`, `coverage_gap_series`, `_median_rev_growth`, `ACCEL_PP`, `GAP_WIDEN_PP`, `REV_TREND_WINDOW_DAYS`, `REV_FLAT_PP`, `VAL_WARN_QUANTILE`, `SEMIS_CLUSTER`.
- Produces: each chip dict now additionally has `sub: str`, `tone: str` (`"good"|"watch"|"stress"|"neutral"|"na"`), `arrow: str` (`"up"|"down"|"none"`). `state` is unchanged (removed later in Task 5). Order stays `["capex","gap","rev","val","fragile"]`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_capex.py`:

```python
def test_chips_carry_tone_arrow_and_sub():
    chips = build_chips(_capex_three_yoy(50.0, 52.0),
                        fundamentals_history(GAP_REPORTS), _date(2026, 7, 3))
    capex = _chip(chips, "capex")
    assert capex["tone"] == "neutral" and capex["arrow"] == "up"   # accel = direction only
    assert all(c["sub"] for c in chips)                            # every chip self-labels


def test_capex_tone_neutral_even_when_decelerating():
    chips = build_chips(_capex_three_yoy(60.0, 40.0), fundamentals_history({}),
                        _date(2026, 7, 3))
    c = _chip(chips, "capex")
    assert c["tone"] == "neutral" and c["arrow"] == "down"


def test_rev_falling_is_watch_tone_and_down_arrow():
    reports = {
        "2026-04-01": _report({"NVDA": {"valuation": {"revenue_growth_pct": 90.0}},
                               "MU": {"valuation": {"revenue_growth_pct": 60.0}}}),
        "2026-07-01": _report({"NVDA": {"valuation": {"revenue_growth_pct": 70.0}},
                               "MU": {"valuation": {"revenue_growth_pct": 30.0}}}),
    }
    c = _chip(build_chips(parse_capex(_raw()), fundamentals_history(reports),
                          _date(2026, 7, 3)), "rev")
    assert c["tone"] == "watch" and c["arrow"] == "down"


def test_fragile_red_is_stress_tone():
    capex = parse_capex(_raw({"CRWV": [
        {"cq": "2026Q1", "reported": "2026-05-07", "capex_usd_b": 9.9, "flag": "red"}]}))
    c = _chip(build_chips(capex, fundamentals_history({}), _date(2026, 7, 3)), "fragile")
    assert c["tone"] == "stress"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_capex.py -k "tone or arrow or stress" -v`
Expected: FAIL with `KeyError: 'tone'` (chips have no `tone` yet).

- [ ] **Step 3: Rewrite the five chip functions**

In `lib/capex.py`, replace the bodies of `_capex_chip`, `_gap_chip`, `_rev_chip`, `_val_chip`, `_fragile_chip` with these (each keeps `state`, adds `sub`/`tone`/`arrow`):

```python
def _capex_chip(capex: dict) -> dict:
    names = "/".join(capex["core"]) or "core-spender"
    sub = f"combined {names} capex, year-over-year"
    yoy = [r for r in core_capex_yoy(capex) if r["yoy_pct"] is not None]
    if len(yoy) < 2:
        pend = pending_quarter(capex)
        detail = (f"awaiting {len(pend['missing'])} of {len(capex['core'])} spenders for {pend['cq']}"
                  if pend else "needs two quarters of complete core capex")
        return {"key": "capex", "label": "Capex", "sub": sub, "state": "na",
                "tone": "na", "arrow": "none", "detail": detail,
                "asof": yoy[-1]["cq"] if yoy else "—"}
    cur, prev = yoy[-1], yoy[-2]
    delta = cur["yoy_pct"] - prev["yoy_pct"]
    if delta >= ACCEL_PP:
        state, arrow, word = "accel", "up", "accelerating"
    elif delta <= -ACCEL_PP:
        state, arrow, word = "warn", "down", "decelerating"
    else:
        state, arrow, word = "ok", "none", "steady"
    return {"key": "capex", "label": "Capex", "sub": sub, "state": state,
            "tone": "neutral", "arrow": arrow,
            "detail": (f"core YoY {cur['yoy_pct']:+.1f}% vs "
                       f"{prev['yoy_pct']:+.1f}% prior — {word}"),
            "asof": cur["cq"]}


def _gap_chip(capex: dict, fund_df: pd.DataFrame) -> dict:
    sub = ("beneficiary revenue growth minus capex growth — "
           "negative = spend outrunning sales")
    gaps = coverage_gap_series(capex, fund_df)
    if not gaps:
        return {"key": "gap", "label": "Coverage gap", "sub": sub, "state": "na",
                "tone": "na", "arrow": "none", "detail": "needs capex data",
                "asof": "—"}
    g = gaps[-1]
    widening = len(gaps) >= 2 and (g["gap_pp"] - gaps[-2]["gap_pp"]) <= -GAP_WIDEN_PP
    if g["gap_pp"] < 0:
        state, tone = "warn", "watch"
        word = "negative and widening" if widening else "capex outrunning revenue"
    elif widening:
        state, tone, word = "warn", "watch", "narrowing fast"
    else:
        state, tone, word = "ok", "good", "revenue keeping pace"
    return {"key": "gap", "label": "Coverage gap", "sub": sub, "state": state,
            "tone": tone, "arrow": "none",
            "detail": (f"{g['gap_pp']:+.1f}pp (rev {g['rev_growth_pct']:+.1f}% − "
                       f"capex {g['capex_yoy_pct']:+.1f}%) — {word}"),
            "asof": g["cq"]}


def _rev_chip(capex: dict, fund_df: pd.DataFrame) -> dict:
    sub = "median sales growth of the chip names that sell into that capex"
    now = _median_rev_growth(fund_df, capex["beneficiaries"])
    if now is None:
        return {"key": "rev", "label": "Beneficiary revenue", "sub": sub,
                "state": "na", "tone": "na", "arrow": "none",
                "detail": "no revenue-growth data in reports", "asof": "—"}
    now_date, now_med = now
    cutoff = (datetime.strptime(now_date, "%Y-%m-%d").date()
              - timedelta(days=REV_TREND_WINDOW_DAYS)).isoformat()
    bdf = fund_df[fund_df["ticker"].isin(capex["beneficiaries"])].dropna(
        subset=["revenue_growth_pct"])
    older = sorted(d for d in bdf["date"].unique() if d <= cutoff)
    if not older:
        return {"key": "rev", "label": "Beneficiary revenue", "sub": sub,
                "state": "ok", "tone": "good", "arrow": "none",
                "detail": (f"median {now_med:+.1f}% — corpus younger than "
                           f"{REV_TREND_WINDOW_DAYS}d, no trend yet"),
                "asof": now_date}
    ref_date = older[-1]
    ref_med = float(bdf[bdf["date"] == ref_date]["revenue_growth_pct"].median())
    delta = now_med - ref_med
    if delta >= REV_FLAT_PP:
        state, tone, arrow, word = "ok", "good", "up", "rising"
    elif delta <= -REV_FLAT_PP:
        state, tone, arrow, word = "warn", "watch", "down", "falling"
    else:
        state, tone, arrow, word = "ok", "good", "none", "flat"
    return {"key": "rev", "label": "Beneficiary revenue", "sub": sub,
            "state": state, "tone": tone, "arrow": arrow,
            "detail": f"median {now_med:+.1f}% vs {ref_med:+.1f}% on {ref_date} — {word}",
            "asof": now_date}


def _val_chip(fund_df: pd.DataFrame) -> dict:
    sub = "Semis forward P/E vs its own recent range"
    sem = fund_df[fund_df["cluster"] == SEMIS_CLUSTER]
    pe = sem.dropna(subset=["forward_pe"]).groupby("date")["forward_pe"].median()
    if len(pe) < 5:
        return {"key": "val", "label": "Valuation", "sub": sub, "state": "na",
                "tone": "na", "arrow": "none",
                "detail": "needs ≥5 reports with Semis valuations", "asof": "—"}
    peg = sem.dropna(subset=["peg_ratio"]).groupby("date")["peg_ratio"].median()
    pe_now, pe_hot = float(pe.iloc[-1]), float(pe.quantile(VAL_WARN_QUANTILE))
    peg_now = float(peg.iloc[-1]) if len(peg) else float("nan")
    peg_hot = float(peg.quantile(VAL_WARN_QUANTILE)) if len(peg) else float("nan")
    rich = pe_now > pe_hot or (peg_now == peg_now and peg_hot == peg_hot
                               and peg_now > peg_hot)
    peg_s = f" · PEG {peg_now:.2f}" if peg_now == peg_now else ""
    return {"key": "val", "label": "Valuation", "sub": sub,
            "state": "warn" if rich else "ok",
            "tone": "watch" if rich else "good", "arrow": "none",
            "detail": (f"Semis median fwd PE {pe_now:.1f} "
                       f"(80th pct {pe_hot:.1f}){peg_s} — "
                       f"{'rich vs own history' if rich else 'within range'}"),
            "asof": str(pe.index[-1])}


def _fragile_chip(capex: dict) -> dict:
    sub = "the debt-funded name most likely to crack first; NVDA–CRWV circularity node"
    frows = [(tk, capex["series"][tk][-1]) for tk in capex["fragile"]
             if capex["series"].get(tk)]
    if not frows:
        return {"key": "fragile", "label": "Fragile tier", "sub": sub, "state": "na",
                "tone": "na", "arrow": "none", "detail": "no fragile-tier rows",
                "asof": "—"}
    severity = {"red": 2, "amber": 1}
    tk, row = max(frows, key=lambda p: severity.get(p[1].get("flag", ""), 0))
    flag = row.get("flag") or "unflagged"
    note = f" — {row['note']}" if row.get("note") else ""
    tone = {"red": "stress", "amber": "watch"}.get(flag, "good")
    return {"key": "fragile", "label": "Fragile tier", "sub": sub,
            "state": "warn" if flag in severity else "ok",
            "tone": tone, "arrow": "none",
            "detail": f"{tk} {row['cq']} capex ${row['capex_usd_b']:.1f}B · {flag}{note}",
            "asof": row["cq"]}
```

- [ ] **Step 4: Run the full capex test file to verify pass (new + existing green)**

Run: `python -m pytest tests/test_capex.py -v`
Expected: PASS — the four new tests pass, and every existing `state`-based test still passes (state is unchanged).

- [ ] **Step 5: Commit**

```bash
git add lib/capex.py tests/test_capex.py
git commit -m "feat(capex): add tone/arrow/sub chip metadata (health vs direction)"
```
(+ standard trailer)

---

### Task 2: `pulse_verdict` + `compute_verdict`

Add the auto-derived headline read. Pure `pulse_verdict` takes plain booleans/floats; `compute_verdict` wires the band's own chips into it so the verdict can never disagree with the chips it summarizes.

**Files:**
- Modify: `lib/capex.py`
- Test: `tests/test_capex.py`

**Interfaces:**
- Consumes: `coverage_gap_series`, chip dicts from `build_chips` (reads `tone` on `rev`/`fragile`).
- Produces:
  - `pulse_verdict(gap_available: bool, gap_pp: float, rev_falling: bool, fragile_red: bool) -> dict` returning `{"state","label","tone","gloss"}` where `state ∈ {"intact","digesting","cracking","insufficient"}`.
  - `compute_verdict(capex: dict, fund_df: pd.DataFrame, chips: list) -> dict` (same return).

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_capex.py`:

```python
from lib.capex import pulse_verdict, compute_verdict


def test_verdict_insufficient_when_no_gap():
    v = pulse_verdict(False, 0.0, False, False)
    assert v["state"] == "insufficient" and v["label"] == "INSUFFICIENT DATA"


def test_verdict_intact_when_gap_nonneg_and_calm():
    assert pulse_verdict(True, 0.0, False, False)["state"] == "intact"   # boundary gap == 0
    assert pulse_verdict(True, 5.0, False, False)["state"] == "intact"


def test_verdict_digesting_when_gap_negative_but_revenue_holds():
    v = pulse_verdict(True, -18.6, False, False)
    assert v["state"] == "digesting" and v["tone"] == "watch"


def test_verdict_cracking_via_fragile_red():
    assert pulse_verdict(True, 5.0, False, True)["state"] == "cracking"


def test_verdict_cracking_via_negative_gap_and_falling_revenue():
    assert pulse_verdict(True, -3.0, True, False)["state"] == "cracking"


def test_compute_verdict_fragile_red_forces_cracking():
    fund = fundamentals_history(GAP_REPORTS)
    capex = parse_capex({
        "core_spenders": ["MSFT", "GOOG"], "fragile_tier": ["CRWV"],
        "beneficiaries": ["NVDA", "MU"],
        "series": {
            "MSFT": [{"cq": "2025Q1", "reported": "2025-04-30", "capex_usd_b": 10.0},
                     {"cq": "2026Q1", "reported": "2026-05-01", "capex_usd_b": 15.0}],
            "GOOG": [{"cq": "2025Q1", "reported": "2025-04-24", "capex_usd_b": 10.0},
                     {"cq": "2026Q1", "reported": "2026-04-28", "capex_usd_b": 19.0}],
            "CRWV": [{"cq": "2026Q1", "reported": "2026-05-14", "capex_usd_b": 9.9,
                      "flag": "red"}],
        },
    })
    chips = build_chips(capex, fund, _date(2026, 7, 3))
    assert compute_verdict(capex, fund, chips)["state"] == "cracking"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_capex.py -k verdict -v`
Expected: FAIL with `ImportError: cannot import name 'pulse_verdict'`.

- [ ] **Step 3: Implement both functions**

Add to `lib/capex.py` (after `build_chips`):

```python
_VERDICT = {
    "intact": ("INTACT", "good",
               "Revenue is keeping pace with the spending it's built on — cycle looks intact."),
    "digesting": ("DIGESTING", "watch",
                  "Spending is outrunning the revenue it produces — the cycle is still "
                  "growing, but the gap bears watching."),
    "cracking": ("CRACKING", "stress",
                 "The spend/revenue gap is opening while demand or the fragile name is "
                 "under stress — treat as an early crack."),
    "insufficient": ("INSUFFICIENT DATA", "neutral",
                     "Not enough complete capex quarters yet — showing the signals we have."),
}


def pulse_verdict(gap_available: bool, gap_pp: float,
                  rev_falling: bool, fragile_red: bool) -> dict:
    """One headline read for the band, from the digestion axis (gap + revenue +
    fragile). Valuation is narrated in the band copy but never sets the state.

    A documented presentation rule, NOT a calibrated signal — nothing here feeds
    the scenario odds.
    """
    if not gap_available:
        state = "insufficient"
    elif fragile_red or (gap_pp < 0 and rev_falling):
        state = "cracking"
    elif gap_pp >= 0 and not rev_falling and not fragile_red:
        state = "intact"
    else:
        state = "digesting"
    label, tone, gloss = _VERDICT[state]
    return {"state": state, "label": label, "tone": tone, "gloss": gloss}


def compute_verdict(capex: dict, fund_df: pd.DataFrame, chips: list) -> dict:
    """Wire the band's own chips into ``pulse_verdict`` — the single testable
    entry point. Reuses the rev/fragile chip tones so the verdict can never
    disagree with the chips it summarizes.
    """
    gaps = coverage_gap_series(capex, fund_df)
    gap_pp = gaps[-1]["gap_pp"] if gaps else 0.0
    by_key = {c["key"]: c for c in chips}
    rev_falling = by_key.get("rev", {}).get("tone") == "watch"
    fragile_red = by_key.get("fragile", {}).get("tone") == "stress"
    return pulse_verdict(bool(gaps), gap_pp, rev_falling, fragile_red)
```

- [ ] **Step 4: Run tests to verify pass**

Run: `python -m pytest tests/test_capex.py -k verdict -v`
Expected: PASS (6 tests).

- [ ] **Step 5: Commit**

```bash
git add lib/capex.py tests/test_capex.py
git commit -m "feat(capex): add auto-derived pulse verdict (intact/digesting/cracking)"
```
(+ standard trailer)

---

### Task 3: `forward_revenue_note` (replaces the contradictory second gap)

Report where beneficiary revenue has moved *since* the quarter's anchored figure, as a forward hint — never a second gap subtracted from a quarter-old capex number. Leave `current_read` in place for now (the component still calls it; removed in Task 5).

**Files:**
- Modify: `lib/capex.py`
- Test: `tests/test_capex.py`

**Interfaces:**
- Consumes: `coverage_gap_series`, `_median_rev_growth`, `REV_FLAT_PP`.
- Produces: `forward_revenue_note(capex: dict, fund_df: pd.DataFrame) -> dict | None` returning `{"now_pct": float, "now_asof": str, "direction": "risen"|"fallen", "hint": "narrow"|"widen"}`, or `None` when there is no fresher report or the move is within `±REV_FLAT_PP`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_capex.py`:

```python
from lib.capex import forward_revenue_note


def test_forward_note_risen_since_quarter_says_narrow():
    reports = {
        "2026-05-02": _report({"NVDA": {"valuation": {"revenue_growth_pct": 55.0}},
                               "MU": {"valuation": {"revenue_growth_pct": 45.0}}}),
        "2026-07-01": _report({"NVDA": {"valuation": {"revenue_growth_pct": 95.0}},
                               "MU": {"valuation": {"revenue_growth_pct": 75.0}}}),
    }
    note = forward_revenue_note(_capex_with_yoy(), fundamentals_history(reports))
    assert note["direction"] == "risen" and note["hint"] == "narrow"
    assert note["now_asof"] == "2026-07-01" and note["now_pct"] == 85.0  # median(95,75)


def test_forward_note_fallen_since_quarter_says_widen():
    # GAP_REPORTS: anchored median at 05-02 is 60; latest 07-01 median is 50 → fell
    note = forward_revenue_note(_capex_with_yoy(), fundamentals_history(GAP_REPORTS))
    assert note["direction"] == "fallen" and note["hint"] == "widen"


def test_forward_note_none_when_no_fresher_report():
    reports = {
        "2026-05-02": _report({"NVDA": {"valuation": {"revenue_growth_pct": 80.0}},
                               "MU": {"valuation": {"revenue_growth_pct": 40.0}}}),
    }
    assert forward_revenue_note(_capex_with_yoy(), fundamentals_history(reports)) is None


def test_forward_note_none_when_move_is_flat():
    reports = {
        "2026-05-02": _report({"NVDA": {"valuation": {"revenue_growth_pct": 80.0}},
                               "MU": {"valuation": {"revenue_growth_pct": 40.0}}}),
        "2026-07-01": _report({"NVDA": {"valuation": {"revenue_growth_pct": 80.2}},
                               "MU": {"valuation": {"revenue_growth_pct": 40.1}}}),
    }
    assert forward_revenue_note(_capex_with_yoy(), fundamentals_history(reports)) is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_capex.py -k forward_note -v`
Expected: FAIL with `ImportError: cannot import name 'forward_revenue_note'`.

- [ ] **Step 3: Implement the function**

Add to `lib/capex.py` (after `current_read`):

```python
def forward_revenue_note(capex: dict, fund_df: pd.DataFrame) -> dict | None:
    """Where beneficiary revenue has moved SINCE the quarter's anchored figure —
    a forward hint, not a gap.

    The coverage gap anchors revenue to the date the quarter's capex was reported.
    This reports the latest beneficiary median relative to that anchor, so the
    band can say "revenue has since risen/fallen — next gap may narrow/widen"
    without subtracting today's revenue from a quarter-old capex number (which is
    what produced the old, contradictory second gap). ``None`` when there is no
    fresher report or the move is within ``±REV_FLAT_PP``.
    """
    gaps = coverage_gap_series(capex, fund_df)
    if not gaps:
        return None
    anchor_pct = gaps[-1]["rev_growth_pct"]
    anchor_date = gaps[-1]["rev_asof"]
    live = _median_rev_growth(fund_df, capex["beneficiaries"])
    if live is None:
        return None
    now_date, now_med = live
    if now_date <= anchor_date:
        return None
    now_med = round(now_med, 1)
    delta = now_med - anchor_pct
    if delta >= REV_FLAT_PP:
        direction, hint = "risen", "narrow"
    elif delta <= -REV_FLAT_PP:
        direction, hint = "fallen", "widen"
    else:
        return None
    return {"now_pct": now_med, "now_asof": now_date,
            "direction": direction, "hint": hint}
```

- [ ] **Step 4: Run tests to verify pass**

Run: `python -m pytest tests/test_capex.py -k forward_note -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add lib/capex.py tests/test_capex.py
git commit -m "feat(capex): add forward_revenue_note (then->now hint, not a 2nd gap)"
```
(+ standard trailer)

---

### Task 4: Cut the band over — verdict line, hero gap, keyed signal list

Rewrite the component: verdict band on top, coverage gap as an accented hero row with dated anchor + forward note, the other four as a legible keyed list with the health/direction color model. Stops using `current_read`, `_chips_html`, `_STATE_GLYPH`, `_STATE_COLOR` (all deleted here). Chips still carry the transitional `state`, now unread.

**Files:**
- Modify: `components/briefing/capex_pulse.py` (full rewrite below)
- Test: `tests/test_capex_pulse.py` (full rewrite below)

**Interfaces:**
- Consumes: `build_chips`, `compute_verdict`, `forward_revenue_note`, `coverage_gap_series`, `curation_age_days`, `CURATION_OVERDUE_DAYS`, `parse_capex`, `fundamentals_history` (via cache), `_escape_dollars`, chart helpers, color constants `STATUS_POS/WARN/NEG`, `INK_FALLBACK`, `CHART_ACCENT`, `CHART_LINE`, `CHART_PALETTE`.
- Produces: pure HTML helpers `_dot`, `_overdue_html`, `_verdict_html`, `_hero_gap_html`, `_signals_html` (unit-tested); `render_capex_pulse` composition. `_gap_chart_frame`, `_gap_fig`, `_cluster_medians`, `_trend_fig`, `_fundamentals_cached` unchanged.

- [ ] **Step 1: Write the failing tests (full new test file)**

Replace the entire contents of `tests/test_capex_pulse.py` with:

```python
"""Tests for the AI Capex Pulse band's pure HTML/frame helpers."""
import pandas as pd

from components.briefing.capex_pulse import (_cluster_medians, _gap_chart_frame,
                                             _hero_gap_html, _overdue_html,
                                             _signals_html, _verdict_html)
from lib.capex import CURATION_OVERDUE_DAYS


GAP_CHIP = {"key": "gap", "label": "Coverage gap",
            "sub": "beneficiary revenue growth minus capex growth",
            "tone": "watch", "arrow": "none",
            "detail": "-18.6pp (rev +50.3% − capex +68.9%) — negative and widening & <script>",
            "asof": "2026Q1"}

SIGNALS = [
    {"key": "capex", "label": "Capex", "sub": "combined MSFT/GOOG capex",
     "tone": "neutral", "arrow": "up",
     "detail": "core YoY +68.9% vs +61.9% prior — accelerating", "asof": "2026Q1"},
    {"key": "rev", "label": "Beneficiary revenue", "sub": "median sales growth",
     "tone": "good", "arrow": "up", "detail": "median +85.2% — rising",
     "asof": "2026-07-03"},
]


def test_verdict_html_renders_label_and_gloss_and_escapes():
    html = _verdict_html({"state": "digesting", "label": "DIGESTING",
                          "tone": "watch", "gloss": "watch the gap <script>"})
    assert "DIGESTING" in html and "watch the gap" in html
    assert "<script>" not in html and "&lt;script&gt;" in html


def test_hero_gap_html_shows_asof_and_forward_note():
    note = {"now_pct": 85.2, "now_asof": "2026-07-03",
            "direction": "risen", "hint": "narrow"}
    html = _hero_gap_html(GAP_CHIP, note)
    assert "as of 2026Q1 earnings" in html
    assert "risen to +85.2%" in html and "may narrow" in html
    assert "<script>" not in html          # detail HTML-escaped


def test_hero_gap_html_omits_note_when_none():
    assert "↳" not in _hero_gap_html(GAP_CHIP, None)


def test_signals_html_renders_arrows_labels_sublabels_and_key():
    html = _signals_html(SIGNALS)
    assert "Capex" in html and "▲" in html
    assert "median sales growth" in html          # sublabel present
    assert "healthy" in html and "direction only" in html   # key row


def test_overdue_html_only_past_threshold():
    assert _overdue_html(30) == ""
    assert "CURATION OVERDUE" in _overdue_html(CURATION_OVERDUE_DAYS + 1)


def test_gap_chart_frame_columns():
    df = _gap_chart_frame([{"cq": "2026Q1", "capex_yoy_pct": 68.9,
                            "rev_growth_pct": 58.9, "gap_pp": -10.0,
                            "rev_asof": "2026-05-02"}])
    assert list(df.columns) == ["quarter", "capex_yoy_pct", "rev_growth_pct", "gap_pp"]
    assert df.iloc[0]["quarter"] == "2026Q1"


def test_cluster_medians_pivots_by_cluster():
    fund = pd.DataFrame([
        {"date": "2026-06-01", "ticker": "NVDA", "cluster": "Semis",
         "revenue_growth_pct": 80.0},
        {"date": "2026-06-01", "ticker": "MU", "cluster": "Semis",
         "revenue_growth_pct": 40.0},
        {"date": "2026-06-01", "ticker": "D05_SI", "cluster": "SG Banks",
         "revenue_growth_pct": 5.0},
        {"date": "2026-06-01", "ticker": "X", "cluster": "",
         "revenue_growth_pct": 1.0},
    ])
    piv = _cluster_medians(fund, "revenue_growth_pct")
    assert piv.loc["2026-06-01", "Semis"] == 60.0
    assert piv.loc["2026-06-01", "SG Banks"] == 5.0
    assert "" not in piv.columns


def test_cluster_medians_empty_metric():
    piv = _cluster_medians(pd.DataFrame(columns=["date", "cluster", "forward_pe"]),
                           "forward_pe")
    assert piv.empty
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_capex_pulse.py -v`
Expected: FAIL with `ImportError: cannot import name '_verdict_html'`.

- [ ] **Step 3: Rewrite the component (full file)**

Replace the entire contents of `components/briefing/capex_pulse.py` with:

```python
"""Briefing · AI Capex Pulse band.

Human-read digestion scorecard for the capex cycle (spec
docs/superpowers/specs/2026-07-03-capex-pulse-redesign-design.md): an
auto-derived verdict line, the coverage gap as a dated hero with a forward
note, the four remaining signals as a keyed list (color = health, arrow =
direction), then the coverage-gap chart and cluster-fundamentals trends. By
design a cross-check the reader eyeballs against the scenario odds — nothing
here feeds the odds mechanically.
"""
from __future__ import annotations

from datetime import date as _date

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from lib.capex import (CURATION_OVERDUE_DAYS, build_chips, compute_verdict,
                       coverage_gap_series, curation_age_days,
                       forward_revenue_note, fundamentals_history, parse_capex)
from lib.cards import render_section_head
from lib.charts import (CHART_ACCENT, CHART_LINE, CHART_PALETTE, INK_FALLBACK,
                        PLOTLY_CONFIG, STATUS_NEG, STATUS_POS, STATUS_WARN,
                        chart_data_table, style_fig)
from lib.data_loader import data_fingerprint, load_all_reports, load_capex_quarterly
from lib.formatters import _escape_dollars

_TONE_COLOR = {"good": STATUS_POS, "watch": STATUS_WARN, "stress": STATUS_NEG,
               "neutral": INK_FALLBACK, "na": INK_FALLBACK}
_ARROW = {"up": "▲", "down": "▼", "none": ""}

_TREND_METRICS = [("revenue_growth_pct", "Revenue growth %"),
                  ("earnings_growth_pct", "Earnings growth %"),
                  ("fcf_yield_pct", "FCF yield %"),
                  ("forward_pe", "Forward P/E")]


@st.cache_data(show_spinner=False, max_entries=2)
def _fundamentals_cached(cache_key: tuple, _reports: dict) -> pd.DataFrame:
    """Corpus-derived fundamentals frame, memoized on the cheap fingerprint.

    Same contract as the Signal-Tracker derives (review P7-2): ``cache_key`` is
    ``data_fingerprint()``; the heavy corpus is ``_``-prefixed so it is never
    hashed.
    """
    return fundamentals_history(_reports)


def _dot(tone: str) -> str:
    """Inline health dot — the one place tone becomes a color."""
    c = _TONE_COLOR.get(tone, INK_FALLBACK)
    return (f'<span style="display:inline-block;width:8px;height:8px;'
            f'border-radius:50%;background:{c};margin-right:6px;'
            f'vertical-align:middle;"></span>')


def _overdue_html(overdue_days: int | None) -> str:
    """Curation-overdue banner, or '' when the file is fresh enough."""
    if overdue_days is None or overdue_days <= CURATION_OVERDUE_DAYS:
        return ""
    return (f'<div style="margin:0 0 8px;font-family:var(--mono);font-size:11px;'
            f'color:{STATUS_WARN};">⚠ CURATION OVERDUE — newest core capex row '
            f'is {overdue_days}d old; a newer quarter has likely been reported. '
            f'Update data/capex_quarterly.json.</div>')


def _verdict_html(verdict: dict) -> str:
    """The headline read: colored dot + STATE + one-sentence gloss."""
    color = _TONE_COLOR.get(verdict["tone"], INK_FALLBACK)
    return (
        f'<div style="display:flex;align-items:baseline;gap:8px;padding:10px 12px;'
        f'border:1px solid var(--rule);border-left:3px solid {color};margin:0 0 10px;">'
        f'<span style="font-family:var(--mono);font-size:12px;font-weight:700;'
        f'letter-spacing:0.08em;color:{color};white-space:nowrap;">'
        f'{_dot(verdict["tone"])}{_escape_dollars(verdict["label"])}</span>'
        f'<span style="font-size:12.5px;color:var(--ink-2);line-height:1.45;">'
        f'{_escape_dollars(verdict["gloss"])}</span></div>')


def _hero_gap_html(gap: dict, note: dict | None) -> str:
    """Coverage gap as the accented hero: one dated number + optional forward note."""
    color = _TONE_COLOR.get(gap["tone"], INK_FALLBACK)
    asof = (f'<span style="font-family:var(--mono);font-size:10px;'
            f'color:var(--ink-3);">as of {_escape_dollars(gap["asof"])} earnings</span>'
            if gap["asof"] != "—" else "")
    fwd = ""
    if note is not None:
        fwd = (f'<div style="margin-top:4px;font-size:11.5px;color:var(--ink-3);">'
               f'↳ revenue has since {note["direction"]} to {note["now_pct"]:+.1f}% '
               f'({note["now_asof"]}); the matching capex quarter is not reported '
               f'yet, so the next gap may {note["hint"]}.</div>')
    return (
        f'<div style="padding:10px 12px;border:1px solid var(--rule);'
        f'border-left:3px solid {color};margin:0 0 8px;">'
        f'<div style="font-family:var(--mono);font-size:10px;letter-spacing:0.08em;'
        f'text-transform:uppercase;color:var(--ink-3);">'
        f'{_escape_dollars(gap["label"])} · {_escape_dollars(gap["sub"])}</div>'
        f'<div style="margin-top:3px;font-size:13px;color:var(--ink-2);">'
        f'{_dot(gap["tone"])}{_escape_dollars(gap["detail"])} &nbsp;{asof}</div>'
        f'{fwd}</div>')


def _signals_html(chips: list) -> str:
    """The non-gap signals as a legible keyed row (dot + label + arrow + detail + sub)."""
    cells = ""
    for c in chips:
        color = _TONE_COLOR.get(c["tone"], INK_FALLBACK)
        arrow = _ARROW.get(c["arrow"], "")
        arrow_s = (f'<span style="color:{color};font-weight:600;">{arrow}</span> '
                   if arrow else "")
        cells += (
            f'<div style="flex:1 1 200px;min-width:190px;padding:8px 10px;'
            f'border:1px solid var(--rule);border-left:3px solid {color};">'
            f'<div style="font-family:var(--mono);font-size:10px;'
            f'letter-spacing:0.06em;text-transform:uppercase;color:var(--ink-3);">'
            f'{_dot(c["tone"])}{_escape_dollars(c["label"])} · {_escape_dollars(c["asof"])}</div>'
            f'<div style="margin-top:3px;font-size:12.5px;color:var(--ink-2);'
            f'line-height:1.4;">{arrow_s}{_escape_dollars(c["detail"])}</div>'
            f'<div style="margin-top:2px;font-size:10.5px;color:var(--ink-3);'
            f'line-height:1.35;">{_escape_dollars(c["sub"])}</div></div>')
    key = (
        '<div style="margin-top:6px;font-family:var(--mono);font-size:10px;'
        'color:var(--ink-3);">'
        f'<span style="color:{STATUS_POS};">●</span> healthy · '
        f'<span style="color:{STATUS_WARN};">●</span> watch · '
        f'<span style="color:{STATUS_NEG};">●</span> stress &nbsp;&nbsp;'
        '▲▼ = direction only</div>')
    return f'<div style="display:flex;flex-wrap:wrap;gap:8px;">{cells}</div>{key}'


def _gap_chart_frame(gap_rows: list) -> pd.DataFrame:
    """The exact frame behind the gap chart (also the a11y table)."""
    return pd.DataFrame(
        [{"quarter": g["cq"], "capex_yoy_pct": g["capex_yoy_pct"],
          "rev_growth_pct": g["rev_growth_pct"], "gap_pp": g["gap_pp"]}
         for g in gap_rows],
        columns=["quarter", "capex_yoy_pct", "rev_growth_pct", "gap_pp"])


def _gap_fig(df: pd.DataFrame):
    fig = go.Figure()
    fig.add_bar(x=df["quarter"], y=df["gap_pp"], name="Coverage gap (pp)",
                marker_color=[STATUS_POS if v >= 0 else STATUS_NEG
                              for v in df["gap_pp"]])
    fig.add_scatter(x=df["quarter"], y=df["capex_yoy_pct"],
                    name="Core capex YoY %", mode="lines+markers",
                    line=dict(color=CHART_LINE))
    fig.add_scatter(x=df["quarter"], y=df["rev_growth_pct"],
                    name="Beneficiary revenue growth %", mode="lines+markers",
                    line=dict(color=CHART_ACCENT))
    fig.update_layout(height=260, margin=dict(l=0, r=0, t=10, b=0),
                      legend=dict(orientation="h", yanchor="bottom", y=1.02))
    return style_fig(fig)


def _cluster_medians(fund_df: pd.DataFrame, metric: str) -> pd.DataFrame:
    """dates × clusters pivot of per-cluster medians for *metric*."""
    if fund_df.empty:
        return pd.DataFrame()
    df = fund_df[fund_df["cluster"] != ""].dropna(subset=[metric])
    if df.empty:
        return pd.DataFrame()
    return df.groupby(["date", "cluster"])[metric].median().unstack("cluster")


def _trend_fig(pivot: pd.DataFrame):
    fig = go.Figure()
    for i, cluster in enumerate(pivot.columns):
        fig.add_scatter(x=list(pivot.index), y=pivot[cluster], mode="lines",
                        name=str(cluster),
                        line=dict(color=CHART_PALETTE[i % len(CHART_PALETTE)],
                                  width=1.6))
    fig.update_layout(height=220, margin=dict(l=0, r=0, t=10, b=0),
                      legend=dict(orientation="h", yanchor="bottom", y=1.02))
    return style_fig(fig)


def render_capex_pulse() -> None:
    """The AI Capex Pulse band (Briefing). Degrades chip-by-chip, never crashes."""
    capex = parse_capex(load_capex_quarterly())
    fund_df = _fundamentals_cached(data_fingerprint(), load_all_reports())
    if not capex["series"] and fund_df.empty:
        return
    today = _date.today()
    render_section_head(
        "AI Capex Pulse",
        "Digestion cross-check — human-read, not a wired signal")
    for w in capex["warnings"]:
        st.caption(f"⚠ capex file: {w}")
    chips = build_chips(capex, fund_df, today)
    by_key = {c["key"]: c for c in chips}
    verdict = compute_verdict(capex, fund_df, chips)
    note = forward_revenue_note(capex, fund_df)
    st.markdown(
        "".join([
            _overdue_html(curation_age_days(capex, today)),
            _verdict_html(verdict),
            _hero_gap_html(by_key["gap"], note),
            _signals_html([by_key[k] for k in ("capex", "rev", "val", "fragile")]),
        ]),
        unsafe_allow_html=True)
    gaps = coverage_gap_series(capex, fund_df)
    if gaps:
        df = _gap_chart_frame(gaps)
        st.plotly_chart(_gap_fig(df), use_container_width=True,
                        config=PLOTLY_CONFIG)
        chart_data_table(df)
    if not fund_df.empty:
        with st.expander("Cluster fundamentals over time"):
            for metric, label in _TREND_METRICS:
                pivot = _cluster_medians(fund_df, metric)
                if pivot.empty:
                    continue
                st.markdown(
                    f'<div style="font-family:var(--mono);font-size:10px;'
                    f'letter-spacing:0.1em;text-transform:uppercase;'
                    f'color:var(--ink-3);margin:8px 0 2px;">{label}</div>',
                    unsafe_allow_html=True)
                st.plotly_chart(_trend_fig(pivot), use_container_width=True,
                                config=PLOTLY_CONFIG)
                chart_data_table(pivot.reset_index())
```

- [ ] **Step 4: Run the component tests + the full suite**

Run: `python -m pytest tests/test_capex_pulse.py tests/test_capex.py -v`
Expected: PASS (all component helper tests + all lib tests; the old `test_chips_html_*` tests are gone, replaced by verdict/hero/signals/overdue tests).

- [ ] **Step 5: Commit**

```bash
git add components/briefing/capex_pulse.py tests/test_capex_pulse.py
git commit -m "feat(capex): redesign band — verdict line, hero gap, health/direction colors"
```
(+ standard trailer)

---

### Task 5: Retire the transitional `state` field and `current_read`

Now that nothing reads them, delete the dead code and migrate the `state`-asserting tests to `tone`/`arrow`.

**Files:**
- Modify: `lib/capex.py`
- Modify: `tests/test_capex.py`

**Interfaces:**
- Consumes: nothing new.
- Produces: chip dicts no longer contain `state`; `current_read` no longer exists.

- [ ] **Step 1: Migrate the `state`-based test assertions**

In `tests/test_capex.py`, make these exact edits:

Change in `test_chips_always_five_in_order_even_on_empty_inputs`:
```python
    assert all(c["state"] == "na" for c in chips)
```
to:
```python
    assert all(c["tone"] == "na" for c in chips)
```

Change in `test_capex_chip_accelerating_at_threshold`:
```python
    assert _chip(chips, "capex")["state"] == "accel"       # +2.0pp = ACCEL_PP
```
to:
```python
    c = _chip(chips, "capex")
    assert c["tone"] == "neutral" and c["arrow"] == "up"   # +2.0pp = ACCEL_PP
```

Change in `test_capex_chip_decelerating_warns`:
```python
    assert c["state"] == "warn" and "decelerating" in c["detail"]
```
to:
```python
    assert c["tone"] == "neutral" and c["arrow"] == "down" and "decelerating" in c["detail"]
```

Change in `test_gap_chip_warns_when_negative`:
```python
    assert _chip(chips, "gap")["state"] == "warn"     # rev ~60 < capex 70
```
to:
```python
    assert _chip(chips, "gap")["tone"] == "watch"     # rev ~60 < capex 70
```

Change in `test_rev_chip_falling_warns`:
```python
    assert c["state"] == "warn" and "falling" in c["detail"]
```
to:
```python
    assert c["tone"] == "watch" and "falling" in c["detail"]
```

Change in `test_valuation_chip_needs_five_reports`:
```python
    assert _chip(chips, "val")["state"] == "na"
```
to:
```python
    assert _chip(chips, "val")["tone"] == "na"
```

Change in `test_fragile_chip_surfaces_flag_and_note`:
```python
    assert c["state"] == "warn"
```
to:
```python
    assert c["tone"] == "watch"
```

Delete the two `current_read` tests entirely (`test_current_read_uses_latest_report` and `test_current_read_none_without_yoy`), and change the import line:
```python
from lib.capex import coverage_gap_series, current_read
```
to:
```python
from lib.capex import coverage_gap_series
```

- [ ] **Step 2: Remove `state` from the chips and delete `current_read`**

In `lib/capex.py`, in each of the five chip functions, delete every `"state": ...,` entry from the returned dicts, and drop `state` from the tuple assignments where present. Concretely:

- `_capex_chip`: remove `"state": "na",` (na branch) and `"state": state,` (main branch); change the three assignments to `arrow, word = "up", "accelerating"` / `arrow, word = "down", "decelerating"` / `arrow, word = "none", "steady"`.
- `_gap_chip`: remove `"state": "na",` and `"state": state,`; change assignments to `tone = "watch"` (negative branch), `tone, word = "watch", "narrowing fast"` (widening branch), `tone, word = "good", "revenue keeping pace"` (else branch).
- `_rev_chip`: remove all three `"state": ...` dict entries; change the trend assignments to `tone, arrow, word = "good", "up", "rising"` / `"watch", "down", "falling"` / `"good", "none", "flat"`.
- `_val_chip`: remove the `"state": "na",` entry and the `"state": "warn" if rich else "ok",` entry.
- `_fragile_chip`: remove the `"state": "na",` entry and the `"state": "warn" if flag in severity else "ok",` entry.

Then delete the entire `current_read` function.

- [ ] **Step 3: Verify no `state`/`current_read` references remain in the capex code**

Run: `python -m pytest tests/test_capex.py tests/test_capex_pulse.py -v`
Expected: PASS (all green).

Then confirm the dead names are gone (should print nothing):
Run: `grep -rn "current_read\|\"state\"" lib/capex.py components/briefing/capex_pulse.py`
Expected: no output.

- [ ] **Step 4: Commit**

```bash
git add lib/capex.py tests/test_capex.py
git commit -m "refactor(capex): drop transitional state field and current_read"
```
(+ standard trailer)

---

### Task 6: Assert the verdict renders in the Briefing page-walk

Extend the existing AppTest so the page-walk guards the new verdict line, not just the band title.

**Files:**
- Modify: `tests/test_app_pages.py`

**Interfaces:**
- Consumes: existing `_boot()` helper and the `test_briefing_renders_capex_pulse_band` pattern.
- Produces: a stronger assertion that exactly one verdict label renders.

- [ ] **Step 1: Add the failing assertion**

In `tests/test_app_pages.py`, add this test just below `test_briefing_renders_capex_pulse_band`:

```python
def test_briefing_capex_pulse_shows_a_verdict():
    at = _boot()
    assert not at.exception
    page = " ".join(str(m.value) for m in at.markdown)
    assert any(v in page for v in
               ("INTACT", "DIGESTING", "CRACKING", "INSUFFICIENT DATA"))
```

- [ ] **Step 2: Run it**

Run: `python -m pytest tests/test_app_pages.py::test_briefing_capex_pulse_shows_a_verdict -v`
Expected: PASS (the seeded data renders one verdict; today that is `DIGESTING`). If this fails with no exception but no verdict word, the band's data is fully degraded — check `data/capex_quarterly.json` loaded.

- [ ] **Step 3: Run the whole suite**

Run: `python -m pytest -q`
Expected: PASS (full suite green).

- [ ] **Step 4: Commit**

```bash
git add tests/test_app_pages.py
git commit -m "test(capex): assert the pulse verdict renders on the Briefing"
```
(+ standard trailer)

---

## Self-Review

**1. Spec coverage:**
- Verdict line (spec §1) → Task 2 (`pulse_verdict`/`compute_verdict`), rendered Task 4, guarded Task 6. ✓
- One dated gap + forward note (spec §2) → Task 3 (`forward_revenue_note`), rendered as hero Task 4; old second gap deleted with `current_read` in Task 5. ✓
- Color = health, arrow = direction + sublabels (spec §3) → Task 1 (`tone`/`arrow`/`sub`), rendered Task 4. ✓
- UI composition order (spec §4) → Task 4 `render_capex_pulse`. ✓
- Honesty/degradation (spec §5): chips still five/ordered/explicit-na (Task 1 preserves), verdict → INSUFFICIENT DATA on missing gap (Task 2), forward note omitted when flat/no-fresher (Task 3), overdue tag preserved (Task 4 `_overdue_html`), `_escape_dollars` on all injected text (Task 4). ✓
- Testing (spec §6): pure-fn tests (Tasks 1–3, 5), component HTML tests (Task 4), page-walk (Task 6). ✓
- Files touched match spec's list (`lib/capex.py`, `components/briefing/capex_pulse.py`, `tests/test_capex.py`, `tests/test_capex_pulse.py`, plus `tests/test_app_pages.py` for the walk). ✓

**2. Placeholder scan:** No "TBD"/"TODO"/"handle edge cases"/"similar to". Every code step shows complete code; every test step shows the assertions. ✓

**3. Type consistency:** Chip dict keys (`key,label,sub,tone,arrow,detail,asof`) are consistent across Tasks 1/4/5. `pulse_verdict` returns `{state,label,tone,gloss}` — consumed by `_verdict_html` (Task 4) using `label`/`tone`/`gloss`. ✓ `forward_revenue_note` returns `{now_pct,now_asof,direction,hint}` — consumed by `_hero_gap_html` (Task 4) using all four. ✓ `compute_verdict(capex, fund_df, chips)` signature matches its call in `render_capex_pulse`. ✓ Tone vocabulary (`good/watch/stress/neutral/na`) is identical in `lib.capex` chips, `pulse_verdict`, and `_TONE_COLOR`. ✓
```
