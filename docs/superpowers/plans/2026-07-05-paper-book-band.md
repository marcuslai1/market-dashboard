# Paper-Book Band + Thin/Episodes Adoption Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Render the pipeline's mechanical paper portfolio as a Signal Tracker band (NAV-vs-SPY/SOXX curve + summary + positions drawer) and adopt the pipeline's new per-cell `thin`/`n_episodes` fields as the Briefing calibration honesty gate.

**Architecture:** One small upstream export addition (`paper_nav.csv` from the `paper_portfolio_nav` SQLite table, MarketReport repo), then dashboard-side: a cached CSV loader, a new `components/paper_book.py` module (pure reducers + HTML builders + one Plotly figure), one call site in the tracker page between scorecard and changelog, and a field-preference upgrade in `components/briefing/calibration.py`. Everything degrades tier-by-tier when data is absent — the 85 existing reports render exactly as today.

**Tech Stack:** Python, Streamlit, pandas, Plotly (`lib/charts.py` conventions), pytest, ruff. Spec: `docs/superpowers/specs/2026-07-05-paper-book-band-design.md`.

## Global Constraints

- **Two repos.** Task 1 runs in `C:\Users\laize\Desktop\MarketReport`; Tasks 2–6 run in `C:\Users\laize\Desktop\market-dashboard`. Every command below states its working directory.
- **pandas 1.4.2 floor** (local env is base Anaconda): no pandas-2.x-only APIs. Everything used here (`to_numeric`, `dropna`, `sort_values`, `groupby`) is 1.x-safe.
- **Dashboard math budget** (spec): rebasing exported series to 100 at their first valid row is the ONLY arithmetic the dashboard adds. No win/loss scoring, no return math beyond `value / base * 100`.
- **Escaping:** every report-derived string injected through `unsafe_allow_html` goes through `_escape_dollars` (text nodes) or `_escape_attr` (attribute values) from `lib/formatters.py`.
- **Fallback paths byte-identical:** reports without the new fields must render exactly today's HTML — do NOT regenerate visual baselines in this plan (deliberate regen happens later, when the first real export lands).
- **Gates:** `pytest -q` and `ruff check .` green in the repo you touched, every task.
- **Copy rules:** ISO dates as-is (no month-name humanizing); the paper book's caveat/banner text comes verbatim from the export — never invent caveat wording dashboard-side.
- **Spec refinement (deliberate, called out here so nobody "fixes" it):** `_is_low_confidence` keeps treating `single_regime=True` as low-confidence even when the pipeline's `thin` flag is present and False. The pipeline's `thin` gate covers sample size (alpha-n AND episode floors) but not regime coverage; dropping the regime check would let the headline say "decision-grade" two lines above the pipeline's own "single-regime — not decision-grade" banner. `thin` replaces only the local `n<30` floor.

---

### Task 1: Upstream `paper_nav.csv` export (MarketReport repo)

**Working directory:** `C:\Users\laize\Desktop\MarketReport`

**Files:**
- Modify: `pipeline/output.py` (inside `export_to_dashboard`, after the `signal_log.csv` export, ~line 444)
- Create: `tests/test_export_paper_nav.py`
- Modify: `PIPELINE_FEATURES.md` (export-file list under the `export_to_dashboard()` section, ~line 890)
- Modify: `.claude/skills/market-report-bot/references/data-and-storage.md` (export list, ~line 319)

**Interfaces:**
- Consumes: existing `paper_portfolio_nav` table (`policy_id TEXT, date TEXT, nav_units INTEGER, cash_units INTEGER, n_positions INTEGER, spy_close REAL, soxx_close REAL`, UNIQUE(policy_id, date)); `export_to_dashboard(today_str)`.
- Produces: `<dashboard>/data/paper_nav.csv` with header exactly `policy_id,date,nav_units,cash_units,n_positions,spy_close,soxx_close`, ordered by `policy_id, date`. Tasks 2–4 rely on these column names.

- [ ] **Step 1: Write the failing test**

Create `tests/test_export_paper_nav.py`:

```python
"""export_to_dashboard writes paper_nav.csv — the paper-book band's curve
source (dashboard spec 2026-07-05-paper-book-band-design)."""
import sqlite3

import pandas as pd

import pipeline.config as config
from pipeline.output import export_to_dashboard
from pipeline.persistence import init_db

_ROW = ("INSERT INTO paper_portfolio_nav (policy_id, date, nav_units, "
        "cash_units, n_positions, spy_close, soxx_close) VALUES (?,?,?,?,?,?,?)")


def test_export_writes_paper_nav_csv(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "test.db")
    init_db()
    with sqlite3.connect(config.DB_PATH) as conn:
        conn.execute(_ROW, ("v1_flat10", "2026-04-19", 1_000_000, 1_000_000, 0, 522.1, 201.3))
        conn.execute(_ROW, ("v1_flat10", "2026-04-20", 1_004_500, 900_000, 1, 524.0, 203.9))
        conn.commit()
    dash = tmp_path / "dash"
    (dash / "data").mkdir(parents=True)
    monkeypatch.setattr("pipeline.output.DASHBOARD_REPO", dash)

    export_to_dashboard("2026-04-20")   # git push step fails in tmp dir; caught + logged

    out = pd.read_csv(dash / "data" / "paper_nav.csv")
    assert list(out.columns) == ["policy_id", "date", "nav_units", "cash_units",
                                 "n_positions", "spy_close", "soxx_close"]
    assert len(out) == 2
    assert out.iloc[1]["nav_units"] == 1_004_500


def test_export_paper_nav_empty_table_writes_header_only(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "test.db")
    init_db()
    dash = tmp_path / "dash"
    (dash / "data").mkdir(parents=True)
    monkeypatch.setattr("pipeline.output.DASHBOARD_REPO", dash)

    export_to_dashboard("2026-04-20")

    out = pd.read_csv(dash / "data" / "paper_nav.csv")
    assert len(out) == 0   # header-only, never an error
```

- [ ] **Step 2: Run test to verify it fails**

Run (in `MarketReport`): `pytest tests/test_export_paper_nav.py -v`
Expected: FAIL — `FileNotFoundError` / `EmptyDataError` reading `paper_nav.csv` (the export doesn't write it yet).

- [ ] **Step 3: Add the export**

In `pipeline/output.py`, inside the `with sqlite3.connect(str(config.DB_PATH)) as conn:` block of `export_to_dashboard`, directly after the `signal_log.csv` `to_csv` call (after ~line 444), add:

```python
            # paper_portfolio_nav — daily NAV/benchmark series for the
            # dashboard's paper-book band (curve incl. replay-seeded history;
            # dashboard spec 2026-07-05-paper-book-band-design)
            pd.read_sql_query(
                "SELECT policy_id, date, nav_units, cash_units, n_positions, "
                "spy_close, soxx_close FROM paper_portfolio_nav "
                "ORDER BY policy_id, date", conn,
            ).to_csv(data_dir / "paper_nav.csv", index=False)
```

- [ ] **Step 4: Run test to verify it passes**

Run (in `MarketReport`): `pytest tests/test_export_paper_nav.py -v`
Expected: 2 PASSED.

- [ ] **Step 5: Update the two doc lists**

In `PIPELINE_FEATURES.md`, in the exported-files list under the `export_to_dashboard()` section (~line 890), add one bullet in the list's existing style:

```markdown
- `paper_nav.csv` — daily paper-portfolio NAV + SPY/SOXX closes per `policy_id` (the dashboard paper-book band's curve source)
```

In `.claude/skills/market-report-bot/references/data-and-storage.md` (~line 319), extend the sentence listing exported CSVs to include `paper_nav.csv`.

- [ ] **Step 6: Full gate + commit**

Run (in `MarketReport`): `pytest -q` then `ruff check .`
Expected: all pass, no lint errors.

```bash
git add pipeline/output.py tests/test_export_paper_nav.py PIPELINE_FEATURES.md ".claude/skills/market-report-bot/references/data-and-storage.md"
git commit -m "feat(export): paper_nav.csv - daily paper-book NAV series for the dashboard band"
```

---

### Task 2: `load_paper_nav()` loader (dashboard repo)

**Working directory:** `C:\Users\laize\Desktop\market-dashboard`

**Files:**
- Modify: `lib/data_loader.py` (append after `load_sqlite_prices`, ~line 186)
- Modify: `tests/test_data_loader.py` (append)

**Interfaces:**
- Consumes: `data/paper_nav.csv` (Task 1's columns), existing `_safe_read_csv`, `_mtime`, `DATA_DIR`.
- Produces: `load_paper_nav() -> pd.DataFrame` — raw CSV frame (columns as exported, `date` left as string), empty DataFrame when the file is missing/malformed. Tasks 3–5 rely on this exact name and behavior.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_data_loader.py`:

```python
# ── Paper-book band: load_paper_nav (spec 2026-07-05-paper-book-band) ──
def test_load_paper_nav_missing_file_returns_empty(monkeypatch, tmp_path):
    monkeypatch.setattr(dl, "DATA_DIR", tmp_path)
    df = dl.load_paper_nav()
    assert df.empty


def test_load_paper_nav_reads_columns(monkeypatch, tmp_path):
    monkeypatch.setattr(dl, "DATA_DIR", tmp_path)
    (tmp_path / "paper_nav.csv").write_text(
        "policy_id,date,nav_units,cash_units,n_positions,spy_close,soxx_close\n"
        "v1_flat10,2026-04-19,1000000,1000000,0,522.1,201.3\n"
        "v1_flat10,2026-04-20,1004500,900000,1,524.0,203.9\n",
        encoding="utf-8",
    )
    df = dl.load_paper_nav()
    assert list(df.columns) == ["policy_id", "date", "nav_units", "cash_units",
                                "n_positions", "spy_close", "soxx_close"]
    assert len(df) == 2
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_data_loader.py -v -k paper_nav`
Expected: FAIL with `AttributeError: module 'lib.data_loader' has no attribute 'load_paper_nav'`.

- [ ] **Step 3: Implement the loader**

In `lib/data_loader.py`, after `load_sqlite_prices` (~line 186), add:

```python
@st.cache_data(max_entries=4)
def _load_paper_nav_cached(path_str: str, mtime: float) -> pd.DataFrame:
    return _safe_read_csv(Path(path_str))


def load_paper_nav() -> pd.DataFrame:
    """Daily paper-portfolio NAV series (``data/paper_nav.csv``), or empty.

    Exported by the pipeline from its ``paper_portfolio_nav`` table (spec
    2026-07-05-paper-book-band-design): ``policy_id, date, nav_units,
    cash_units, n_positions, spy_close, soxx_close``. Raw frame — date
    parsing and policy selection live in the band's reducers. Missing file
    (every checkout until the pipeline first exports it) → empty frame.
    """
    path = DATA_DIR / "paper_nav.csv"
    return _load_paper_nav_cached(str(path), _mtime(path))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_data_loader.py -v -k paper_nav`
Expected: 2 PASSED.

- [ ] **Step 5: Commit**

```bash
git add lib/data_loader.py tests/test_data_loader.py
git commit -m "feat(loader): load_paper_nav - mtime-keyed reader for the paper-book CSV"
```

---

### Task 3: Paper-book reducers (pure functions)

**Working directory:** `C:\Users\laize\Desktop\market-dashboard`

**Files:**
- Create: `components/paper_book.py`
- Create: `tests/test_paper_book.py`

**Interfaces:**
- Consumes: nothing project-specific yet (pandas only).
- Produces (Task 4 renders these; exact signatures):
  - `select_policy(nav_df: pd.DataFrame, block: dict) -> pd.DataFrame` — rows for the policy the report block names; sole-distinct-id fallback; empty frame otherwise. Sorted by date.
  - `rebase_curves(df: pd.DataFrame) -> pd.DataFrame` — columns `date` (datetime) + up to `Paper book` / `SPY` / `SOXX`, each rebased to 100 at its own first valid value.
  - `verdict_bits(block: dict) -> tuple[str, str]` — (verdict sentence, tone) with tone in `{"pos", "neg", ""}`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_paper_book.py`:

```python
"""Paper-book band reducers + renderers (spec 2026-07-05-paper-book-band)."""
import pandas as pd

from components.paper_book import rebase_curves, select_policy, verdict_bits


def _nav_df(policy="v1_flat10"):
    return pd.DataFrame({
        "policy_id": [policy, policy],
        "date": ["2026-04-19", "2026-04-20"],
        "nav_units": [1_000_000, 1_004_500],
        "cash_units": [1_000_000, 900_000],
        "n_positions": [0, 1],
        "spy_close": [500.0, 510.0],
        "soxx_close": [200.0, 199.0],
    })


# ── select_policy ──
def test_select_policy_prefers_block_policy_id():
    df = pd.concat([_nav_df("v1_flat10"), _nav_df("trim_on_caution")])
    out = select_policy(df, {"policy_id": "trim_on_caution"})
    assert set(out["policy_id"]) == {"trim_on_caution"}
    assert len(out) == 2


def test_select_policy_sole_id_without_block():
    out = select_policy(_nav_df(), {})
    assert len(out) == 2


def test_select_policy_multi_id_without_block_is_empty():
    df = pd.concat([_nav_df("v1_flat10"), _nav_df("trim_on_caution")])
    assert select_policy(df, {}).empty     # never mix variants into one curve


def test_select_policy_empty_input():
    assert select_policy(pd.DataFrame(), {}).empty
    assert select_policy(None, {"policy_id": "v1_flat10"}).empty


# ── rebase_curves ──
def test_rebase_to_100_at_first_row():
    out = rebase_curves(select_policy(_nav_df(), {}))
    assert list(out.columns) == ["date", "Paper book", "SPY", "SOXX"]
    assert out["Paper book"].iloc[0] == 100.0
    assert round(out["Paper book"].iloc[1], 2) == 100.45
    assert round(out["SPY"].iloc[1], 1) == 102.0
    assert round(out["SOXX"].iloc[1], 1) == 99.5


def test_rebase_skips_series_with_no_valid_base():
    df = _nav_df()
    df["soxx_close"] = None
    out = rebase_curves(df)
    assert "SOXX" not in out.columns
    assert "Paper book" in out.columns


def test_rebase_empty_input():
    assert rebase_curves(pd.DataFrame()).empty
    assert rebase_curves(None).empty


# ── verdict_bits ──
def test_verdict_trailing():
    text, tone = verdict_bits({"nav_return_pct": 4.2, "spy_return_pct": 6.1,
                               "inception": "2026-04-19"})
    assert "+4.2%" in text and "+6.1%" in text and "2026-04-19" in text
    assert "trailing" in text
    assert tone == "neg"


def test_verdict_leading():
    text, tone = verdict_bits({"nav_return_pct": 8.0, "spy_return_pct": 6.1})
    assert "leading" in text
    assert tone == "pos"


def test_verdict_seeded_when_returns_none():
    text, tone = verdict_bits({"nav_return_pct": None, "spy_return_pct": None,
                               "inception": "2026-04-19"})
    assert "seeded" in text
    assert tone == ""
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_paper_book.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'components.paper_book'`.

- [ ] **Step 3: Implement the reducers**

Create `components/paper_book.py`:

```python
"""Signal Tracker · Paper-book band (page-contract tier 1c).

Renders the pipeline's mechanical paper portfolio — policy ``v1_flat10``,
replay-seeded 2026-04-19, Measurement-Gate-exempt — from two exported
sources: the report's ``paper_portfolio`` summary block and
``data/paper_nav.csv`` (daily NAV + SPY/SOXX closes). The dashboard's only
arithmetic is rebasing exported series to 100 at their first valid row;
all measurement lives upstream
(docs/superpowers/specs/2026-07-05-paper-book-band-design.md).
"""
from __future__ import annotations

import pandas as pd

# Exported column → display series name. NAV is the hero series; SPY/SOXX are
# the benchmarks the upstream summary already compares against.
_REBASE_COLS = {"nav_units": "Paper book", "spy_close": "SPY", "soxx_close": "SOXX"}


def select_policy(nav_df: pd.DataFrame | None, block: dict) -> pd.DataFrame:
    """Rows of *nav_df* for the policy the latest report block names.

    Without a block, falls back to the sole distinct ``policy_id`` — but a
    multi-policy CSV with no block to disambiguate yields an EMPTY frame:
    side-by-side policy variants must never blend into one curve.
    """
    if nav_df is None or nav_df.empty or "policy_id" not in nav_df.columns:
        return pd.DataFrame()
    pid = (block or {}).get("policy_id")
    if pid is None:
        ids = nav_df["policy_id"].dropna().unique()
        if len(ids) != 1:
            return pd.DataFrame()
        pid = ids[0]
    return nav_df[nav_df["policy_id"] == pid].sort_values("date")


def rebase_curves(df: pd.DataFrame | None) -> pd.DataFrame:
    """``date`` + one rebased-to-100 column per available series.

    Each series rebases to its own first valid value (the upstream summary
    computes benchmark returns first-row→last-row the same way — this is
    presentation math, not measurement). Series that are absent, all-NaN, or
    zero-based are omitted rather than plotted wrong.
    """
    if df is None or df.empty:
        return pd.DataFrame()
    out = pd.DataFrame({"date": pd.to_datetime(df["date"], errors="coerce")})
    for col, label in _REBASE_COLS.items():
        if col not in df.columns:
            continue
        series = pd.to_numeric(df[col], errors="coerce")
        valid = series.dropna()
        if valid.empty or valid.iloc[0] == 0:
            continue
        out[label] = series / valid.iloc[0] * 100.0
    if out.columns.tolist() == ["date"]:
        return pd.DataFrame()
    return out


def verdict_bits(block: dict) -> tuple[str, str]:
    """(verdict sentence, tone) for the band's lead line.

    Tone ∈ {"pos", "neg", ""} colours the "— …the benchmark" clause. A block
    whose returns are still ``None`` (seed day / no matured session) reads
    "seeded", mirroring the upstream Telegram glance line.
    """
    nav = block.get("nav_return_pct")
    spy = block.get("spy_return_pct")
    since = f" since {block['inception']}" if block.get("inception") else ""
    if nav is None or spy is None:
        return (f"Paper book seeded{since} — first fills pending.", "")
    body = f"Paper book {nav:+.1f}%{since} vs SPY {spy:+.1f}%"
    if nav > spy:
        return (f"{body} — leading the benchmark.", "pos")
    if nav < spy:
        return (f"{body} — trailing the benchmark.", "neg")
    return (f"{body} — tracking the benchmark.", "")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_paper_book.py -v`
Expected: 13 PASSED.

- [ ] **Step 5: Commit**

```bash
git add components/paper_book.py tests/test_paper_book.py
git commit -m "feat(paper-book): policy selection, rebasing, verdict reducers"
```

---

### Task 4: Paper-book renderers (HTML, figure, band entry point, CSS)

**Working directory:** `C:\Users\laize\Desktop\market-dashboard`

**Files:**
- Modify: `components/paper_book.py` (append renderers)
- Modify: `assets/theme.css` (append one small `.pb-*` block at the end)
- Modify: `tests/test_paper_book.py` (append)

**Interfaces:**
- Consumes: Task 3's reducers; `lib/charts` (`CHART_ACCENT`, `CHART_LINE`, `CHART_PALETTE`, `PLOTLY_CONFIG`, `STATUS_NEG`, `STATUS_POS`, `chart_data_table`, `style_fig`); `lib/cards.render_section_head`; `lib/formatters` (`_escape_dollars`, `display_ticker`).
- Produces: `render_paper_book(latest_report: dict, nav_df: pd.DataFrame) -> None` — the full band with absence tiers. Task 5 calls exactly this.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_paper_book.py`:

```python
# ── renderers ──
from components.paper_book import _positions_table_html, _stats_html, _verdict_html

_BLOCK = {
    "policy_id": "v1_flat10", "inception": "2026-04-19", "as_of": "2026-07-03",
    "nav_pct": 104.2, "cash_pct": 38.0, "n_positions": 5,
    "nav_return_pct": 4.2, "spy_return_pct": 6.1, "soxx_return_pct": 9.9,
    "trade_counts": {"buy_signal": 12, "stop": 3},
    "positions": [
        {"ticker": "NVDA", "weight_pct": 10.4, "stop": 101.5, "tranches": 1,
         "max_dd_pct": -8.3},
        {"ticker": "000660_KS", "weight_pct": 9.1, "stop": None, "tranches": 2,
         "max_dd_pct": -2.0},
    ],
    "trades_today": [{"date": "2026-07-03", "ticker": "AMD", "side": "buy",
                      "reason": "buy_signal"}],
    "banner": "Paper measurement only — single-regime window; "
              "not a performance verdict.",
}


def test_verdict_html_escapes_and_tones():
    html = _verdict_html(_BLOCK)
    assert "trailing the benchmark" in html
    assert 'class="pb-verdict"' in html


def test_stats_html_carries_cash_positions_and_reasons():
    html = _stats_html(_BLOCK)
    assert "38" in html and "5" in html
    assert "12" in html and "3" in html          # trade counts by reason


def test_positions_table_lists_rows_and_skips_malformed():
    html = _positions_table_html(_BLOCK["positions"] + ["not-a-dict", {}])
    assert "NVDA" in html
    assert "000660.KS" in html                    # display_ticker conversion
    assert html.count("<tr>") >= 2                # malformed entries skipped


def test_render_paper_book_absent_renders_nothing():
    from streamlit.testing.v1 import AppTest

    def app():
        import pandas as pd
        from components.paper_book import render_paper_book
        render_paper_book({}, pd.DataFrame())

    at = AppTest.from_function(app)
    at.run()
    assert not at.exception
    assert not at.markdown                        # band skipped entirely


def test_render_paper_book_csv_only_renders_curve_only():
    from streamlit.testing.v1 import AppTest

    def app():
        import pandas as pd
        from components.paper_book import render_paper_book
        nav = pd.DataFrame({
            "policy_id": ["v1_flat10", "v1_flat10"],
            "date": ["2026-04-19", "2026-04-20"],
            "nav_units": [1_000_000, 1_004_500],
            "cash_units": [1_000_000, 900_000],
            "n_positions": [0, 1],
            "spy_close": [500.0, 510.0],
            "soxx_close": [200.0, 199.0],
        })
        render_paper_book({}, nav)   # report predates the block

    at = AppTest.from_function(app)
    at.run()
    assert not at.exception
    joined = " ".join(m.value for m in at.markdown)
    assert "Paper book" in joined                 # section head + curve…
    assert "benchmark" not in joined              # …but no verdict line
    assert "Paper measurement" not in joined      # …and no invented banner


def test_render_paper_book_block_only_renders_summary():
    from streamlit.testing.v1 import AppTest

    def app():
        import pandas as pd
        from components.paper_book import render_paper_book
        block = {"policy_id": "v1_flat10", "inception": "2026-04-19",
                 "cash_pct": 38.0, "n_positions": 1, "nav_return_pct": 4.2,
                 "spy_return_pct": 6.1, "trade_counts": {},
                 "positions": [], "trades_today": [],
                 "banner": "Paper measurement only."}
        render_paper_book({"paper_portfolio": block}, pd.DataFrame())

    at = AppTest.from_function(app)
    at.run()
    assert not at.exception
    joined = " ".join(m.value for m in at.markdown)
    assert "Paper book" in joined
    assert "trailing the benchmark" in joined
    assert "Paper measurement only." in joined
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_paper_book.py -v -k "html or render"`
Expected: FAIL with `ImportError: cannot import name '_positions_table_html'`.

- [ ] **Step 3: Implement the renderers**

Append to `components/paper_book.py` (extend the imports at the top of the file first):

```python
import plotly.graph_objects as go
import streamlit as st

from lib.cards import render_section_head
from lib.charts import (
    CHART_ACCENT,
    CHART_LINE,
    CHART_PALETTE,
    PLOTLY_CONFIG,
    STATUS_NEG,
    STATUS_POS,
    chart_data_table,
    style_fig,
)
from lib.formatters import _escape_dollars, display_ticker
```

Then append after `verdict_bits`:

```python
# Trade-reason keys (upstream policy vocabulary) → compact chip labels.
_REASON_LABELS = {
    "buy_signal": "BUY entries",
    "accumulate_tranche": "ACC tranches",
    "stop": "stops",
    "avoid_exit": "AVOID exits",
    "delist_exit": "delist exits",
}

# Series colours: NAV is the hero (brass); SPY the reference line at ink-3
# (CHART_LINE — ≥3:1 on --paper, same rationale as the capex band); SOXX the
# muted steel blue. None of these collide with signal tokens by design.
_SERIES_COLORS = {"Paper book": CHART_ACCENT, "SPY": CHART_LINE,
                  "SOXX": CHART_PALETTE[0]}


def _verdict_html(block: dict) -> str:
    """Band lead line — plain-English verdict first, house style."""
    text, tone = verdict_bits(block)
    color = {"pos": STATUS_POS, "neg": STATUS_NEG}.get(tone)
    head, sep, tail = text.partition(" — ")
    tail_html = ""
    if sep:
        style = f' style="color:{color};"' if color else ""
        tail_html = f'<span{style}> — {_escape_dollars(tail)}</span>'
    return f'<p class="pb-verdict">{_escape_dollars(head)}{tail_html}</p>'


def _stats_html(block: dict) -> str:
    """Stat chips: cash weight, open positions, trade counts by reason."""
    chips = []
    if block.get("cash_pct") is not None:
        chips.append((f'{block["cash_pct"]:.0f}%', "cash"))
    if block.get("n_positions") is not None:
        chips.append((str(block["n_positions"]), "open positions"))
    for key, label in _REASON_LABELS.items():
        n = (block.get("trade_counts") or {}).get(key)
        if n:
            chips.append((str(n), label))
    if not chips:
        return ""
    body = "".join(
        f'<div class="pb-stat"><b>{_escape_dollars(v)}</b>'
        f"<span>{label}</span></div>"
        for v, label in chips
    )
    return f'<div class="pb-stats">{body}</div>'


def _banner_html(block: dict) -> str:
    """The exported caveat, verbatim — honesty inherited, never invented."""
    banner = (block.get("banner") or "").strip()
    if not banner:
        return ""
    return f'<p class="pb-banner">{_escape_dollars(banner)}</p>'


def _positions_table_html(positions: list) -> str:
    """Open-positions table for the drawer. Malformed rows skipped via .get."""
    rows = ""
    for p in positions or []:
        if not isinstance(p, dict) or not p.get("ticker"):
            continue
        stop = p.get("stop")
        dd = p.get("max_dd_pct")
        rows += (
            "<tr>"
            f"<td>{_escape_dollars(display_ticker(str(p['ticker'])))}</td>"
            f'<td class="num">{p.get("weight_pct", 0):.1f}%</td>'
            f'<td class="num">{f"{stop:.2f}" if stop is not None else "—"}</td>'
            f'<td class="num">{p.get("tranches", "—")}</td>'
            f'<td class="num">{f"{dd:+.1f}%" if dd is not None else "—"}</td>'
            "</tr>"
        )
    if not rows:
        return ""
    return (
        '<table class="ep-table"><thead><tr>'
        '<th scope="col">Name</th><th scope="col" class="num">Weight</th>'
        '<th scope="col" class="num">Stop</th>'
        '<th scope="col" class="num">Tranches</th>'
        '<th scope="col" class="num">Max drawdown</th>'
        f"</tr></thead><tbody>{rows}</tbody></table>"
    )


def _trades_today_html(trades: list) -> str:
    """Today's fills with their policy reasons, one line each."""
    items = ""
    for t in trades or []:
        if not isinstance(t, dict) or not t.get("ticker"):
            continue
        side = _escape_dollars(str(t.get("side", "?")).upper())
        tk = _escape_dollars(display_ticker(str(t["ticker"])))
        reason = _escape_dollars(_REASON_LABELS.get(t.get("reason"),
                                                    str(t.get("reason", ""))))
        items += f"<li><b>{side}</b> {tk} <span>({reason})</span></li>"
    if not items:
        return ""
    return f'<ul class="pb-trades">{items}</ul>'


def _nav_fig(rebased: pd.DataFrame):
    fig = go.Figure()
    for name in [c for c in rebased.columns if c != "date"]:
        fig.add_scatter(
            x=rebased["date"], y=rebased[name], mode="lines", name=name,
            line=dict(color=_SERIES_COLORS.get(name, CHART_LINE),
                      width=2.2 if name == "Paper book" else 1.4),
        )
    fig.update_layout(height=260, margin=dict(l=0, r=0, t=10, b=0),
                      legend=dict(orientation="h", yanchor="bottom", y=1.02),
                      yaxis_title="rebased · inception = 100")
    return style_fig(fig)


def render_paper_book(latest_report: dict, nav_df: pd.DataFrame) -> None:
    """Tier 1c — the paper book. Corpus-scoped (the tracker's name filter
    deliberately does not touch it). Absence tiers per the spec: block+CSV →
    full band; block only → summary, no curve; CSV only → curve only; neither
    → skipped entirely (every pre-export report renders exactly as before).
    """
    block = (latest_report or {}).get("paper_portfolio") or {}
    rebased = rebase_curves(select_policy(nav_df, block))
    if not block and rebased.empty:
        return
    render_section_head(
        "Paper book",
        "The signals traded mechanically · measured by the pipeline",
    )
    if block:
        st.markdown(_verdict_html(block) + _stats_html(block),
                    unsafe_allow_html=True)
    if not rebased.empty:
        st.plotly_chart(_nav_fig(rebased), use_container_width=True,
                        config=PLOTLY_CONFIG)
        chart_data_table(rebased)
    if block:
        st.markdown(_banner_html(block), unsafe_allow_html=True)
        positions_html = _positions_table_html(block.get("positions"))
        trades_html = _trades_today_html(block.get("trades_today"))
        if positions_html or trades_html:
            with st.expander("Positions & today's trades", expanded=False):
                if trades_html:
                    st.markdown(trades_html, unsafe_allow_html=True)
                if positions_html:
                    st.markdown(f'<div class="tk-scroll">{positions_html}</div>',
                                unsafe_allow_html=True)
```

- [ ] **Step 4: Append the CSS block**

At the end of `assets/theme.css`, add:

```css
/* ── Signal Tracker · Paper-book band (tier 1c — spec 2026-07-05) ── */
.pb-verdict { font-size: 19px; line-height: 1.4; color: var(--ink);
  margin: 2px 0 10px; }
.pb-stats { display: flex; flex-wrap: wrap; gap: 20px; margin: 0 0 8px; }
.pb-stat b { display: block; font-size: 15px; color: var(--ink); }
.pb-stat span { font-size: 11px; color: var(--ink-3); }
.pb-banner { font-size: 12px; font-style: italic; color: var(--ink-3);
  margin: 6px 0 0; }
.pb-trades { list-style: none; padding: 0; margin: 0 0 10px; font-size: 13px; }
.pb-trades span { color: var(--ink-3); }
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_paper_book.py -v`
Expected: all PASS (13 reducer + 6 renderer tests).

- [ ] **Step 6: Commit**

```bash
git add components/paper_book.py tests/test_paper_book.py assets/theme.css
git commit -m "feat(paper-book): band renderers - verdict, curve, stats, drawer"
```

---

### Task 5: Tracker page integration

**Working directory:** `C:\Users\laize\Desktop\market-dashboard`

**Files:**
- Modify: `components/signal_tracker.py` (imports ~line 14; page function ~line 643-712; trailing comment ~line 776)
- Test: existing suites (`tests/test_app_pages.py`, `tests/test_signal_tracker.py`) must stay green — the band is absent on the current corpus.

**Interfaces:**
- Consumes: `render_paper_book(latest_report, nav_df)` (Task 4), `load_paper_nav()` (Task 2), the page's existing `latest_report` local (~line 679).
- Produces: the band on the live page, tier 1c.

- [ ] **Step 1: Wire the band into the page**

In `components/signal_tracker.py`:

(a) Extend the loader import (line 14) to:

```python
from lib.data_loader import load_changelog, load_paper_nav
```

(b) Add below the other `components`-level imports (after line 21, `from lib.pills import _signal_pill_html`):

```python
from components.paper_book import render_paper_book
```

(c) In `render_signal_tracker_page`, directly after the scorecard block's closing `else:` body (after the `HOLD: … not scored` caption, ~line 698) and BEFORE the `# ── 2. What we've changed` comment, insert:

```python
    # ── 1c. Paper book — the pipeline's mechanical NAV lane. Corpus-scoped:
    # the name filter below deliberately does not touch it (page contract,
    # spec 2026-07-05-paper-book-band-design). Skips itself until the
    # pipeline's paper_portfolio block / paper_nav.csv export first lands.
    render_paper_book(latest_report, load_paper_nav())
```

(d) Update the page function's docstring tier list (lines 648-654) to mention the new tier — replace the three-tier list with:

```python
    Four tiers, verdict-first:
      1. Readiness meter + scorecard — is the pipeline systematically any good?
         Corpus-wide by design: per-signal calibration is a property of the
         system, so the name filter deliberately does not touch it.
      1c. Paper book — the pipeline's mechanical paper portfolio (NAV vs
         SPY/SOXX), rendered from exports only; also corpus-wide.
      2. What we've changed — dated methodology strip.
      3. Detail drawers (collapsed) — by-name ledger + signal changes; the
         name filter lives here and scopes only these.
```

(e) Update the trailing comment (~lines 776-780) so it can't read as forbidding this band — replace its last sentence (`Its pipeline-log data (signal_log.csv) is still exported; if we want realised P&L back, fold one line into the scorecard rather than re-adding this table.`) with:

```python
# Its pipeline-log data (signal_log.csv) is still exported. The paper-book
# band (tier 1c) is NOT that table returning: it renders the pipeline's own
# paper_portfolio lane — one engine, exported numbers, zero dashboard math
# (spec 2026-07-05-paper-book-band-design).
```

- [ ] **Step 2: Run the page + app suites**

Run: `pytest tests/test_signal_tracker.py tests/test_app_pages.py tests/test_paper_book.py -v`
Expected: all PASS — on the current corpus (no block, no CSV) the band renders nothing, so existing page assertions are untouched.

- [ ] **Step 3: Full gate**

Run: `pytest -q` then `ruff check .`
Expected: full suite green, no lint errors. Do NOT regenerate visual baselines — the band is absent on the baseline corpus by design.

- [ ] **Step 4: Commit**

```bash
git add components/signal_tracker.py
git commit -m "feat(signal-tracker): paper-book band as page-contract tier 1c"
```

---

### Task 6: Calibration honesty gate — thin/episodes fields

**Working directory:** `C:\Users\laize\Desktop\market-dashboard`

**Files:**
- Modify: `components/briefing/calibration.py` (`_is_low_confidence` ~line 40; `_scorecard_rows` ~line 54; `_scorecard_table_html` ~line 127)
- Modify: `tests/test_calibration.py` (append)

**Interfaces:**
- Consumes: `signal_performance.per_signal` cells, which (from the next pipeline run) may carry `thin: bool`, `n_episodes: int`, `alpha_episode_mean_10d: float|None`.
- Produces: row dicts gain `n_episodes` and `ep_mean` keys; the table gains an `α/ep` column and `n · Nep` sample cells ONLY when at least one row carries the fields.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_calibration.py`:

```python
# ── Thin/episodes adoption (spec 2026-07-05-paper-book-band-design) ──
def test_is_low_confidence_pipeline_thin_flag_wins_over_local_floor():
    # thin=False from the pipeline overrides the local n<30 floor…
    assert _is_low_confidence(
        {"single_regime": False, "n_matured_10d": 12, "thin": False}
    ) is False
    # …and thin=True flags even a large-n cell (episode floor not met).
    assert _is_low_confidence(
        {"single_regime": False, "n_matured_10d": 500, "thin": True}
    ) is True


def test_is_low_confidence_single_regime_still_gates_with_thin_false():
    # Regime coverage is orthogonal to the pipeline's sample-size gate: a
    # single-regime cell must never read "decision-grade" (it would
    # contradict the pipeline's own banner two lines below).
    assert _is_low_confidence(
        {"single_regime": True, "n_matured_10d": 500, "thin": False}
    ) is True


def test_scorecard_rows_carry_episode_fields():
    sp = {"CAUTION": {"n_matured_10d": 555, "win_rate_pct": 43.4,
                      "avg_return_10d": 1.83, "alpha_10d": -3.22,
                      "single_regime": False, "thin": False,
                      "n_episodes": 12, "alpha_episode_mean_10d": -2.9}}
    row = _scorecard_rows(sp, {})[0]
    assert row["n_episodes"] == 12
    assert row["ep_mean"] == -2.9
    assert row["low_conf"] is False


def test_table_shows_episode_column_only_when_fields_present():
    from components.briefing.calibration import _scorecard_table_html
    with_ep = _scorecard_table_html(_scorecard_rows(
        {"CAUTION": {"n_matured_10d": 555, "win_rate_pct": 43.4,
                     "avg_return_10d": 1.83, "alpha_10d": -3.22,
                     "single_regime": True, "thin": False,
                     "n_episodes": 12, "alpha_episode_mean_10d": -2.9}}, {}))
    assert " ep</td>" in with_ep       # sample cell: "555 · 12 ep"
    assert "α/ep" in with_ep           # new column header

    without = _scorecard_table_html(_scorecard_rows(_SP, {}))
    assert " ep</td>" not in without   # fallback sample cells unchanged
    assert "α/ep" not in without


def test_fallback_html_is_byte_identical_shape():
    # Golden guard: a field-absent corpus renders exactly the pre-adoption
    # markup (column count and headers), so visual baselines don't churn.
    html = _scorecard_table_html(_scorecard_rows(_SP, {"CAUTION": 23}))
    assert html.count("<th") == 6      # Signal/Today/n/Win/Avg 10d/α — no more
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_calibration.py -v -k "thin or episode or fallback"`
Expected: `test_is_low_confidence_pipeline_thin_flag_wins_over_local_floor` FAILS (returns True for n=12); `test_scorecard_rows_carry_episode_fields` FAILS with `KeyError: 'n_episodes'`; the table tests FAIL on missing "α/ep".

- [ ] **Step 3: Implement the adoption**

In `components/briefing/calibration.py`:

(a) Replace `_is_low_confidence` (~lines 40-51) with:

```python
def _is_low_confidence(perf: dict) -> bool:
    """True when a signal_performance bucket is single-regime or thin.

    Sample-size honesty: when the pipeline exports its own ``thin`` flag
    (alpha-n floor AND ≥5 independent episodes — commit 5dc0fa3 upstream),
    that flag replaces the local ``n < _MIN_MATURED_N`` floor; older reports
    keep the local heuristic. ``single_regime`` stays a gate in both paths —
    regime coverage is orthogonal to sample size, and a single-regime cell
    reading "decision-grade" would contradict the pipeline's own banner.
    """
    if not perf:
        return True
    if perf.get("single_regime"):
        return True
    if "thin" in perf:
        return bool(perf["thin"])
    return (perf.get("n_matured_10d") or 0) < _MIN_MATURED_N
```

(b) In `_scorecard_rows`, extend the appended dict (after the `"alpha"` line, ~line 74) with:

```python
            "n_episodes": perf.get("n_episodes"),
            "ep_mean": perf.get("alpha_episode_mean_10d"),
```

(c) Replace `_scorecard_table_html` (~lines 127-153) with:

```python
def _scorecard_table_html(rows: list) -> str:
    """A .ep-table of signal → today-count, n, win%, avg-10d, alpha.

    When any row carries the pipeline's episode fields, the sample cell
    becomes "n · Nep" (overlapping daily rows can't pose as independent
    observations) and an α/ep column shows the one-episode-one-vote mean.
    Field-absent corpora render exactly the pre-adoption markup. Low-
    confidence rows carry ``data-lowconf="1"`` for CSS muting. Returns ''
    when there are no rows.
    """
    if not rows:
        return ""
    has_ep = any(r["n_episodes"] is not None for r in rows)
    trs = []
    for r in rows:
        lc = ' data-lowconf="1"' if r["low_conf"] else ""
        win = f'{_fmt_num(r["win"], 0)}%' if r["win"] is not None else "—"
        n_cell = _fmt_num(r["n"], 0)
        if has_ep and r["n_episodes"] is not None:
            n_cell = f'{n_cell} · {int(r["n_episodes"])} ep'
        ep_td = f'<td class="num">{_pct(r["ep_mean"])}</td>' if has_ep else ""
        trs.append(
            f"<tr{lc}><td>{_signal_pill_html(r['signal'], small=True)}</td>"
            f'<td class="num">{r["today"]}</td>'
            f'<td class="num">{n_cell}</td>'
            f'<td class="num">{win}</td>'
            f'<td class="num">{_pct(r["avg"])}</td>'
            f'<td class="num">{_pct(r["alpha"])}</td>{ep_td}</tr>'
        )
    ep_th = '<th class="num">α/ep</th>' if has_ep else ""
    return (
        '<div class="tk-scroll"><table class="ep-table cal-scorecard">'
        '<thead><tr><th>Signal</th><th class="num">Today</th>'
        '<th class="num">n</th><th class="num">Win</th>'
        f'<th class="num">Avg 10d</th><th class="num">α</th>{ep_th}</tr></thead>'
        f'<tbody>{"".join(trs)}</tbody></table></div>'
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_calibration.py -v`
Expected: all PASS, including every pre-existing test (the fallback path is unchanged).

- [ ] **Step 5: Full gate + commit**

Run: `pytest -q` then `ruff check .`
Expected: full suite green.

```bash
git add components/briefing/calibration.py tests/test_calibration.py
git commit -m "feat(calibration): adopt pipeline thin/n_episodes as the honesty gate"
```

---

## Post-plan notes (not tasks)

- **Visual baselines:** regenerate ONCE, deliberately, after the first real pipeline export lands (next pipeline run) — expected diff: the paper-book band appearing on the tracker and the α/ep column on the Briefing. Slow-host regen via PowerShell + Docker per `tests/visual/README.md`.
- **`data/changelog.json`:** consider a hand-written entry ("Paper book goes live — signals traded mechanically since 2026-04-19") once real data shows; editorial call, not code.
- **Server restart:** `_page_*` modules are lazily imported and cached — restart Streamlit to see the band after these edits.
