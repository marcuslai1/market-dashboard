# AI Capex Pulse Datasheet Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild the Briefing's AI Capex Pulse band as a fixed-geometry datasheet plate where every figure sits beside a plain-English explanation.

**Architecture:** Each of the five chip builders in `lib/capex.py` gains three derived presentation fields (`measure`, `value`, `remark`). `components/briefing/capex_pulse.py` replaces its three HTML builders with one `_datasheet_html`. Styling moves out of inline `style=` attributes into a `.capex-sheet` block in `assets/theme.css`. No computation, no data source, and no tone/arrow logic changes — this is presentation only.

**Tech Stack:** Python 3.10, Streamlit 1.58, pandas, pytest, Playwright (visual baselines, Docker only).

## Global Constraints

- Spec: `docs/superpowers/specs/2026-07-22-capex-pulse-datasheet-design.md`. Read it first.
- **Presentation layer only.** Every `remark` must be a formatting of a value the chip builder already computed. No new analysis, no new data source, no change to scenario odds.
- **Banned from every `remark`** (spec §2 rule 1): `PEG`, `pp`, `pct`, `percentile`, `circularity`, `fragile tier`, `beneficiary`. Enforced by unit test.
- **Never `--ink-4` for text** in the plate — it measures 2.51:1 on `--paper-2`.
- Signal palette in `assets/theme.css` must not change; `tests/test_design_tokens.py` fails on drift.
- Run tests with `.venv/Scripts/python.exe -m pytest` (module form — bare `pytest` fails collection).
- Visual baselines regenerate **only** in `mcr.microsoft.com/playwright/python:v1.60.0-jammy`, never on the Windows host.
- Branch: `capex-datasheet`. Commit after every task.

## Two corrections to the spec

Found while mapping the code. Both are resolved this way in the plan below.

1. **Spec §4 says a degraded chip's row is omitted. That contradicts the
   2026-07-03 spec's "a chip never silently vanishes" rule**, which the current
   code implements via `tone: "na"` chips carrying explicit copy. Resolution:
   **the row stays**, with `value` = `"—"` and `remark` carrying the degraded
   explanation. Rows are omitted only when the chip is absent from the list
   entirely, which `build_chips` never does.
2. **Spec §2 says two new fields; this plan adds three.** `measure` (the plate
   label from spec §1's rename table) is added as its own field rather than
   overwriting `label`, so the History expander, the accessibility table, and
   the existing `tests/test_capex.py` assertions on `label` keep working.

## File Structure

| File | Responsibility | Change |
|---|---|---|
| `lib/capex.py` | Pure derivation. The five `_*_chip` builders gain `measure`/`value`/`remark`; a `_BANNED_REMARK_TERMS` constant documents the vocabulary rule. | Modify |
| `components/briefing/capex_pulse.py` | Rendering. `_datasheet_html` replaces `_verdict_html`, `_hero_gap_html`, `_signals_html`. | Modify |
| `assets/theme.css` | `.capex-sheet` geometry, rhythm and ink. | Modify |
| `tests/test_capex.py` | Unit tests for the new derivation, incl. degraded paths and the banned-vocabulary guard. | Modify |
| `tests/test_capex_pulse.py` | Renderer tests; the three deleted builders' tests are replaced. | Modify |
| `data/changelog.json` | User-facing entry. | Modify |

---

### Task 1: `measure`/`value`/`remark` on the capex and revenue chips

**Files:**
- Modify: `lib/capex.py:254-277` (`_capex_chip`), `lib/capex.py:304-336` (`_rev_chip`)
- Test: `tests/test_capex.py`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: every chip dict gains `measure: str`, `value: str`, `remark: str`. Later tasks rely on all five chips carrying all three keys. `_BANNED_REMARK_TERMS: tuple[str, ...]` of regex patterns.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_capex.py`:

```python
import re

from lib.capex import _BANNED_REMARK_TERMS, build_chips


def test_capex_chip_value_and_remark_when_accelerating():
    capex = _capex_fixture_two_quarters()  # reuse the fixture used by
                                           # test_capex_chip_accelerating_at_threshold
    chip = [c for c in build_chips(capex, _empty_fund_df(), date(2026, 7, 22))
            if c["key"] == "capex"][0]
    assert chip["measure"] == "Capex growth"
    assert chip["value"].endswith("%")
    assert "still building" in chip["remark"]
    assert "Up from" in chip["remark"]


def test_capex_chip_degraded_row_keeps_dash_value_and_explains():
    chip = [c for c in build_chips({"core": ["MSFT"], "series": {}, "fragile": [],
                                    "beneficiaries": [], "warnings": []},
                                   _empty_fund_df(), date(2026, 7, 22))
            if c["key"] == "capex"][0]
    assert chip["value"] == "—"
    assert chip["remark"]  # never blank — the reader must learn why


def test_rev_chip_value_and_remark_name_the_reference_month():
    capex, fund = _rev_fixture_flat()  # reuse from test_rev_chip_falling_warns
    chip = [c for c in build_chips(capex, fund, date(2026, 7, 22))
            if c["key"] == "rev"][0]
    assert chip["measure"] == "Customer sales"
    assert chip["value"].endswith("%")
    assert re.search(r"\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\b",
                     chip["remark"])


def test_no_remark_uses_banned_vocabulary():
    capex, fund = _rev_fixture_flat()
    for chip in build_chips(capex, fund, date(2026, 7, 22)):
        for pattern in _BANNED_REMARK_TERMS:
            assert not re.search(pattern, chip["remark"], re.I), (
                f"{chip['key']} remark uses banned term {pattern}: {chip['remark']}")
```

Reuse the existing fixtures in the file rather than inventing new ones; if a
fixture is inline in an existing test, lift it to a module-level helper first.

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_capex.py -k "value_and_remark or banned_vocabulary or degraded_row" -v`
Expected: FAIL — `ImportError: cannot import name '_BANNED_REMARK_TERMS'`

- [ ] **Step 3: Add the constant and the two chips' fields**

In `lib/capex.py`, after the `SEMIS_CLUSTER` constant:

```python
# Vocabulary banned from every chip `remark` (spec §2 rule 1). The remark column
# is the one place the band speaks plain English; these terms assume a
# vocabulary the reader has told us they do not have. Enforced by
# tests/test_capex.py::test_no_remark_uses_banned_vocabulary.
_BANNED_REMARK_TERMS = (r"\bPEG\b", r"\bpp\b", r"\bpct\b", r"\bpercentile\b",
                        r"\bcircularity\b", r"\bfragile tier\b", r"\bbeneficiar")
```

In `_capex_chip`, the degraded return becomes:

```python
        return {"key": "capex", "label": "Capex", "sub": sub,
                "measure": "Capex growth", "value": "—",
                "remark": (f"Waiting on {len(pend['missing'])} of "
                           f"{len(capex['core'])} big spenders to report {pend['cq']}"
                           if pend else
                           "Needs two full quarters before it can be compared"),
                "tone": "na", "arrow": "none", "detail": detail,
                "asof": yoy[-1]["cq"] if yoy else "—"}
```

and the healthy return gains — note `word` already holds accelerating/decelerating/steady:

```python
    _CAPEX_REMARK = {"accelerating": "Up from {prev:+.1f}% — still building",
                     "decelerating": "Down from {prev:+.1f}% — easing off",
                     "steady": "Holding near {prev:+.1f}%"}
    return {"key": "capex", "label": "Capex", "sub": sub,
            "measure": "Capex growth",
            "value": f"{cur['yoy_pct']:+.1f}%",
            "remark": _CAPEX_REMARK[word].format(prev=prev["yoy_pct"]),
            "tone": "neutral", "arrow": arrow,
            "detail": (f"core YoY {cur['yoy_pct']:+.1f}% vs "
                       f"{prev['yoy_pct']:+.1f}% prior — {word}"),
            "asof": cur["cq"]}
```

Hoist `_CAPEX_REMARK` to module level beside `_BANNED_REMARK_TERMS`.

In `_rev_chip`, all three returns gain the fields. `measure` is `"Customer sales"` throughout:

```python
# na branch
        "measure": "Customer sales", "value": "—",
        "remark": "No sales-growth figures in the reports yet",

# young-corpus branch
        "measure": "Customer sales", "value": f"{now_med:+.1f}%",
        "remark": "Not enough history yet to show a trend",

# trend branch — add beside the tone/arrow/word assignment:
    ref_month = datetime.strptime(ref_date, "%Y-%m-%d").strftime("%b")
    _REV_REMARK = {"rising": f"Up from {ref_med:+.1f}% in {ref_month}",
                   "falling": f"Down from {ref_med:+.1f}% in {ref_month} — buyers slowing",
                   "flat": f"Unchanged since {ref_month}"}
    ...
        "measure": "Customer sales", "value": f"{now_med:+.1f}%",
        "remark": _REV_REMARK[word],
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/test_capex.py -v`
Expected: PASS — all 40 existing tests plus the 4 new ones.

- [ ] **Step 5: Commit**

```bash
git add lib/capex.py tests/test_capex.py
git commit -m "feat(capex): plate fields on the capex and sales chips"
```

---

### Task 2: `measure`/`value`/`remark` on the coverage-gap chip

This is the task that fixes the bug the whole rework exists for: the remark must
reconcile the gap's revenue figure with the sales chip's, in the same row.

**Files:**
- Modify: `lib/capex.py:280-301` (`_gap_chip`)
- Test: `tests/test_capex.py`

**Interfaces:**
- Consumes: `_BANNED_REMARK_TERMS` from Task 1.
- Produces: the `gap` chip's `measure` carries the quarter — `"Coverage gap (2026Q1)"`.

- [ ] **Step 1: Write the failing tests**

```python
def test_gap_chip_remark_reconciles_with_current_sales():
    """The bug this rework exists for: the gap's revenue figure and the sales
    chip's disagree because they cover different periods. The remark must say so."""
    capex, fund = _gap_fixture_negative_with_forward_note()
    chip = [c for c in build_chips(capex, fund, date(2026, 7, 22))
            if c["key"] == "gap"][0]
    assert chip["measure"].startswith("Coverage gap (")
    assert chip["value"].endswith("pp")
    assert "only" in chip["remark"]          # names the period limit
    assert "since" in chip["remark"]         # carries the forward clause


def test_gap_chip_remark_omits_forward_clause_when_note_absent():
    capex, fund = _gap_fixture_no_forward_note()
    chip = [c for c in build_chips(capex, fund, date(2026, 7, 22))
            if c["key"] == "gap"][0]
    assert "since" not in chip["remark"]
    assert chip["remark"]


def test_gap_chip_degraded_keeps_dash_value():
    chip = [c for c in build_chips({"core": [], "series": {}, "fragile": [],
                                    "beneficiaries": [], "warnings": []},
                                   _empty_fund_df(), date(2026, 7, 22))
            if c["key"] == "gap"][0]
    assert chip["value"] == "—"
    assert chip["remark"] == "Needs at least one complete spending quarter"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_capex.py -k gap_chip -v`
Expected: FAIL — `KeyError: 'measure'`

- [ ] **Step 3: Implement**

`_gap_chip` already receives `capex` and `fund_df`, which is exactly
`forward_revenue_note`'s signature — so it can build the forward clause itself
with no signature change.

```python
def _gap_chip(capex: dict, fund_df: pd.DataFrame) -> dict:
    sub = ("beneficiary revenue growth minus capex growth — "
           "negative = spend outrunning sales")
    gaps = coverage_gap_series(capex, fund_df)
    if not gaps:
        return {"key": "gap", "label": "Coverage gap", "sub": sub,
                "measure": "Coverage gap", "value": "—",
                "remark": "Needs at least one complete spending quarter",
                "tone": "na", "arrow": "none", "detail": "needs capex data",
                "asof": "—"}
    g = gaps[-1]
    widening = len(gaps) >= 2 and (g["gap_pp"] - gaps[-2]["gap_pp"]) <= -GAP_WIDEN_PP
    if g["gap_pp"] < 0:
        tone = "watch"
        word = "negative and widening" if widening else "capex outrunning revenue"
    elif widening:
        tone, word = "watch", "narrowing fast"
    else:
        tone, word = "good", "revenue keeping pace"
    # The reconciliation (spec §2 rule 4). The gap is anchored to the last
    # complete quarter, so its sales figure is older than the sales row's. Say
    # that in the same row as the number, at full text weight — the 2026-07-03
    # pass put this in an --ink-3 footnote and the reader never reached it.
    remark = (f"{g['cq']} only: spending grew {g['capex_yoy_pct']:+.1f}% "
              f"against sales {g['rev_growth_pct']:+.1f}%.")
    note = forward_revenue_note(capex, fund_df)
    if note is not None:
        remark += (f" Sales have since reached {note['now_pct']:+.1f}%, "
                   f"so the next reading should {note['hint']}.")
    return {"key": "gap", "label": "Coverage gap", "sub": sub,
            "measure": f"Coverage gap ({g['cq']})",
            "value": f"{g['gap_pp']:+.1f}pp",
            "remark": remark,
            "tone": tone, "arrow": "none",
            "detail": (f"{g['gap_pp']:+.1f}pp (rev {g['rev_growth_pct']:+.1f}% − "
                       f"capex {g['capex_yoy_pct']:+.1f}%) — {word}"),
            "asof": g["cq"]}
```

`forward_revenue_note` is defined at `lib/capex.py:220`, above `_gap_chip`, so
no import or reordering is needed.

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/test_capex.py -v`
Expected: PASS

Then confirm against real data that the two figures now reconcile on screen:

Run: `PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe -c "from lib.capex import *; from lib.data_loader import *; c=parse_capex(load_capex_quarterly()); f=fundamentals_history(load_all_reports()); [print(x['key'], '|', x['value'], '|', x['remark']) for x in build_chips(c,f,__import__('datetime').date(2026,7,22))]"`
Expected: the `gap` line reads `-18.6pp | 2026Q1 only: spending grew +68.9% against sales +50.3%. Sales have since reached +85.2%, so the next reading should narrow.`

- [ ] **Step 5: Commit**

```bash
git add lib/capex.py tests/test_capex.py
git commit -m "fix(capex): reconcile the gap's sales figure inside its own row"
```

---

### Task 3: `measure`/`value`/`remark` on the valuation and borrower chips

**Files:**
- Modify: `lib/capex.py:338-359` (`_val_chip`), `lib/capex.py:361-377` (`_fragile_chip`)
- Test: `tests/test_capex.py`

**Interfaces:**
- Consumes: `_BANNED_REMARK_TERMS` from Task 1.
- Produces: all five chips now carry `measure`/`value`/`remark`. Task 4 depends on this being complete.

- [ ] **Step 1: Write the failing tests**

```python
def test_val_chip_remark_avoids_percentile_and_peg_jargon():
    fund = _fund_fixture_five_reports()
    chip = [c for c in build_chips(_empty_capex(), fund, date(2026, 7, 22))
            if c["key"] == "val"][0]
    assert chip["measure"] == "Chip valuations"
    assert chip["value"].endswith("x")
    assert "range" in chip["remark"]


def test_fragile_chip_measure_is_plain_english():
    capex = _capex_fixture_with_amber_fragile()
    chip = [c for c in build_chips(capex, _empty_fund_df(), date(2026, 7, 22))
            if c["key"] == "fragile"][0]
    assert chip["measure"] == "Weakest borrower"
    assert chip["value"] == "CRWV"
    assert "Borrows" in chip["remark"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_capex.py -k "val_chip_remark or fragile_chip_measure" -v`
Expected: FAIL — `KeyError: 'measure'`

- [ ] **Step 3: Implement**

`_val_chip` — `peg_s` stays in `detail` only; the remark names the range in words:

```python
    # na branch
        "measure": "Chip valuations", "value": "—",
        "remark": "Needs at least five reports carrying chip valuations",

    # healthy branch
        "measure": "Chip valuations",
        "value": f"{pe_now:.1f}x",
        "remark": (f"Above its own recent range — {pe_hot:.1f}x is the usual high"
                   if rich else
                   f"Inside its own recent range — {pe_hot:.1f}x is the usual high"),
```

`_fragile_chip` — the note's jargon ("circularity node") stays in `detail`:

```python
    # na branch
        "measure": "Weakest borrower", "value": "—",
        "remark": "No borrower rows in the spending file",

    # healthy branch — add beside the existing `tone` assignment:
    _FRAGILE_REMARK = {
        "stress": (f"Under strain funding ${row['capex_usd_b']:.1f}B of spending "
                   f"— the first to struggle if money tightens"),
        "watch": (f"Borrows to fund ${row['capex_usd_b']:.1f}B of spending "
                  f"— watch this one first if money tightens"),
        "good": f"Spending ${row['capex_usd_b']:.1f}B with no strain flagged",
    }
    ...
        "measure": "Weakest borrower",
        "value": tk,
        "remark": _FRAGILE_REMARK[tone],
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/test_capex.py -v`
Expected: PASS — the banned-vocabulary test from Task 1 now covers all five chips.

- [ ] **Step 5: Commit**

```bash
git add lib/capex.py tests/test_capex.py
git commit -m "feat(capex): plate fields on the valuation and borrower chips"
```

---

### Task 4: `_datasheet_html` replaces the three HTML builders

**Files:**
- Modify: `components/briefing/capex_pulse.py:83-144` (delete `_verdict_html`, `_hero_gap_html`, `_signals_html`), `components/briefing/capex_pulse.py:197-220` (`render_capex_pulse`)
- Test: `tests/test_capex_pulse.py`

**Interfaces:**
- Consumes: chips carrying `measure`/`value`/`remark` from Tasks 1–3.
- Produces: `_datasheet_html(verdict: dict, chips: list[dict]) -> str`, emitting one `<table class="capex-sheet">`.

- [ ] **Step 1: Write the failing test**

Replace the three tests `test_verdict_html_renders_label_and_gloss_and_escapes`,
`test_hero_gap_html_shows_asof_and_forward_note`,
`test_hero_gap_html_omits_note_when_none`,
`test_hero_gap_html_escapes_forward_note_fields` and
`test_signals_html_renders_arrows_labels_sublabels_and_key` with:

```python
from components.briefing.capex_pulse import _datasheet_html

_VERDICT = {"state": "digesting", "label": "DIGESTING", "tone": "watch",
            "gloss": "Spending is outrunning the revenue it produces."}


def _chip(key, measure, value, remark, tone="good"):
    return {"key": key, "measure": measure, "value": value, "remark": remark,
            "tone": tone, "label": measure, "sub": "", "detail": "", "arrow": "none"}


def test_datasheet_renders_verdict_and_one_row_per_chip():
    chips = [_chip("capex", "Capex growth", "+68.9%", "Up from +61.9%"),
             _chip("rev", "Customer sales", "+85.2%", "Unchanged since May")]
    html = _datasheet_html(_VERDICT, chips)
    assert "DIGESTING" in html
    assert html.count("<tr") == 3          # header row + two data rows
    assert "Capex growth" in html and "+68.9%" in html and "Up from +61.9%" in html
    assert "01" in html and "02" in html   # sequential numbering


def test_datasheet_numbers_rows_without_holes():
    chips = [_chip("a", "A", "1", "x"), _chip("b", "B", "2", "y"),
             _chip("c", "C", "3", "z")]
    html = _datasheet_html(_VERDICT, chips)
    for n in ("01", "02", "03"):
        assert f">{n}<" in html


def test_datasheet_escapes_html_metacharacters_in_remarks():
    chips = [_chip("a", "A & B", "<1", "P/E < 15 & rising")]
    html = _datasheet_html(_VERDICT, chips)
    assert "&lt;" in html and "&amp;" in html
    assert "<1" not in html.replace("&lt;1", "")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/test_capex_pulse.py -v`
Expected: FAIL — `ImportError: cannot import name '_datasheet_html'`

- [ ] **Step 3: Implement**

Delete `_verdict_html`, `_hero_gap_html` and `_signals_html` entirely. Add:

```python
def _datasheet_html(verdict: dict, chips: list) -> str:
    """The plate: verdict header + one row per chip (spec §1).

    Fixed geometry — widths come from the colgroup in theme.css's .capex-sheet,
    never from content. Tone appears once per row as a dot in the No. cell, not
    as a border on every block.
    """
    vcolor = _TONE_COLOR.get(verdict["tone"], INK_FALLBACK)
    rows = ""
    for i, c in enumerate(chips, start=1):
        rows += (
            f'<tr>'
            f'<td class="cs-no">{_dot(c["tone"])}{i:02d}</td>'
            f'<td class="cs-measure">{_escape_dollars(c["measure"])}</td>'
            f'<td class="cs-value">{_escape_dollars(c["value"])}</td>'
            f'<td class="cs-remark">{_escape_dollars(c["remark"])}</td>'
            f'</tr>')
    return (
        f'<table class="capex-sheet">'
        f'<colgroup><col class="c-no"><col class="c-measure">'
        f'<col class="c-value"><col class="c-remark"></colgroup>'
        f'<thead>'
        f'<tr class="cs-read"><td colspan="4">'
        f'<span class="cs-state" style="color:{vcolor};">'
        f'{_escape_dollars(verdict["label"])}</span> '
        f'<span class="cs-gloss">{_escape_dollars(verdict["gloss"])}</span>'
        f'</td></tr>'
        f'<tr class="cs-head"><th scope="col">No</th><th scope="col">Measure</th>'
        f'<th scope="col">Value</th><th scope="col">What it means</th></tr>'
        f'</thead><tbody>{rows}</tbody></table>')
```

In `render_capex_pulse`, the `st.markdown` block becomes:

```python
    st.markdown(
        "".join([
            _overdue_html(curation_age_days(capex, today)),
            _datasheet_html(verdict, [by_key[k] for k in
                                      ("capex", "rev", "gap", "val", "fragile")]),
        ]),
        unsafe_allow_html=True)
```

Note the order — `capex`, `rev`, **then** `gap`: spec §1 puts the two inputs
before the figure derived from them.

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/test_capex_pulse.py tests/test_capex.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add components/briefing/capex_pulse.py tests/test_capex_pulse.py
git commit -m "feat(capex): one datasheet plate replaces verdict, hero and tiles"
```

---

### Task 5: `.capex-sheet` styles

**Files:**
- Modify: `assets/theme.css` (append a new block; do **not** touch the `:root` signal palette at lines 1023-1035)

**Interfaces:**
- Consumes: the class names emitted in Task 4 — `.capex-sheet`, `.c-no`, `.c-measure`, `.c-value`, `.c-remark`, `.cs-read`, `.cs-state`, `.cs-gloss`, `.cs-head`, `.cs-no`, `.cs-measure`, `.cs-value`, `.cs-remark`.
- Produces: no Python interface.

- [ ] **Step 1: Add the block**

Append to `assets/theme.css`, before any trailing `@media` query (see commit
`8d6a615` — a block added *after* a trailing media query silently lands inside
it):

```css
/* ── AI Capex Pulse datasheet (spec 2026-07-22 §6) ──────────────
   Fixed geometry: every column is a declared width, nothing sizes to content —
   this is the fix for "the boxes are all differently sized" (the old tiles were
   flex: 1 1 200px). Rhythm: a 22px leading unit (14px body at 1.5, matching
   .card-body); every vertical value is 11px or 22px, nothing else. Ink is
   assigned per measured contrast on --paper-2: --ink 15.06:1 for the value,
   --ink-2 9.75:1 for measure and remark, --ink-3 5.03:1 for furniture.
   --ink-4 measures 2.51:1 and is never used for text here. */
.capex-sheet {
  width: 100%;
  table-layout: fixed;
  border-collapse: collapse;
  border: 1px solid var(--rule);
  font-size: 14px;
  line-height: 22px;
}
.capex-sheet col.c-no      { width: 3.5ch; }
.capex-sheet col.c-measure { width: 22%; }
.capex-sheet col.c-value   { width: 14%; }

.capex-sheet .cs-read td {
  padding: 11px 22px;
  border-bottom: 1px solid var(--rule);
}
.capex-sheet .cs-state {
  font-family: var(--mono);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.08em;
  white-space: nowrap;
}
.capex-sheet .cs-gloss { color: var(--ink-2); }

.capex-sheet .cs-head th {
  padding: 11px 22px;
  text-align: left;
  font-family: var(--mono);
  font-size: 10px;
  font-weight: 400;
  letter-spacing: 0.13em;
  text-transform: uppercase;
  color: var(--ink-3);
  border-bottom: 1px solid var(--rule);
}

.capex-sheet tbody td {
  padding: 11px 22px;
  vertical-align: baseline;
  border-bottom: 1px solid var(--rule);
}
.capex-sheet tbody tr:last-child td { border-bottom: 0; }
.capex-sheet .cs-no {
  padding-right: 0;
  font-family: var(--mono);
  font-size: 11px;
  color: var(--ink-3);
  white-space: nowrap;
}
.capex-sheet .cs-measure { color: var(--ink-2); }
.capex-sheet .cs-value {
  font-family: var(--mono);
  font-variant-numeric: tabular-nums;
  color: var(--ink);
  white-space: nowrap;
}
.capex-sheet .cs-remark { color: var(--ink-2); }

@media (max-width: 720px) {
  /* Phone: the four columns cannot hold their declared widths, so each row
     becomes its own small plate — number and measure on one line, the value
     beneath, the remark last. Reading order is unchanged. */
  .capex-sheet, .capex-sheet tbody, .capex-sheet tbody td { display: block; }
  .capex-sheet thead .cs-head { display: none; }
  .capex-sheet tbody tr {
    display: grid;
    grid-template-columns: max-content 1fr;
    column-gap: 11px;
    padding: 11px 0;
    border-bottom: 1px solid var(--rule);
  }
  .capex-sheet tbody td { padding: 0 22px; border-bottom: 0; }
  .capex-sheet .cs-value, .capex-sheet .cs-remark { grid-column: 1 / -1; }
}
```

- [ ] **Step 2: Verify the block did not land inside a media query**

Run: `.venv/Scripts/python.exe -c "import re,pathlib; css=pathlib.Path('assets/theme.css').read_text(encoding='utf-8'); i=css.index('.capex-sheet'); print('braces open before block:', css[:i].count('{')-css[:i].count('}'))"`
Expected: `braces open before block: 0`

- [ ] **Step 3: Confirm the palette guard still passes**

Run: `.venv/Scripts/python.exe -m pytest tests/test_design_tokens.py -v`
Expected: PASS

- [ ] **Step 4: Look at it**

```bash
TEST_DATE=2026-07-22 LIVE_QUOTES_DISABLED=1 .venv/Scripts/python.exe -m streamlit run dashboard.py \
  --server.headless true --server.port 8599 --server.address 127.0.0.1 &
```

Open `http://127.0.0.1:8599/` and scroll to AI Capex Pulse. Check: all five rows
align on the same column edges; the remark column is the same body weight as the
measure column; no row has its own border; the verdict is the only colored text
besides the row dots.

- [ ] **Step 5: Commit**

```bash
git add assets/theme.css
git commit -m "style(capex): fixed-geometry datasheet plate on a 22px rhythm"
```

---

### Task 6: Page-level test, changelog, baselines

**Files:**
- Modify: `tests/test_capex_pulse.py`, `data/changelog.json`, `tests/visual/baselines/briefing.png`

**Interfaces:**
- Consumes: everything from Tasks 1–5.
- Produces: none.

- [ ] **Step 1: Write the failing AppTest**

```python
from streamlit.testing.v1 import AppTest

from components.briefing.capex_pulse import render_capex_pulse


def test_capex_pulse_renders_the_plate_end_to_end():
    at = AppTest.from_function(render_capex_pulse).run(timeout=30)
    assert not at.exception
    html = "".join(m.value for m in at.markdown)
    assert "capex-sheet" in html
    assert "What it means" in html
    assert "Weakest borrower" in html
```

`AppTest.from_function` is required — driving a non-default page through
`dashboard.py` resets navigation to the default page.

- [ ] **Step 2: Run it**

Run: `.venv/Scripts/python.exe -m pytest tests/test_capex_pulse.py::test_capex_pulse_renders_the_plate_end_to_end -v`
Expected: PASS (Tasks 1–5 already implement it; this is the integration guard)

- [ ] **Step 3: Add the changelog entry**

Prepend to `data/changelog.json`, preserving UTF-8 + CRLF:

```python
import json, pathlib
p = pathlib.Path("data/changelog.json")
entries = json.loads(p.read_text(encoding="utf-8"))
entries.insert(0, {
    "date": "2026-07-22",
    "title": "The AI Capex Pulse now explains itself",
    "note": (
        "Every figure in the AI Capex Pulse now sits beside a plain-English line "
        "saying what it means, in one table instead of six separate boxes. The "
        "coverage gap moved below the two numbers it is calculated from, and it "
        "now says in the same row why its sales figure differs from the one above "
        "it — the gap is anchored to the last completed quarter, while the sales "
        "row is current. Jargon like PEG, percentiles and 'circularity node' has "
        "moved into the History panel. Nothing was removed and no figure changed."),
})
p.write_bytes((json.dumps(entries, indent=2, ensure_ascii=False) + "\n")
              .replace("\n", "\r\n").encode("utf-8"))
```

- [ ] **Step 4: Full suite**

Run: `.venv/Scripts/python.exe -m pytest tests -q --ignore=tests/visual`
Expected: PASS, count >= 397 + the new tests

- [ ] **Step 5: Regenerate the visual baseline**

**PowerShell, not Git Bash** (Docker path translation mangles the mount under
Git Bash):

```powershell
docker run --rm -v "${PWD}:/work" -w /work mcr.microsoft.com/playwright/python:v1.60.0-jammy bash -lc "pip install -q -r requirements.lock playwright==1.60.0 pytest-playwright pixelmatch pillow && python -m playwright install chromium && VISUAL_UPDATE=1 python -m pytest tests/visual -q"
```

Then verify against the fresh baselines:

```powershell
docker run --rm -v "${PWD}:/work" -w /work mcr.microsoft.com/playwright/python:v1.60.0-jammy bash -lc "pip install -q -r requirements.lock playwright==1.60.0 pytest-playwright pixelmatch pillow && python -m playwright install chromium && python -m pytest tests/visual -q"
```

Expected: 22 passed. Only `briefing.png` should differ — if other baselines move,
stop and investigate before committing.

- [ ] **Step 6: Commit**

```bash
git add tests/test_capex_pulse.py data/changelog.json tests/visual/baselines/
git commit -m "test(capex): end-to-end plate render, changelog, baselines"
```

---

## Self-Review

**Spec coverage:** §1 plate → Tasks 1–4. §1 rename table → Tasks 1–3 (`measure`).
§2 column contract → Tasks 1–3; remark rules 1–4 → banned-vocabulary test (Task 1)
and the gap reconciliation (Task 2). §3 renderer changes → Task 4. §4 degradation →
degraded-path tests in Tasks 1–3, as corrected above. §5 testing → Tasks 1–4, 6.
§6 typographic contract → Task 5.

**Type consistency:** `measure`/`value`/`remark` are `str` on every chip in every
branch, including degraded ones. `_datasheet_html(verdict: dict, chips: list) -> str`
is defined in Task 4 and used only there. `_BANNED_REMARK_TERMS` is defined in
Task 1 and consumed by the test added in the same task.

**Known gap:** the plan reuses fixtures from `tests/test_capex.py` by name
(`_capex_fixture_two_quarters`, `_rev_fixture_flat`, `_gap_fixture_negative_with_forward_note`,
`_fund_fixture_five_reports`, `_capex_fixture_with_amber_fragile`, `_empty_capex`,
`_empty_fund_df`). Several exist only as inline setup inside existing tests. Task 1
Step 1 instructs lifting them to module-level helpers first; do that before writing
the new tests.
