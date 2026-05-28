# Market Dashboard Redesign Plan

## Overview

This plan covers the editorial UI/UX upgrade for the market-dashboard project (`C:\Users\laize\Desktop\market-dashboard`). The production surface is **Streamlit** — `dashboard.py` (~3617 lines), run with `streamlit run dashboard.py`. It renders editorial HTML via `st.markdown(unsafe_allow_html=True)` over Streamlit's native widget primitives and injects its theme from `assets/theme.css` (~604 lines) at startup.

- **Part 1** modularizes `dashboard.py` into a `components/` Python package so each editorial section (Stance, Pulse, Changes, ActionCard, Macro, Calendar, Watchlist, etc.) lives in its own file, with a shared `lib/` helper layer for catalog constants, formatters, pills, and a new `card_container()` primitive.
- **Part 2** modernizes the visual layout — card primitive, named-lane grid, OKLCh signal tints, refined Watchlist row + ContextBand interactive states, motion tokens — implemented as HTML/CSS additions to `assets/theme.css` and session-state-driven re-renders inside the Streamlit shell.

The deliverable does not change `live_prices.py`, the `assets/catalog.json` schema, or the `data/morning_report_*.json` JSON shape. The previously-explored React surface and Vite setup have been removed; this plan supersedes both.

---

## Part 1 — Modular Refactor of dashboard.py

### 1.1 Target File Tree

```
C:\Users\laize\Desktop\market-dashboard\
├── dashboard.py                       # shrinks to ~250 lines: routing + sidebar
├── live_prices.py                     # unchanged
├── data/                              # JSON reports (per-day) — unchanged
├── assets/
│   ├── catalog.json                   # unchanged data contract
│   └── theme.css                      # tokens + selectors (single CSS source)
├── lib/
│   ├── __init__.py
│   ├── catalog.py                     # SIGNAL_COLORS / TINTS / VERBS, RETIRED_TICKERS
│   ├── formatters.py                  # _escape_dollars, _truncate_rationale, _metric_bg, _fmt_*
│   ├── pills.py                       # _signal_pill_html, _render_live_caption
│   ├── cards.py                       # card_container(), section_head() — Part-2 primitives
│   ├── data_loader.py                 # @st.cache_data loaders (reports, prices)
│   └── state.py                       # session-state helpers (expanded rows, page, filters)
└── components/
    ├── __init__.py
    ├── masthead.py                    # Masthead + topnav radio       (dashboard.py:2000–2029)
    ├── briefing/
    │   ├── __init__.py                # render_briefing() orchestrator
    │   ├── stance.py                  # render_stance                 (803–829)
    │   ├── pulse.py                   # render_pulse                  (874–889)
    │   ├── changes.py                 # render_changes                (892–926)
    │   ├── action_card.py             # render_action_card + summary  (948–1085)
    │   ├── catalyst_playbook.py       # render_catalyst_playbook      (1174–1245)
    │   ├── contrarians.py             # render_contrarian_candidates  (1247–1289)
    │   ├── interconnected.py          # render_interconnected         (1345–1389)
    │   ├── macro.py                   # render_macro                  (1088–1171)
    │   └── calendar.py                # render_calendar               (1292–1342)
    ├── watchlist/
    │   ├── __init__.py
    │   ├── watchlist.py               # render_watchlist              (1392–1417)
    │   ├── row.py                     # _render_ticker_details_html   (1925–1978)
    │   └── drilldown.py               # _render_drilldown_detail_html (1436–1922) — largest unit
    ├── signal_tracker.py              # page == "Signal Tracker" body (2239–2528)
    ├── scenario_log.py                # page == "Scenario Log" body   (2533–2617)
    ├── pipeline_stats.py              # page == "Pipeline Stats" body (2622–2902)
    ├── report_comparison.py           # page == "Report Comparison"   (2907–3162)
    └── terminology.py                 # page == "Terminology" body    (3167–3616)
```

**Grouping rationale.**
- `lib/` holds pure helpers — no Streamlit calls in constants/formatters modules; only `data_loader.py` and `state.py` touch `st`.
- `components/briefing/` is the busiest namespace because the Briefing page composes ten render calls; flattening would make imports unreadable.
- `components/watchlist/` splits row from drilldown because `_render_drilldown_detail_html` is the largest single function in the codebase (~490 lines of HTML templating) and warrants its own file even before any new work.
- Page-level modules (`signal_tracker.py`, etc.) are flat siblings — they share `lib/` but not each other.

### 1.2 Function Dependency Analysis

Cross-cutting symbols and their new homes:

| Symbol | Today's location | New home |
|---|---|---|
| `_CATALOG`, `RETIRED_TICKERS` | `dashboard.py:23, 27` | `lib/catalog.py` |
| `SIGNAL_COLORS`, `SIGNAL_ST_COLORS`, `SIGNAL_VERBS` | `dashboard.py:594, 597, 599` | `lib/catalog.py` |
| `SIGNAL_TINTS` (currently inline rgba strings) | scattered inside renderers | `lib/catalog.py` — promote to module constant |
| `_escape_dollars`, `_truncate_rationale` | `dashboard.py:39, 44` | `lib/formatters.py` |
| `_metric_bg` (threshold→color) | inline | `lib/formatters.py` |
| `_signal_pill_html` | `dashboard.py:784` | `lib/pills.py` |
| `render_section_head` | `dashboard.py:795` | `lib/cards.py` (reused by every card) |
| `_render_signal_guide` | `dashboard.py:602` | `components/masthead.py` (sidebar-adjacent) |
| `_render_live_caption` | `dashboard.py:844` | `lib/pills.py` |
| `load_all_reports`, `load_sqlite_prices` (cached) | `dashboard.py:133–179` | `lib/data_loader.py` |
| Page router, sidebar filters | `dashboard.py:2030–2135` | stays in `dashboard.py` |

**Per-component reads:**

| Component | Reads from report dict | Reads from `lib/` | Streamlit calls |
|---|---|---|---|
| `masthead` | `meta.report_date`, `meta.market_date` | — | `st.markdown`, `st.radio` |
| `stance` | `portfolio_snapshot.{overall_stance, risk_posture, signal_counts}` | `catalog.SIGNAL_COLORS` | `st.markdown` |
| `pulse` | `benchmarks.*` | `formatters._fmt_pct` | `st.markdown` |
| `changes` | today_wl vs prev_wl diff | `catalog.*`, `pills._signal_pill_html`, `formatters._truncate_rationale` | `st.markdown`, `st.expander` |
| `action_card` | `watchlist`, `events_this_week` | `catalog.SIGNAL_COLORS`, `pills._signal_pill_html` | `st.markdown` |
| `macro` | `geopolitical.{macro_summary, portfolio_action, probabilities, active_risks}` | `cards.card_container`, `cards.section_head` | `st.markdown` |
| `calendar` | `events_this_week` | `formatters._fmt_date` | `st.markdown` |
| `watchlist.row` | `watchlist[ticker]` | `pills._signal_pill_html`, `formatters._metric_bg` | `st.markdown` |
| `watchlist.drilldown` | `watchlist[ticker]` (full detail) | every formatter + pill helper | `st.markdown` |
| `signal_tracker` (page) | episodes, calibration | `data_loader.*` | `st.dataframe`, `st.plotly_chart` |

**Shared state:**
- `st.session_state.page` (written by `st.radio` in `dashboard.py:2020–2029`) — already implicit; formalize in `lib/state.py`.
- `st.session_state.expanded_rows` (new, Part-2 watchlist expand) — lives in `lib/state.py` once Part-2 lands.
- `st.session_state.date_range`, `st.session_state.live_prices_enabled` — already exist; document them.

**No circular dependency risk:** `lib/` is leaf; `components/` only imports downward.

### 1.3 Extraction Order

Each step must leave `streamlit run dashboard.py` working. Streamlit hot-reloads on file save; verification is one `Ctrl+R` away.

| Step | Move | Why this order |
|---|---|---|
| 0 | Create empty `lib/`, `components/`, `components/briefing/`, `components/watchlist/` with `__init__.py`. Add no logic. | Confirm Python import paths resolve. |
| 1 | `lib/catalog.py` — `_CATALOG`, `RETIRED_TICKERS`, `SIGNAL_COLORS`, `SIGNAL_ST_COLORS`, `SIGNAL_VERBS`. Promote `SIGNAL_TINTS` to a constant. Import into `dashboard.py`. | Pure constants. |
| 2 | `lib/formatters.py` — `_escape_dollars`, `_truncate_rationale`, `_metric_bg`, any `_fmt_*` helpers. | Pure functions. |
| 3 | `lib/pills.py` — `_signal_pill_html`, `_render_live_caption`. | Leaf helpers. |
| 4 | `lib/data_loader.py` — `@st.cache_data` loaders. Verify cache survives the move (fast reload after first hit). | Cache decorators are sensitive to source location. |
| 5 | `components/briefing/stance.py` — `render_stance`. | Smallest editorial component; validates the pattern. |
| 6 | `components/briefing/pulse.py`, `changes.py`. | Pure-HTML renderers. |
| 7 | `components/briefing/action_card.py`. | Larger, but stateless. |
| 8 | `components/briefing/{catalyst_playbook,contrarians,interconnected}.py`. | Three similar siblings. |
| 9 | `components/briefing/macro.py`, `calendar.py`. | The two halves of the columned bottom region. |
| 10 | `components/watchlist/drilldown.py` — `_render_drilldown_detail_html`. | The ~490-line drilldown is the biggest single block; isolating first reduces blast radius for step 11. |
| 11 | `components/watchlist/row.py` (`_render_ticker_details_html`), then `components/watchlist/watchlist.py` (`render_watchlist`). | Detail panel is the riskiest single HTML; jargon branch + metric grid. |
| 12 | `components/masthead.py` — Masthead + topnav + `_render_signal_guide`. | Touches page state — saved late. |
| 13 | `components/{signal_tracker, scenario_log, pipeline_stats, report_comparison, terminology}.py` — extract each `elif page == "..."` block into a module-level `render_*()` function. | Self-contained tab bodies. |
| 14 | Reduce `dashboard.py` to: imports, `st.set_page_config`, theme injection, sidebar, page-routing `if/elif` calling `components/*`. ~250 lines. | Final cleanup. |

### 1.4 CSS Strategy

**Recommendation: keep `assets/theme.css` as the single source.** Add section banners as new selectors are introduced.

**Why not co-located `.css` per component:** Streamlit injects CSS via `st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)`. Each additional injection means a duplicate `<style>` block in the DOM and a separate cascade entry — chasing override conflicts becomes painful. One file, one injection at startup.

**Concrete CSS structure:**

```
assets/theme.css
  §1  Design tokens          (lines 7–20 today; add Part-2 motion + surface + radius tokens)
  §2  Streamlit chrome       (sidebar, .block-container, .topnav-wrap)
  §3  Shared primitives      (.eyebrow, .section-head, .card — NEW from Part 2)
  §4  Briefing sections      (.stance-*, .pulse-*, .changes-*, .action-*, .macro-*)
  §5  Calendar / Macro right column
  §6  Watchlist              (.tk-row, .tk-details summary, .tk-drilldown, .gauge, .rsi-bar)
  §7  Signal pills           (.sig-pill, .sig-{SIGNAL})
  §8  Motion + states        (NEW — keyframes, transitions; respects prefers-reduced-motion)
  §9  Responsive             (≤860 collapses grids)
```

**Token invariant:** every Streamlit visual override (sidebar, expander, dataframe, plotly bg) reads from the same `:root` tokens. The `[data-theme="ink"]` attribute selector (a relic of the deleted React side) is moot — Streamlit is currently dark-only. Treat the existing palette (`--paper: #14140F`, `--ink: #F4EFE2`, …) as the single theme; a light/paper mode is a possible future v2 (Open Question 4).

### 1.5 Verification Checkpoints

After **every** step, run the one-minute checklist:

1. **Terminal clean** — `streamlit run dashboard.py` starts with no `ImportError` / `ModuleNotFoundError` / `AttributeError` on rerun.
2. **Browser console clean** — no 404s, no JS errors.
3. **Page selector** — Briefing, Watchlist, Signal Tracker, Scenario Log, Pipeline Stats, Report Comparison, Terminology — each renders.
4. **Briefing order** — Stance → Pulse → Changes → Action Card → Trigger Map → Contrarians → Interconnected → Macro + Calendar.
5. **Watchlist drilldown** — `<details>` opens to show the drilldown HTML.
6. **Cache hits stable** — reload; `@st.cache_data` loaders should not re-fetch.
7. **Sidebar filters** — date range preset, date input, live-prices toggle, Refresh button.
8. **Signal Guide expander** opens.
9. **Visual regression spots:**
   - `<details>` summary row in Watchlist — grid alignment and `tk-details > summary:hover` styling.
   - `.macro-lead` paragraph + scenario odds bar — flexbox math is finicky.
   - `_render_drilldown_detail_html` jargon branches (technical vs plain).

### 1.6 Risks & Mitigations

- **Streamlit module re-runs.** Streamlit re-runs the script top-to-bottom on every interaction. Module-scope file I/O (e.g., `_CATALOG = json.loads(...)`) is acceptable for tiny reads but should not be added on top of existing reads. **Mitigation:** wrap any new file I/O in `@st.cache_data`. Pure dict/list constants are cheap to recompute.
- **`@st.cache_data` key stability.** Cached functions are keyed by argument values + serialized source. Moving a function to a new module changes its qualified name but not its source — caches survive. **Mitigation:** after step 4, confirm `Refresh Data` still clears caches; expect one cold miss after the refactor.
- **Circular imports.** `components/briefing/macro.py` will call `lib/cards.card_container()`. As long as `lib/` modules never import from `components/`, no cycles. **Mitigation:** enforce as a code-review rule; `lib/__init__.py` stays empty.
- **HTML string fragility.** Every renderer is f-string HTML with inline `style="..."`. One misplaced `}` breaks the page. **Mitigation:** rerun every page after each extraction; Streamlit's tracebacks pinpoint the line.
- **Stale `app.jsx`/`data.js` mirror comment.** `dashboard.py:22` still warns "Mirror to app.jsx/data.js manually." After Part 1, replace with: "Single source for signal palette + ticker metadata; consumed by `lib/catalog.py`."
- **`live_prices.py` import path.** `dashboard.py:15` imports `fetch_live_quotes`, `overlay_live`. The Briefing route uses both for the optional live overlay. **Mitigation:** the orchestration stays in `components/briefing/__init__.py`'s `render_briefing()` — don't scatter live-overlay logic across leaf components.
- **`data.js` is dead.** It's no longer referenced by `dashboard.py` (and was only ever consumed by the removed React app). Delete it in a follow-up commit unless an external tool reads it. (Open Question 3.)

---

## Part 2 — UI/UX Layout Upgrade

### 2.1 Concept Brief

**Working title: "Broadsheet, hinged."** The current Streamlit layout reads as a strong single-column newspaper page, but it does not flex. The redesign keeps the broadsheet sensibility (serif headlines, mono eyebrows, ink-on-paper restraint, hairline rules) while introducing a **hinged card system** where each editorial unit (ActionCard, Pulse, Macro, ContextBand, Watchlist) becomes a card hinged on a named lane in a 12-column grid. Hairline rules survive as inset dividers inside cards rather than as full-bleed separators between sections.

Editorial references:
- **Financial Times** — restrained type, salmon paper, full-bleed eyebrow tags.
- **The Economist** — strict grid, named sections, generous gutters.
- **NYT Daily** — the "if you only do one thing" treatment in the Action Card is already in that idiom; the upgrade strengthens it as a card with heavier rule above and below.
- **Bloomberg Terminal** — Watchlist density and tabular numerics. Borrow the left signal rail; discard the heavy darkness.

What we **preserve**: type families (Newsreader / Inter Tight / JetBrains Mono), OKLCh-style signal tokens (`--buy`, `--accumulate`, `--watch`, `--hold`, `--caution` + tint variants), the dark editorial palette, the eyebrow class rollup, mono numerics with `tnum`.

What we **modernize**: layout becomes lane-based instead of section-per-section vertical stacking; cards introduce a soft second surface tier; interactive states gain motion; the Watchlist `<details>` row uses a left signal rail; the Macro + Risks + Upcoming trio becomes a true band of related cards rather than a 2-up `st.columns([3, 2])`.

### 2.2 Grid System v2

12 columns, 24px gutter wide / 16px narrow, with **named lanes** so component CSS can place itself semantically. Lanes are expressed as CSS grid inside a Briefing wrapper emitted via `st.markdown(unsafe_allow_html=True)` — Streamlit's `st.columns` only handles proportional splits, so the lane grid lives in raw HTML.

```
Lane name      Cols (wide ≥1100)        Cols (mid 720–1099)    Cols (narrow <720)
─────────────────────────────────────────────────────────────────────────────────
lede            1–7  (7 cols)            1–8                    1–12
ledger          8–12 (5 cols)            9–12                   1–12
strip          1–12 (full)               1–12                   1–12
```

**Briefing page, wide viewport (≥1100px):**

```
┌──────────── strip (Masthead + topnav) ────────────────┐
├──────────── strip (Changes ribbon, if any) ───────────┤
│                                                       │
│  lede                          │ ledger               │
│  ┌─ Action Card ───────────┐   │ ┌─ Stance counts ─┐  │
│  │  headline · action      │   │ │ BUY ACC WATCH   │  │
│  │  if you only do one     │   │ │ HOLD CAUTION    │  │
│  └─────────────────────────┘   │ └─────────────────┘  │
│                                │                      │
├──── strip (Pulse: 8-col benchmarks, full bleed) ──────┤
│                                                       │
│  lede                          │ ledger               │
│  ┌─ Macro Note ────────────┐   │ ┌─ Risks ─────────┐  │
│  │  lede paragraph         │   │ │ tag · text      │  │
│  │  portfolio implication  │   │ │ tag · text      │  │
│  │  scenario odds (bar)    │   │ ├──── rule ──────┤  │
│  └─────────────────────────┘   │ │ Upcoming        │  │
│                                │ │ day · events    │  │
│                                │ └─────────────────┘  │
└───────────────────────────────────────────────────────┘
```

**Mapping today → tomorrow.**
- Today's `st.columns([3, 2])` (`dashboard.py:2190`) splits Macro + Calendar at 60/40. New grid splits at 7/5 ≈ 58/42 — visually nearly identical, but expressed inside the lane wrapper rather than via Streamlit's native column primitive.
- `render_action_card` (today single-row, embeds stance counts inline) → `lede` card; stance counts lift out into the `ledger` lane.
- `render_macro` (today one block) → `lede` Macro Note card; Risks and Upcoming move to stacked `ledger` cards.
- `render_calendar` (today a 40%-wide column) → becomes the Upcoming sub-card inside `ledger`. The full Calendar page is unchanged.
- `render_pulse` → full-width `strip`.
- `render_changes` → full-width `strip` (hides if empty).

### 2.3 Card System

**The card primitive — implemented as `lib/cards.py::card_container()`.** A Python helper that emits standardized HTML around an inner content string:

```python
def card_container(*, eyebrow: str, headline: str = "", body_html: str, lane: str = "lede") -> str:
    return f"""<div class="card" data-lane="{lane}">
      <div class="card-head">
        <span class="eyebrow">{eyebrow}</span>
        {f'<h2 class="card-headline">{headline}</h2>' if headline else ''}
      </div>
      <div class="card-body">{body_html}</div>
    </div>"""
```

| Property | Value | Rationale |
|---|---|---|
| Background | `--surface-1` (= `--paper-2`) | Tier-1 cards sit on `--paper`. |
| Nested surface | `--surface-2` (= `--paper-3`) | Stance count cells, metric rows. |
| Border | `1px solid var(--rule)` | Hairline, not shadow — editorial restraint. |
| Radius | `--radius-card: 4px` | Newspaper corners are sharp; 4px softens just enough. |
| Interior padding | `--card-pad-y/x` = 24/24 default, 16/16 compact | Driven by `[data-density]` switch (new). |
| Header zone | Eyebrow (mono uppercase) + optional sub. Bottom rule = `--rule`. | Reuses `.section-head` pattern. |
| Hover | None on containers. | Cards are containers; only their contents respond. |

**Why hairlines over shadows.** Soft shadows on `--paper` (dark cream) muddy the OKLCh signal palette. Hairlines stay neutral — same token, same look. We reserve a single low-elevation effect (`--shadow-card: 0 1px 0 var(--rule)`) for the Action Card only, reading as a printed double-rule.

```
┌──────────────────────────────────────────────┐
│  EYEBROW · MONO 10PX                         │  ← header (rule below)
│  ────────────────────────────────────────    │
│                                              │
│   Serif headline                             │
│   (Newsreader 22–32px)                       │
│                                              │
│   Sans-serif body paragraph, 14/1.5.         │
│   ─── inset rule ───                         │
│   Footer row · mono numerics    ↪ accent     │
│                                              │
└──────────────────────────────────────────────┘
   24px padding (relaxed) / 16px (compact)
```

**Density mode.** Extend the existing density story (currently implicit in `theme.css`) with a `[data-density]` attribute set on the lane wrapper. `compact` shrinks `--card-pad-*` and `--card-gap`. Type sizes stay the same — compactness is whitespace, not type. Toggle via a sidebar control in `lib/state.py`.

### 2.4 Watchlist Interactive States

The Watchlist row today uses HTML `<details>` (`_render_ticker_details_html` at `dashboard.py:1925–1978`). The native `<summary>` element provides browser-default Enter/Space toggling — keyboard a11y is free as long as we don't override it. New spec:

| State | Visual change | Motion |
|---|---|---|
| **Default** | Dark surface, hairline `--rule` between rows. Signal pill at column 3. | — |
| **Hover** | Row gains a 3px left rail in `var(--{signal})` at full saturation. Background washes to `var(--{signal}-tint)`. Cursor pointer. | `--dur-fast` ease-out on `background-color` + `border-left-color`. |
| **Focus-visible** | Same as hover + 2px `outline: 2px solid var(--ink)` on the `<summary>`. Browser-default — don't remove it. | Instant. |
| **Expanded** (`details[open]`) | Left rail stays. Background `var(--{signal}-tint)`. Chevron rotates 90deg. | Chevron `transform: rotate` over `--dur-fast`. Detail panel: `details[open] > .tk-drilldown { animation: slide-down --dur-base ease-out; }` — keyframes from `opacity:0; transform:translateY(-4px)` to `opacity:1; transform:none`. |
| **Signal-flash** (new) | If today's signal differs from yesterday's (already computed in `render_changes`), the new-signal pill pulses its `--{signal}-tint` once on first render. | Keyframes over `--dur-slow`. Once only. Guard with `prefers-reduced-motion` and an `st.session_state` `mounted` flag so Streamlit re-runs don't replay it. |

**Tint mapping (left rail color).**
- BUY → `--buy`, ACCUMULATE → `--accumulate`, WATCH → `--watch`, HOLD → `--ink-3` (intentionally muted), CAUTION → `--caution`.

**Keyboard a11y.** The `<details>`/`<summary>` element is keyboard-accessible by default (Tab focuses, Enter/Space toggles). Adding `tabindex="0"` to a wrapping `<details>` is unnecessary. **Arrow-key row navigation** is the only non-default behavior — Streamlit can't run inline JS, so this is dropped from v1 (Open Question 2).

**Detail panel layout.** Today's drilldown uses a 1.4fr/1fr grid inside `.tk-drilldown`. Keep the internal split; render it inside the row's tinted background. Cap detail max-height with a soft fade if content overflows (rare).

### 2.5 ContextBand Interactive States

Today the Macro + Calendar columns (`dashboard.py:2190`) read as two side-by-side blocks. Upgrade to a **band of three cards**: Macro Note (lede lane), Risks (ledger top), Upcoming (ledger bottom).

**Macro Note card.**
- Headline + portfolio-implication paragraph + Scenario odds bar.
- Scenario odds bar becomes **interactive** via CSS-only hover: each segment shows its label as a hover-overlay using `::after` content (no JS needed). Segments lift 1px on hover (`transform: translateY(-1px)`).
- Tooltip-style detail on hover (scenario name + one-line description) is **dropped from v1** because it requires either a real tooltip library or JS positioning — see Open Question 1.

**Risks card.**
- Each `.risk-card` row gets a 2px left dot keyed to severity (HIGH → `--caution`, MED → `--watch`, LOW → `--ink-3`).
- Severity is read from `geopolitical.active_risks[i].severity` if present, else inferred from the existing tag string (see Open Question 5 — schema confirmation).
- One-time "severity pulse" on first mount for HIGH only, gated by `prefers-reduced-motion` + session-state mounted flag.

**Upcoming card.**
- Each event becomes hover-interactive (highlight ticker, fully-saturated impact pill).
- Click on an event sets `st.session_state.page = "Watchlist"` (or future "Calendar" page) and scrolls to a day anchor. Implementation requires capturing the click in a Streamlit-native widget rather than HTML — likely a small `st.button` per row styled to look like the rest of the band (Open Question 6).

**Card-vs-band.** The three cards share a visual band via `--card-gap: 16px` — close enough to read as a unit, separated enough to read as distinct. No outer wrapper, no shared shadow.

### 2.6 Motion & Micro-interactions

```css
:root {
  --dur-fast: 120ms;
  --dur-base: 200ms;
  --dur-slow: 360ms;
  --ease-out:    cubic-bezier(0.2, 0.7, 0.1, 1);
  --ease-in-out: cubic-bezier(0.4, 0.0, 0.2, 1);
}
@media (prefers-reduced-motion: reduce) {
  :root { --dur-fast: 0ms; --dur-base: 0ms; --dur-slow: 0ms; }
  *, *::before, *::after {
    animation-duration: 0.001ms !important;
    transition-duration: 0.001ms !important;
  }
}
```

| Where | Property | Duration | Easing |
|---|---|---|---|
| Watchlist `<summary>` hover | `background-color`, `border-left-color` | `--dur-fast` | `--ease-out` |
| `details[open] > .tk-drilldown` enter | `opacity`, `transform` (keyframes) | `--dur-base` | `--ease-out` |
| Chevron rotate | `transform` | `--dur-fast` | `--ease-out` |
| Signal flash (first mount only) | `background-color` keyframes | `--dur-slow` | `--ease-out` |
| Scenario odds segment hover | `transform`, inset shadow | `--dur-fast` | `--ease-out` |
| Risk severity pulse (first mount, HIGH only) | `background-color` keyframes | `--dur-slow` | `--ease-out` |
| Streamlit page swap | not interceptable | — | — |

**Streamlit-specific rules.**
- Streamlit reruns the script on every widget interaction. CSS transitions on persistent elements work fine; **first-mount animations** (signal flash, severity pulse) must be gated by `st.session_state.has_mounted` so they don't replay on every rerun.
- Never animate `height` (jank). Use `grid-template-rows: 0fr → 1fr` with `min-height: 0` on the child if needed, or keyframe `opacity` + `transform: translateY`.
- Page swap fade is not feasible — Streamlit's rerender replaces the whole canvas before CSS sees the transition.

### 2.7 Token Additions

Add to `:root` in `assets/theme.css`. Do **not** modify existing palette tokens. Do **not** modify the OKLCh signal colors in `assets/catalog.json`.

```css
:root {
  /* — Surface tiers — */
  --surface-1: var(--paper-2);     /* card background */
  --surface-2: var(--paper-3);     /* nested / count cells, metric rows */

  /* — Radii — */
  --radius-card: 4px;
  --radius-pill: 3px;              /* formalize existing */
  --radius-control: 6px;           /* sidebar controls */

  /* — Elevation (sparing) — */
  --shadow-card: 0 1px 0 var(--rule);  /* Action Card only */

  /* — Motion — */
  --dur-fast: 120ms;
  --dur-base: 200ms;
  --dur-slow: 360ms;
  --ease-out:    cubic-bezier(0.2, 0.7, 0.1, 1);
  --ease-in-out: cubic-bezier(0.4, 0.0, 0.2, 1);

  /* — Card spacing — */
  --card-pad-y: 24px;
  --card-pad-x: 24px;
  --card-gap:   32px;

  /* — Focus — */
  --focus-ring: 0 0 0 2px var(--ink);

  /* — Grid lanes — */
  --grid-cols: 12;
  --grid-gutter: 24px;
}

[data-density="compact"] {
  --card-pad-y: 16px;
  --card-pad-x: 16px;
  --card-gap:   20px;
}
```

### 2.8 Migration Sequencing

Each step is independently mergeable and visually reviewable. **No big-bang.** Part-1 modular refactor lands first so Part-2 changes touch focused files instead of a 3617-line monolith.

1. **Tokens land first.** Add the new tokens to `:root` in `assets/theme.css`. No selectors use them yet. Pure token diff.
2. **`lib/cards.py` introduced** with `card_container()` and `section_head()`. Not yet wired into any renderer.
3. **Migrate Action Card** to `card_container()`. Highest-traffic section first — surfaces taste issues early.
4. **Migrate Stance counts** to its own ledger card (lift out of the Action Card region). Largest visual shift in the Briefing layout; gate behind a quick designer eyeball.
5. **ContextBand split** — Macro Note (lede) + Risks (ledger top) + Upcoming (ledger bottom). Replace `st.columns([3, 2])` with the lane wrapper.
6. **Watchlist row chrome** — left signal rail, hover wash, focus-visible styles. Detail-panel slide-down lands here. Signal-flash off until step 8.
7. **Scenario odds + Risks visual treatment** — segment lift on hover, severity dots on risks. Drop tooltip behavior to v2.
8. **Motion polish** — signal-flash + severity pulse, both gated on `st.session_state.has_mounted` and `prefers-reduced-motion`.
9. **Grid lanes formalized** — wrap the Briefing route in the named-lane CSS grid. Verify Watchlist, Signal Tracker, etc. tabs still hold (they don't use lanes; remain unchanged).
10. **Density audit** — walk `[data-density="compact"]` once it's wired to a sidebar control. Tune any card that feels cramped.

---

## Combined Rollout Timeline

| Phase | Sprint | Part-1 work (refactor) | Part-2 work (visual) |
|---|---|---|---|
| 0 | Day 1 | Steps 0–4 (`lib/` modules) | — |
| 1 | Day 2 | Steps 5–9 (briefing components) | Tokens land (Part 2.8 step 1) |
| 2 | Day 3 | Steps 10–11 (watchlist split) | `lib/cards.py` defined (step 2) |
| 3 | Day 4 | Steps 12–13 (masthead + page modules) | Action Card + Stance migrate (steps 3–4) |
| 4 | Day 5 | Step 14 (final `dashboard.py` cleanup) | ContextBand split (step 5) |
| 5 | Day 6 | — | Watchlist row chrome + states (step 6) |
| 6 | Day 7 | — | Odds + Risks visuals (step 7) |
| 7 | Day 8 | — | Motion polish + grid formalization + density audit (steps 8–10) |

Part-1 is fully complete before Part-2's structural cards land — restyling well-scoped components beats wrestling with the monolith.

---

## Open Questions

1. **Tooltip primitive.** Scenario odds and risk-row tooltips would lift the UX, but Streamlit has no inline JS. Options: (a) drop tooltips for v1 (recommended), (b) build a custom Streamlit component (`streamlit.components.v1.declare_component`), (c) lean on CSS `::after` content with `[data-tooltip]` attributes — limited but JS-free.
2. **Keyboard a11y scope.** `<details>`/`<summary>` covers Tab + Enter/Space natively. Arrow-key row navigation and Escape-to-collapse require JS, which Streamlit can't host inline. Confirm: drop arrow-key navigation from v1 (recommended) or build a custom component.
3. **`data.js` cleanup.** Unused after React removal. Confirm no external script (cron, deploy, snapshot tool) reads it before deleting.
4. **Light/paper mode.** The dark editorial palette is the only theme today. Adding a light mode (`[data-theme="paper"]`) is straightforward but unbudgeted. Defer to v2 unless explicitly wanted.
5. **Severity field on risks.** Part 2.5 reads `geopolitical.active_risks[i].severity`. Confirm whether the JSON schema (and the upstream report generator) populates it; if not, infer from tag string until the schema is extended.
6. **Click-into-Calendar from Upcoming.** Wiring a click on an HTML element to `st.session_state.page = "..."` requires a real Streamlit widget per row (e.g., `st.button`) rather than pure HTML. Confirm this trade-off (styled buttons inside the band) before building.
7. **Density toggle UI.** `[data-density="compact"]` needs a sidebar control. Confirm placement (sidebar vs. masthead) and whether it persists across sessions (`st.session_state` is per-session only; long-term persistence needs query params or a small JSON sidecar).

### Critical Files for Implementation

- `C:\Users\laize\Desktop\market-dashboard\dashboard.py`
- `C:\Users\laize\Desktop\market-dashboard\assets\theme.css`
- `C:\Users\laize\Desktop\market-dashboard\assets\catalog.json`
- `C:\Users\laize\Desktop\market-dashboard\live_prices.py`
- `C:\Users\laize\Desktop\market-dashboard\data\morning_report_*.json` (data contract)
