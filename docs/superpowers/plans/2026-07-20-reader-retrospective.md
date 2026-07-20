# Reader Retrospective Page Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A new "Retrospective" dashboard page that tells, month by month, what calls the pipeline made and what happened to them — plain one-sentence verdicts derived from `data/signal_log.csv`, with a paper-book month line and the single-regime honesty banner always on top.

**Architecture:** All derivation lives in pure functions in a new `components/retrospective.py` (dedupe daily log rows into calls → classify each call from its own frozen 5/10/20-session window → group by calendar month). Rendering is templated HTML through `st.markdown(..., unsafe_allow_html=True)` using existing theme primitives plus a small `retro-*` CSS family. The page registers in `dashboard.py`'s `_PAGES` / `st.navigation` and the masthead nav list.

**Tech Stack:** Streamlit (local 1.50), pandas (local 1.4.2 — see constraints), pytest + `streamlit.testing.v1.AppTest`, existing visual-regression harness (Docker + Playwright).

**Spec:** `docs/superpowers/specs/2026-07-20-reader-retrospective-design.md` — read it before starting.

## Global Constraints

- Local env is base Anaconda with **pandas 1.4.2** — use only APIs that exist in 1.4 (no `include_groups`, no `DataFrame.map`). CI proves 2.x compat. Do NOT upgrade any package.
- Run tests as **`python -m pytest`** (module form — puts repo root on `sys.path`). The default run already excludes `tests/visual` via `addopts` in `pyproject.toml`.
- Ruff: line length 100, double quotes, isort-ordered imports (`E501` ignored but keep lines sane).
- Any function passed to `AppTest.from_function` must be **ASCII-only and self-contained** (imports + data inside the function body; no closures) — from_function rewrites the source through a locale-encoded temp file on Windows.
- No `date.today()` / `datetime.now()` in page content — visual baselines freeze `TEST_DATE`; all page text must derive from data files only.
- Every `$` reaching injected HTML must be the entity `&#36;` (or pass through `lib.formatters._escape_dollars`) so Streamlit never parses it as LaTeX; report-derived text must go through `_escape_dollars`.
- Commit after every task with the trailer lines:
  `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>` and
  `Claude-Session: https://claude.ai/code/session_01FpRBpwwKC4dLYSU8bWBZmo`
  (embedded quotes in PowerShell 5.1 shatter args — write the message to a temp file and use `git commit -F`, or run git from Git Bash).
- The Streamlit dev server caches lazily-imported `_page_*` modules — restart it when manually verifying UI edits.

## Data contracts (read once, relied on everywhere)

`lib.data_loader.load_signal_log()` returns a DataFrame from `data/signal_log.csv` with:
- `date` parsed to datetime64; `entry_price, invalidation, upside_target, rr_ratio, price_after_5d/10d/20d` numeric (coerced);
- **derived** `return_5d / return_10d / return_20d` percent columns (computed in the loader);
- `hit_invalidation` / `hit_upside_target` as float 0.0 / 1.0 / NaN (NaN = call not matured);
- `signal` ∈ {BUY, ACCUMULATE, WATCH, CAUTION, AVOID, HOLD}; one row per ticker-day (consecutive same-signal days repeat).

`lib.data_loader.load_paper_nav()` returns the raw `data/paper_nav.csv` frame: `policy_id, date (str), nav_units, cash_units, n_positions, spy_close, soxx_close`. `components.paper_book.select_policy(nav_df, block)` picks the headline lane's rows (block = latest report's `paper_portfolio` dict), sorted by date; empty frame when nothing resolves.

Latest report dict may carry `calibration_insights.confidence_banner` (str) and `paper_portfolio` (dict).

---

### Task 1: `dedupe_calls` — one row per call

**Files:**
- Create: `components/retrospective.py`
- Create: `tests/test_retrospective.py`

**Interfaces:**
- Consumes: `load_signal_log()`-shaped DataFrame (see Data contracts).
- Produces: `dedupe_calls(log_df: pd.DataFrame) -> pd.DataFrame` — the first row of each consecutive same-`(ticker, signal)` run, filtered to BUY/ACCUMULATE/CAUTION/AVOID, index reset. Also module constants `_DIRECTIONAL = ("BUY", "ACCUMULATE", "CAUTION", "AVOID")` and `_LONG = ("BUY", "ACCUMULATE")` that later tasks import.

- [ ] **Step 1: Write the failing tests**

```python
"""Tests for the Retrospective page (spec 2026-07-20-reader-retrospective-design)."""
import pandas as pd

from components.retrospective import dedupe_calls


def _log(rows):
    """Minimal signal_log-shaped frame. rows = list of (date, ticker, signal)."""
    df = pd.DataFrame(rows, columns=["date", "ticker", "signal"])
    df["date"] = pd.to_datetime(df["date"])
    return df


def test_dedupe_collapses_consecutive_same_signal_run_to_first_row():
    calls = dedupe_calls(_log([
        ("2026-06-01", "AMD", "ACCUMULATE"),
        ("2026-06-02", "AMD", "ACCUMULATE"),
        ("2026-06-03", "AMD", "ACCUMULATE"),
    ]))
    assert len(calls) == 1
    assert calls.iloc[0]["date"] == pd.Timestamp("2026-06-01")


def test_dedupe_hold_gap_splits_runs_into_two_calls():
    calls = dedupe_calls(_log([
        ("2026-06-01", "AMD", "ACCUMULATE"),
        ("2026-06-02", "AMD", "HOLD"),
        ("2026-06-03", "AMD", "ACCUMULATE"),
    ]))
    assert len(calls) == 2
    assert list(calls["date"]) == [pd.Timestamp("2026-06-01"), pd.Timestamp("2026-06-03")]


def test_dedupe_filters_non_directional_signals():
    calls = dedupe_calls(_log([
        ("2026-06-01", "AMD", "HOLD"),
        ("2026-06-02", "NVDA", "WATCH"),
        ("2026-06-03", "TSM", "CAUTION"),
    ]))
    assert list(calls["signal"]) == ["CAUTION"]


def test_dedupe_is_per_ticker():
    calls = dedupe_calls(_log([
        ("2026-06-01", "AMD", "CAUTION"),
        ("2026-06-01", "NVDA", "CAUTION"),
    ]))
    assert len(calls) == 2


def test_dedupe_empty_frame_returns_empty():
    assert dedupe_calls(pd.DataFrame()).empty
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_retrospective.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'components.retrospective'` (or ImportError).

- [ ] **Step 3: Write the implementation**

Create `components/retrospective.py`:

```python
"""Retrospective page: monthly "what we called / what happened" narrative digest.

Spec: docs/superpowers/specs/2026-07-20-reader-retrospective-design.md
(MarketReport capability-gap survey 2026-07-19, item #8). Derives one-sentence
verdicts from the pipeline's exported call ledger (data/signal_log.csv).
Verdicts are frozen to each call's own 5/10/20-session outcome window — never
re-marked to the latest price — so a finished month's story never changes
afterwards. Retired tickers deliberately stay in: the page is about what we
*said*, and dropping bad old calls would be survivorship bias (deliberate
divergence from the Watchlist's RETIRED_TICKERS filter).
"""
from __future__ import annotations

import pandas as pd

_DIRECTIONAL = ("BUY", "ACCUMULATE", "CAUTION", "AVOID")
_LONG = ("BUY", "ACCUMULATE")


def dedupe_calls(log_df: pd.DataFrame) -> pd.DataFrame:
    """One row per *call*: the first row of each consecutive same-signal run
    per ticker, then directional calls only.

    The log repeats a signal daily while it stands; a HOLD/WATCH day between
    two ACCUMULATE days breaks the run (two distinct calls) — the same streak
    rule ``compute_signal_accuracy`` uses on the report corpus.
    """
    if log_df is None or log_df.empty or "signal" not in log_df.columns:
        return pd.DataFrame()
    df = log_df[log_df["signal"].notna()].sort_values(["ticker", "date"])
    first_of_run = df["signal"] != df.groupby("ticker")["signal"].shift()
    calls = df[first_of_run]
    return calls[calls["signal"].isin(_DIRECTIONAL)].reset_index(drop=True)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_retrospective.py -v`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add components/retrospective.py tests/test_retrospective.py
git commit -F <msgfile>   # "feat(retrospective): dedupe signal log into one row per call" + trailers
```

---

### Task 2: `classify_call` — verdict per call

**Files:**
- Modify: `components/retrospective.py`
- Modify: `tests/test_retrospective.py`

**Interfaces:**
- Consumes: one deduped call row (`pd.Series`) with `signal`, `return_20d`, `hit_upside_target`, `hit_invalidation`.
- Produces: `classify_call(row) -> tuple[str, str]` — `(bucket, outcome)` where bucket ∈ `{"worked", "failed", "pending"}` and outcome is a plain-text sentence tail (no HTML, no `$`).

- [ ] **Step 1: Write the failing tests** (append to `tests/test_retrospective.py`)

```python
from components.retrospective import classify_call


def _call(signal, ret20=None, hit_up=None, hit_stop=None):
    return pd.Series({
        "signal": signal,
        "return_20d": float("nan") if ret20 is None else ret20,
        "hit_upside_target": float("nan") if hit_up is None else hit_up,
        "hit_invalidation": float("nan") if hit_stop is None else hit_stop,
    })


def test_long_target_hit_is_worked():
    bucket, outcome = classify_call(_call("ACCUMULATE", ret20=16.4, hit_up=1.0, hit_stop=0.0))
    assert bucket == "worked"
    assert "hit its target" in outcome
    assert "+16.4%" in outcome


def test_long_stop_hit_is_failed():
    bucket, outcome = classify_call(_call("BUY", ret20=-5.6, hit_up=0.0, hit_stop=1.0))
    assert bucket == "failed"
    assert "stopped out" in outcome


def test_long_both_levels_hit_scores_by_20d_return_sign():
    bucket, outcome = classify_call(_call("BUY", ret20=3.0, hit_up=1.0, hit_stop=1.0))
    assert bucket == "worked"
    assert "both" in outcome
    bucket, _ = classify_call(_call("BUY", ret20=-3.0, hit_up=1.0, hit_stop=1.0))
    assert bucket == "failed"


def test_long_no_levels_hit_scores_by_return_sign():
    assert classify_call(_call("ACCUMULATE", ret20=2.0, hit_up=0.0, hit_stop=0.0))[0] == "worked"
    assert classify_call(_call("ACCUMULATE", ret20=-2.0, hit_up=0.0, hit_stop=0.0))[0] == "failed"


def test_long_flat_return_is_failed():
    # Mirrors the Signal Tracker scorecard: long calls are right only when price ROSE.
    assert classify_call(_call("BUY", ret20=0.0, hit_up=0.0, hit_stop=0.0))[0] == "failed"


def test_long_immature_is_pending():
    bucket, outcome = classify_call(_call("ACCUMULATE"))
    assert bucket == "pending"
    assert "too early" in outcome


def test_caution_drop_is_worked_rally_is_failed():
    bucket, outcome = classify_call(_call("CAUTION", ret20=-9.2))
    assert bucket == "worked"
    assert "staying out was right" in outcome
    assert "9.2%" in outcome
    bucket, outcome = classify_call(_call("AVOID", ret20=4.1))
    assert bucket == "failed"
    assert "rallied" in outcome


def test_caution_flat_counts_as_worked():
    # Scorecard scores avoid-mode with (return <= 0) as right; keep identical.
    assert classify_call(_call("CAUTION", ret20=0.0))[0] == "worked"


def test_caution_immature_is_pending():
    assert classify_call(_call("AVOID"))[0] == "pending"


def test_hit_flag_without_return_still_resolves():
    bucket, outcome = classify_call(_call("BUY", hit_up=1.0, hit_stop=0.0))
    assert bucket == "worked"
    assert "%" not in outcome  # no return available -> no percentage claimed
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_retrospective.py -v`
Expected: new tests FAIL with `ImportError: cannot import name 'classify_call'`.

- [ ] **Step 3: Write the implementation** (append to `components/retrospective.py`)

```python
def _flag(row, col: str) -> bool:
    """True when a 0/1/NaN hit-flag cell is exactly 1."""
    v = row.get(col)
    try:
        return pd.notna(v) and float(v) == 1.0
    except (TypeError, ValueError):
        return False


def _pct_sfx(ret) -> str:
    return f" ({ret:+.1f}%)" if ret is not None else ""


def classify_call(row) -> tuple[str, str]:
    """(bucket, plain-text outcome) for one deduped call row.

    bucket: "worked" | "failed" | "pending". Right/wrong mirrors the Signal
    Tracker scorecard exactly — long calls are right when price rose (>0),
    CAUTION/AVOID right when it fell or went nowhere (<=0) — so the two pages
    can never disagree on a verdict. Only the call's own window is consulted
    (hit flags + 20-session return); no re-marking to the latest price.
    """
    ret = row.get("return_20d")
    ret = None if ret is None or pd.isna(ret) else float(ret)

    if row["signal"] in _LONG:
        hit_up = _flag(row, "hit_upside_target")
        hit_stop = _flag(row, "hit_invalidation")
        if hit_up and hit_stop:
            if ret is None:
                return "pending", ("hit both its target and its stop — verdict pending "
                                   "the 20-session mark")
            bucket = "worked" if ret > 0 else "failed"
            return bucket, (f"hit both its target and its stop inside the window — "
                            f"finished {ret:+.1f}% after 20 sessions")
        if hit_up:
            return "worked", f"hit its target inside 20 sessions{_pct_sfx(ret)}"
        if hit_stop:
            return "failed", f"stopped out{_pct_sfx(ret)}"
        if ret is None:
            return "pending", "too early to judge"
        if ret > 0:
            return "worked", f"up {ret:+.1f}% after 20 sessions"
        return "failed", f"down {ret:+.1f}% after 20 sessions"

    # CAUTION / AVOID — a drop (or nothing) proves the call right
    if ret is None:
        return "pending", "too early to judge"
    if ret == 0:
        return "worked", "went nowhere — staying out cost nothing"
    if ret < 0:
        return "worked", f"fell {abs(ret):.1f}% — staying out was right"
    return "failed", f"rallied {ret:+.1f}% instead"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_retrospective.py -v`
Expected: all pass (16 total).

- [ ] **Step 5: Commit**

```bash
git add components/retrospective.py tests/test_retrospective.py
git commit -F <msgfile>   # "feat(retrospective): classify calls into worked/failed/pending" + trailers
```

---

### Task 3: month grouping — `month_label` + `build_month_digest`

**Files:**
- Modify: `components/retrospective.py`
- Modify: `tests/test_retrospective.py`

**Interfaces:**
- Consumes: `dedupe_calls` output; `classify_call`.
- Produces:
  - `month_label(key: str) -> str` — `"2026-07"` → `"July 2026"`.
  - `build_month_digest(calls: pd.DataFrame, month: str) -> dict` with keys `month` (str `"YYYY-MM"`), `n_calls` (int), `n_resolved` (int), `n_worked` (int), `groups` (`dict[str, list[tuple[pd.Series, str]]]` keyed `"worked"/"failed"/"pending"`, values `(row, outcome)` in date order).

- [ ] **Step 1: Write the failing tests** (append)

```python
from components.retrospective import build_month_digest, month_label


def test_month_label():
    assert month_label("2026-07") == "July 2026"


def _calls_frame():
    df = pd.DataFrame({
        "date": pd.to_datetime(["2026-06-05", "2026-06-20", "2026-07-02"]),
        "ticker": ["AMD", "NVDA", "TSM"],
        "signal": ["ACCUMULATE", "CAUTION", "BUY"],
        "return_20d": [12.0, 3.0, float("nan")],
        "hit_upside_target": [1.0, float("nan"), float("nan")],
        "hit_invalidation": [0.0, float("nan"), float("nan")],
    })
    return df


def test_build_month_digest_filters_to_month_and_counts():
    d = build_month_digest(_calls_frame(), "2026-06")
    assert d["month"] == "2026-06"
    assert d["n_calls"] == 2
    assert d["n_resolved"] == 2          # AMD worked, NVDA failed
    assert d["n_worked"] == 1
    assert [r["ticker"] for r, _ in d["groups"]["worked"]] == ["AMD"]
    assert [r["ticker"] for r, _ in d["groups"]["failed"]] == ["NVDA"]
    assert d["groups"]["pending"] == []


def test_build_month_digest_pending_only_month():
    d = build_month_digest(_calls_frame(), "2026-07")
    assert d["n_calls"] == 1
    assert d["n_resolved"] == 0
    assert [r["ticker"] for r, _ in d["groups"]["pending"]] == ["TSM"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_retrospective.py -v`
Expected: ImportError on `build_month_digest`.

- [ ] **Step 3: Write the implementation** (append)

```python
def month_label(key: str) -> str:
    """'2026-07' -> 'July 2026'."""
    return pd.Timestamp(f"{key}-01").strftime("%B %Y")


def build_month_digest(calls: pd.DataFrame, month: str) -> dict:
    """Classified calls + headline stats for one 'YYYY-MM' month."""
    rows = calls[calls["date"].dt.strftime("%Y-%m") == month].sort_values("date")
    groups: dict[str, list] = {"worked": [], "failed": [], "pending": []}
    for _, row in rows.iterrows():
        bucket, outcome = classify_call(row)
        groups[bucket].append((row, outcome))
    resolved = len(groups["worked"]) + len(groups["failed"])
    return {"month": month, "n_calls": len(rows), "n_resolved": resolved,
            "n_worked": len(groups["worked"]), "groups": groups}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_retrospective.py -v`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add components/retrospective.py tests/test_retrospective.py
git commit -F <msgfile>   # "feat(retrospective): month digest grouping + headline stats" + trailers
```

---

### Task 4: `banner_text` + `paper_month_line`

**Files:**
- Modify: `components/retrospective.py` (adds `from components.paper_book import select_policy` — place it above the `lib` imports per isort: `components` sorts before `lib`)
- Modify: `tests/test_retrospective.py`

**Interfaces:**
- Consumes: `components.paper_book.select_policy(nav_df, block) -> pd.DataFrame` (headline-lane rows sorted by date).
- Produces:
  - `banner_text(calibration_insights: dict | None) -> str` — `confidence_banner` verbatim, else the fixed fallback.
  - `paper_month_line(nav_df: pd.DataFrame, block: dict, month: str) -> str` — e.g. `"Paper book: +2.1% in June vs SPY +1.4% · SOXX +3.0%"`; `""` when the month has no NAV rows or NAV endpoints are unusable.

- [ ] **Step 1: Write the failing tests** (append)

```python
from components.retrospective import banner_text, paper_month_line


def test_banner_text_prefers_report_banner():
    assert banner_text({"confidence_banner": "NOT yet decision-grade."}) == "NOT yet decision-grade."


def test_banner_text_falls_back_when_absent():
    fallback = banner_text(None)
    assert "single market regime" in fallback
    assert banner_text({"confidence_banner": "  "}) == fallback


def _nav():
    return pd.DataFrame({
        "policy_id": ["v1_flat10"] * 3,
        "date": ["2026-05-29", "2026-06-10", "2026-06-30"],
        "nav_units": [1000000.0, 1010000.0, 1030000.0],
        "spy_close": [700.0, 707.0, 714.0],
        "soxx_close": [400.0, 404.0, 410.0],
    })


def test_paper_month_line_uses_pre_month_baseline():
    line = paper_month_line(_nav(), {"policy_id": "v1_flat10"}, "2026-06")
    assert line.startswith("Paper book: +3.0% in June")
    assert "SPY +2.0%" in line
    assert "SOXX +2.5%" in line


def test_paper_month_line_seed_month_baselines_on_first_in_month_row():
    nav = _nav().iloc[1:]  # no pre-June row: June return measured from 06-10
    line = paper_month_line(nav, {"policy_id": "v1_flat10"}, "2026-06")
    assert "+2.0% in June" in line  # 1010000 -> 1030000


def test_paper_month_line_empty_when_month_has_no_rows():
    assert paper_month_line(_nav(), {"policy_id": "v1_flat10"}, "2026-07") == ""
    assert paper_month_line(pd.DataFrame(), {}, "2026-06") == ""
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_retrospective.py -v`
Expected: ImportError on `banner_text`.

- [ ] **Step 3: Write the implementation**

Add near the top of `components/retrospective.py` (import block + constant):

```python
from components.paper_book import select_policy

_FALLBACK_BANNER = (
    "Track record spans mostly a single market regime — read these verdicts "
    "as provisional, not proven."
)
```

Append the functions:

```python
def banner_text(calibration_insights: dict | None) -> str:
    """The honesty banner: the pipeline's own confidence_banner verbatim when
    present, else a fixed single-regime caution. Never empty — the spec
    requires every month to render under it."""
    banner = ((calibration_insights or {}).get("confidence_banner") or "").strip()
    return banner or _FALLBACK_BANNER


def paper_month_line(nav_df: pd.DataFrame, block: dict, month: str) -> str:
    """One-line paper-book month read, or '' when the month has no NAV rows.

    Baseline = last NAV at-or-before month start (the seed month, with no
    prior row, measures from its first in-month observation). Uses the same
    ``select_policy`` rule as the Paper Book band so both surfaces always
    describe the same headline lane.
    """
    rows = select_policy(nav_df if nav_df is not None else pd.DataFrame(), block or {})
    if rows.empty:
        return ""
    rows = rows.assign(_d=pd.to_datetime(rows["date"], errors="coerce")).dropna(subset=["_d"])
    keys = rows["_d"].dt.strftime("%Y-%m")
    in_month = rows[keys == month]
    if in_month.empty:
        return ""
    before = rows[keys < month]
    base = before.iloc[-1] if not before.empty else in_month.iloc[0]
    end = in_month.iloc[-1]

    mon_name = pd.Timestamp(f"{month}-01").strftime("%B")
    bits = []
    for col, label in [("nav_units", None), ("spy_close", "SPY"), ("soxx_close", "SOXX")]:
        b = pd.to_numeric(base.get(col), errors="coerce")
        e = pd.to_numeric(end.get(col), errors="coerce")
        if pd.isna(b) or pd.isna(e) or b == 0:
            if label is None:
                return ""  # no NAV read -> no line at all
            continue
        pct = (e - b) / b * 100
        bits.append(f"{pct:+.1f}% in {mon_name}" if label is None else f"{label} {pct:+.1f}%")
    line = f"Paper book: {bits[0]}"
    if len(bits) > 1:
        line += " vs " + " · ".join(bits[1:])
    return line
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_retrospective.py -v`
Expected: all pass. (If `select_policy` import fails at module import in the bare-pytest context, check `components/paper_book.py` — it imports streamlit, which is installed; no stub needed.)

- [ ] **Step 5: Commit**

```bash
git add components/retrospective.py tests/test_retrospective.py
git commit -F <msgfile>   # "feat(retrospective): honesty banner + paper-book month line" + trailers
```

---

### Task 5: HTML builders — `call_item_html` + `digest_html`

**Files:**
- Modify: `components/retrospective.py`
- Modify: `tests/test_retrospective.py`

**Interfaces:**
- Consumes: `lib.pills._signal_pill_html(sig, small=True)`, `lib.formatters._escape_dollars`, `lib.formatters.display_ticker`, `lib.charts.STATUS_NEG / STATUS_POS`, `classify_call` outputs.
- Produces:
  - `call_item_html(row, bucket: str, outcome: str) -> str` — one `.retro-item` div.
  - `digest_html(digest: dict, paper_line: str) -> str` — headline + optional paper line + the three groups (empty groups omitted).

- [ ] **Step 1: Write the failing tests** (append)

```python
from components.retrospective import call_item_html, digest_html


def _row(signal="ACCUMULATE", ticker="AMD"):
    return pd.Series({
        "date": pd.Timestamp("2026-06-05"),
        "ticker": ticker,
        "signal": signal,
        "entry_price": 203.43,
        "invalidation": 195.96,
        "upside_target": 218.84,
    })


def test_call_item_html_shows_call_and_levels_with_entity_dollars():
    out = call_item_html(_row(), "worked", "hit its target inside 20 sessions (+16.4%)")
    assert "AMD" in out
    assert "&#36;203.43" in out
    assert "target &#36;218.84" in out
    assert "stop &#36;195.96" in out
    assert "$" not in out            # raw dollars would trip Streamlit LaTeX
    assert 'data-bucket="worked"' in out


def test_call_item_html_caution_shows_entry_but_no_target_stop():
    out = call_item_html(_row(signal="CAUTION"), "failed", "rallied +4.0% instead")
    assert "&#36;203.43" in out
    assert "target" not in out
    assert "stop" not in out


def test_digest_html_headline_groups_and_paper_line():
    calls = _calls_frame()  # from Task 3
    d = build_month_digest(calls, "2026-06")
    out = digest_html(d, "Paper book: +3.0% in June vs SPY +2.0%")
    assert "June 2026" in out
    assert "2 new calls" in out and "2 resolved" in out and "1 went our way" in out
    assert "What worked" in out
    assert "What didn&#x27;t" in out or "What didn't" in out
    assert "Too early to judge" not in out   # empty groups are omitted
    assert "Paper book: +3.0% in June" in out


def test_digest_html_without_paper_line_omits_it():
    d = build_month_digest(_calls_frame(), "2026-07")
    out = digest_html(d, "")
    assert "Paper book" not in out
    assert "Too early to judge" in out
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_retrospective.py -v`
Expected: ImportError on `call_item_html`.

- [ ] **Step 3: Write the implementation**

Extend the import block (isort order within the module):

```python
from components.paper_book import select_policy
from lib.charts import STATUS_NEG, STATUS_POS
from lib.formatters import _escape_dollars, display_ticker
from lib.pills import _signal_pill_html
```

Append:

```python
_ICONS = {"worked": "✓", "failed": "✗", "pending": "⏳"}
_GROUP_HEADS = [("worked", "What worked"), ("failed", "What didn't"),
                ("pending", "Too early to judge")]


def _price(v) -> str:
    """'&#36;203.43' — entity dollar so Streamlit never parses LaTeX."""
    if v is None or pd.isna(v):
        return "—"
    return f"&#36;{float(v):,.2f}"


def call_item_html(row, bucket: str, outcome: str) -> str:
    """One verdict line: icon · pill · TICKER @ entry (levels) — outcome · date."""
    icon_col = {"worked": STATUS_POS, "failed": STATUS_NEG}.get(bucket, "var(--ink-3)")
    tk = _escape_dollars(display_ticker(str(row["ticker"])))
    levels = ""
    if row["signal"] in _LONG:
        bits = []
        if pd.notna(row.get("upside_target")):
            bits.append(f"target {_price(row['upside_target'])}")
        if pd.notna(row.get("invalidation")):
            bits.append(f"stop {_price(row['invalidation'])}")
        if bits:
            levels = f' <span class="retro-levels">({", ".join(bits)})</span>'
    return (
        f'<div class="retro-item" data-bucket="{bucket}">'
        f'<span class="retro-icon" style="color:{icon_col};">{_ICONS[bucket]}</span>'
        f'<div class="retro-body">'
        f'{_signal_pill_html(row["signal"], small=True)} '
        f'<b>{tk}</b> @ {_price(row.get("entry_price"))}{levels}'
        f'<span class="retro-outcome">— {_escape_dollars(outcome)}</span>'
        f'<span class="retro-date">{row["date"].strftime("%b %d")}</span>'
        f'</div></div>'
    )


def digest_html(digest: dict, paper_line: str) -> str:
    """Headline + paper line + the three groups for one month (empty groups omitted)."""
    head = (f'<div class="retro-headline"><b>{month_label(digest["month"])}</b> — '
            f'{digest["n_calls"]} new calls · {digest["n_resolved"]} resolved · '
            f'{digest["n_worked"]} went our way</div>')
    paper = (f'<div class="retro-paper">{_escape_dollars(paper_line)}</div>'
             if paper_line else "")
    groups = ""
    for key, title in _GROUP_HEADS:
        items = digest["groups"][key]
        if not items:
            continue
        body = "".join(call_item_html(r, key, o) for r, o in items)
        groups += (f'<div class="retro-group"><div class="retro-group-title">'
                   f'{_escape_dollars(title)} · {len(items)}</div>{body}</div>')
    if not groups:
        groups = '<div class="retro-group retro-empty">No calls this month.</div>'
    return head + paper + groups
```

Note: `_escape_dollars(title)` HTML-escapes the apostrophe in "What didn't" via `html.escape(quote=False)`? No — `quote=False` keeps apostrophes literal, so the plain string passes through; the test accepts either form.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_retrospective.py -v`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add components/retrospective.py tests/test_retrospective.py
git commit -F <msgfile>   # "feat(retrospective): month digest HTML renderers" + trailers
```

---

### Task 6: `render_retrospective_page` + AppTest smoke

**Files:**
- Modify: `components/retrospective.py` (adds `import streamlit as st`, `from lib.cards import render_section_head`)
- Modify: `tests/test_retrospective.py`

**Interfaces:**
- Consumes: everything above; `lib.cards.render_section_head(title, sub)`.
- Produces: `render_retrospective_page(latest_report: dict, log_df: pd.DataFrame, nav_df: pd.DataFrame) -> None` — the full page. Task 7 wires this into `dashboard.py`.

- [ ] **Step 1: Write the failing tests** (append; note the ASCII-only, self-contained AppTest function)

```python
def test_page_renders_and_month_picker_switches_months():
    from streamlit.testing.v1 import AppTest

    def app():
        # ASCII-only + self-contained: AppTest.from_function round-trips this
        # source through a locale-encoded temp file on Windows.
        import pandas as pd

        from components.retrospective import render_retrospective_page

        log = pd.DataFrame({
            "date": pd.to_datetime(["2026-06-01", "2026-06-02", "2026-07-01"]),
            "ticker": ["AMD", "AMD", "NVDA"],
            "signal": ["ACCUMULATE", "ACCUMULATE", "CAUTION"],
            "entry_price": [100.0, 100.0, 50.0],
            "invalidation": [95.0, 95.0, 47.0],
            "upside_target": [110.0, 110.0, 55.0],
            "hit_invalidation": [0.0, 0.0, None],
            "hit_upside_target": [1.0, 1.0, None],
            "return_20d": [12.0, 12.5, None],
        })
        nav = pd.DataFrame({
            "policy_id": ["v1_flat10"] * 3,
            "date": ["2026-05-30", "2026-06-10", "2026-06-30"],
            "nav_units": [1000000.0, 1010000.0, 1020000.0],
            "spy_close": [700.0, 707.0, 714.0],
            "soxx_close": [400.0, 404.0, 410.0],
        })
        report = {"calibration_insights": {"confidence_banner": "Single-regime test banner."},
                  "paper_portfolio": {"policy_id": "v1_flat10"}}
        render_retrospective_page(report, log, nav)

    at = AppTest.from_function(app, default_timeout=30)
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    body = " ".join(str(m.value) for m in at.markdown)
    assert "Single-regime test banner." in body     # banner above everything
    assert "NVDA" in body                           # default month = latest (2026-07)
    assert "too early" in body.lower()
    # Archive: switch to June, the resolved AMD call appears with its verdict
    at.selectbox(key="retro_month").set_value("2026-06").run()
    assert not at.exception
    body = " ".join(str(m.value) for m in at.markdown)
    assert "AMD" in body
    assert "hit its target" in body
    assert "Paper book:" in body                    # June has NAV rows


def test_page_empty_log_renders_honest_empty_state():
    from streamlit.testing.v1 import AppTest

    def app():
        import pandas as pd

        from components.retrospective import render_retrospective_page
        render_retrospective_page({}, pd.DataFrame(), pd.DataFrame())

    at = AppTest.from_function(app, default_timeout=30)
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    texts = " ".join(str(c.value) for c in at.caption) + " ".join(
        str(m.value) for m in at.markdown)
    assert "No calls logged yet" in texts
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_retrospective.py -v`
Expected: ImportError on `render_retrospective_page`.

- [ ] **Step 3: Write the implementation**

Extend imports:

```python
import streamlit as st

from lib.cards import render_section_head
```

Append:

```python
def render_retrospective_page(latest_report: dict, log_df: pd.DataFrame,
                              nav_df: pd.DataFrame) -> None:
    """Retrospective page — monthly narrative digest of calls vs outcomes.

    Deliberately NOT clipped by the sidebar date filter: the month picker is
    this page's own time control and the archive should always be complete.
    """
    render_section_head(
        "Retrospective",
        "What we called, and what actually happened — month by month",
    )
    banner = _escape_dollars(banner_text((latest_report or {}).get("calibration_insights")))
    st.markdown(
        f'<div class="briefing-banner" data-tone="warn">⚠ {banner}</div>',
        unsafe_allow_html=True,
    )

    calls = dedupe_calls(log_df)
    if calls.empty:
        st.caption(
            "No calls logged yet — this page fills in as the pipeline's call "
            "ledger (signal_log.csv) accumulates."
        )
        return

    months = sorted(calls["date"].dt.strftime("%Y-%m").unique(), reverse=True)
    sel = st.selectbox("Month", months, index=0, format_func=month_label,
                       key="retro_month")

    # "In progress" is data-derived (latest month in the ledger), never
    # wall-clock — the visual baselines freeze TEST_DATE.
    if sel == months[0]:
        st.caption(
            f"{month_label(sel)} is still in progress — recent calls sit in "
            '"Too early to judge" until their 20-session window closes.'
        )

    digest = build_month_digest(calls, sel)
    paper = paper_month_line(nav_df, (latest_report or {}).get("paper_portfolio") or {}, sel)
    st.markdown(digest_html(digest, paper), unsafe_allow_html=True)

    st.caption(
        "Outcomes are **raw price direction** over each call's own 20-session "
        "window — not benchmark-relative; the alpha view lives on the "
        "Briefing's Signal Calibration band. WATCH and HOLD aren't scored "
        "here (non-directional). Retired names stay on the record — dropping "
        "old calls would flatter it."
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_retrospective.py -v`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add components/retrospective.py tests/test_retrospective.py
git commit -F <msgfile>   # "feat(retrospective): page renderer with month picker + honesty banner" + trailers
```

---

### Task 7: wire the page into the app (dashboard, masthead, CSS, page-walk test)

**Files:**
- Modify: `dashboard.py` (imports; new `_page_retrospective`; `_PAGES` entry)
- Modify: `components/masthead.py` (`_NAV_PAGES`, `_NAV_LABELS`)
- Modify: `assets/theme.css` (append `retro-*` block at end of file)
- Modify: `tests/test_app_pages.py` (`PAGES` list)

**Interfaces:**
- Consumes: `render_retrospective_page(latest_report, log_df, nav_df)` from Task 6; `lib.data_loader.load_signal_log`, `load_paper_nav`, `list_report_dates`, `load_report`.
- Produces: nav target **"Retrospective"** at `url_path="retrospective"` (visual test in Task 8 relies on this exact path), nav strip label **"Review"**.

- [ ] **Step 1: Extend the page-walk test** — in `tests/test_app_pages.py`, add `"Retrospective"` to `PAGES` after `"Signal Tracker"`:

```python
PAGES = [
    "Briefing",
    "Watchlist",
    "Signal Tracker",
    "Retrospective",
    "Pipeline Stats",
    "Scenario Log",
    "Report Comparison",
    "Terminology",
]
```

Also update the module docstring's "all 7 nav targets" to "all 8 nav targets".

- [ ] **Step 2: Run it to verify it fails**

Run: `python -m pytest tests/test_app_pages.py -v -k Retrospective`
Expected: FAIL — `StreamlitAPIException` / radio value "Retrospective" not among options (page not registered yet).

- [ ] **Step 3: Register the page**

`dashboard.py` — extend the `lib.data_loader` import (keep alphabetical):

```python
from lib.data_loader import (
    data_fingerprint,
    list_report_dates,
    load_all_reports,
    load_earnings_cascades,
    load_paper_nav,
    load_report,
    load_signal_log,
    load_sqlite_prices,
    load_text_asset,
)
```

Add the page function directly after `_page_signal_tracker` (line ~317):

```python
def _page_retrospective() -> None:
    from components.retrospective import render_retrospective_page
    # Not sidebar-date-filtered: the page's month picker is its own time
    # control and the archive should always be complete.
    _dates = list_report_dates()
    _latest = load_report(_dates[-1]) if _dates else {}
    render_retrospective_page(_latest, load_signal_log(), load_paper_nav())
```

Add to `_PAGES` right after the Signal Tracker entry:

```python
    "Retrospective": st.Page(_page_retrospective, title="Retrospective", url_path="retrospective"),
```

`components/masthead.py` — insert into `_NAV_PAGES` after `"Signal Tracker"`:

```python
_NAV_PAGES = [
    "Briefing",
    "Watchlist",
    "Signal Tracker",
    "Retrospective",
    "Pipeline Stats",
    "Scenario Log",
    "Report Comparison",
    "Terminology",
]
```

and add the short strip label:

```python
_NAV_LABELS = {
    "Signal Tracker": "Tracker",
    "Retrospective": "Review",
    "Pipeline Stats": "Pipeline",
    "Scenario Log": "Scenarios",
    "Report Comparison": "Compare",
}
```

- [ ] **Step 4: Append the styles** to the end of `assets/theme.css`:

```css
/* ── Retrospective page (spec 2026-07-20-reader-retrospective-design) ── */
.retro-headline {
  font-family: var(--mono);
  font-size: 13px;
  letter-spacing: 0.04em;
  color: var(--ink-2);
  margin: 18px 0 8px;
}
.retro-headline b { color: var(--ink); }
.retro-paper {
  font-family: var(--mono);
  font-size: 12px;
  color: var(--ink-2);
  margin: 0 0 16px;
}
.retro-group { margin: 0 0 20px; }
.retro-group-title {
  font-family: var(--mono);
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.14em;
  color: var(--ink-3);
  border-bottom: 1px solid var(--rule);
  padding-bottom: 4px;
  margin-bottom: 8px;
}
.retro-item {
  display: flex;
  gap: 10px;
  align-items: baseline;
  padding: 5px 0;
}
.retro-icon { flex: 0 0 16px; text-align: center; }
.retro-body { font-size: 0.92rem; line-height: 1.55; color: var(--ink-2); }
.retro-body b { color: var(--ink); }
.retro-levels { color: var(--ink-3); font-size: 0.85em; }
.retro-outcome { margin-left: 6px; }
.retro-date {
  margin-left: 8px;
  font-family: var(--mono);
  font-size: 10px;
  color: var(--ink-3);
  letter-spacing: 0.08em;
}
.retro-empty { color: var(--ink-3); }
```

(Verify `--ink / --ink-2 / --ink-3 / --rule / --mono` exist in `theme.css` `:root` — they are used throughout the file; if a name differs, match the file's actual token names.)

- [ ] **Step 5: Run the page-walk + full suite**

Run: `python -m pytest tests/test_app_pages.py -v`
Expected: all pass, including `test_page_renders_without_exception[Retrospective]`.
Run: `python -m pytest -q`
Expected: full suite green.

- [ ] **Step 6: Commit**

```bash
git add dashboard.py components/masthead.py assets/theme.css tests/test_app_pages.py
git commit -F <msgfile>   # "feat(retrospective): register page in nav + retro-* styles" + trailers
```

---

### Task 8: rollout — changelog entry, visual baseline, manual check

**Files:**
- Modify: `data/changelog.json` (prepend entry — newest first)
- Modify: `tests/visual/test_pages.py` (`PAGES` list)
- Baselines: `tests/visual/baselines/` (regenerated PNGs: `retrospective`, plus `signal-tracker` — its changelog strip shows the new entry)

**Interfaces:**
- Consumes: the running app at `/retrospective` (Task 7).
- Produces: user-visible changelog entry; committed visual baselines.

- [ ] **Step 1: Prepend the changelog entry** as the FIRST element of the `data/changelog.json` array (hand-edit; keep valid JSON):

```json
{
  "date": "2026-07-20",
  "title": "New page: Retrospective — what we called, what happened",
  "note": "A new page tells each month's story in plain sentences: what we told you to buy or avoid, at what price and with what target, and how it worked out over the following 20 trading sessions — grouped into what worked, what didn't, and what's too early to judge, with the paper book's month alongside. Past months never get quietly rewritten, retired names stay on the record, and the single-regime caution banner sits above every month. Find it in the top navigation as 'Review'."
}
```

Verify: `python -c "import json; json.load(open('data/changelog.json'))"` → no error.

- [ ] **Step 2: Register the visual snapshot** — in `tests/visual/test_pages.py` add to `PAGES` after the signal-tracker tuple:

```python
    ("retrospective", "/retrospective"),
```

No `PAGE_MASKS` entry needed: the page carries no clock-derived text (the "in progress" caption derives from the data's latest month, and the global date-input mask covers the sidebar).

- [ ] **Step 3: Run the full non-visual suite**

Run: `python -m pytest -q`
Expected: green.

- [ ] **Step 4: Regenerate visual baselines** — **PowerShell** (not Git Bash — Docker path mangling), from the repo root:

```powershell
make visual-update
```

Expected: new `tests/visual/baselines/retrospective.png` appears; `signal-tracker.png` regenerates (changelog strip now shows the new entry); unchanged pages are skipped (d5ff587 behavior). This host renders ~10x slower than CI — be patient. Then verify:

```powershell
make visual
```

Expected: all visual comparisons pass.

- [ ] **Step 5: Manual smoke check** — restart the Streamlit dev server (lazy `_page_*` modules are cached), open `/retrospective`, confirm: banner on top, current month selected with "in progress" caption, month picker walks back to April 2026, verdict sentences read correctly against a few known calls (e.g. the 2026-04-01 AMD ACCUMULATE @ 203.43 should show as worked — `hit_upside_target` is 1.0 in the CSV).

- [ ] **Step 6: Commit**

```bash
git add data/changelog.json tests/visual/test_pages.py tests/visual/baselines/
git commit -F <msgfile>   # "feat(retrospective): changelog entry + visual baseline" + trailers
```

---

## Definition of done

- `python -m pytest -q` green; `make visual` green.
- `/retrospective` renders every month April→current with the banner on top.
- Spec requirements all traceable: monthly digest w/ archive (Tasks 3, 6), frozen verdicts (Task 2), honesty banner (Tasks 4, 6), paper-book line (Task 4), retired tickers kept (Task 1 — no filter), empty states (Tasks 1, 6), changelog + baselines (Task 8).
