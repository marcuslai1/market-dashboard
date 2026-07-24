# MarketReport Dashboard — Design & Architecture Handoff

This brief explains how the dashboard is built so that any new design work can be
written in code that drops straight into the existing project. Read the whole
thing before writing code — the constraints at the bottom are as important as
the structure at the top.

---

## 1. What this is (and is not)

- A **Python Streamlit app** — run with `streamlit run dashboard.py`. There is
  **no React, no Vite, no JavaScript build step, no HTML files**. A previous
  React/Vite exploration was deleted; do not reintroduce one.
- The "website" look is achieved by **injecting custom HTML strings with
  `st.markdown(..., unsafe_allow_html=True)`**, styled by one central
  stylesheet, `assets/theme.css` (~1,750 lines of design tokens + selectors).
- The dashboard is a **presentation layer**. It renders daily JSON reports
  produced by an upstream pipeline (sibling repo `MarketReport`). Design work
  means UX, layout, and faithfulness to the data — never inventing new
  signals/analytics, and never changing the report JSON schema or
  `assets/catalog.json` schema.

## 2. File tree (the parts that matter)

```
market-dashboard/
├── dashboard.py            # ~500-line orchestrator: page config, theme CSS injection,
│                           #   st.navigation registry (real URLs), masthead call,
│                           #   sidebar controls (date range, density, live prices), dispatch
├── live_prices.py          # Yahoo live-quote fetch + overlay (do not modify)
├── assets/
│   ├── theme.css           # THE stylesheet. All tokens + selectors live here.
│   └── catalog.json        # Single source of truth: signal palette, ticker metadata
├── lib/                    # Shared helpers
│   ├── catalog.py          # SIGNAL_COLORS/TINTS/VERBS/ORDER etc., loaded from catalog.json
│   ├── formatters.py       # Pure formatters — MUST NOT import streamlit; html-escaping lives here
│   ├── pills.py            # Signal pill HTML, live caption
│   ├── cards.py            # card_container(), render_section_head() — the card primitive
│   ├── charts.py           # Plotly dark-editorial styling (style_fig, PLOTLY_CONFIG, palette)
│   ├── data_loader.py      # @st.cache_data loaders (reports, prices, text assets)
│   ├── filters.py, state.py, clock.py, capex.py
├── components/             # One file per editorial section / page
│   ├── masthead.py         # Masthead + top-nav radio
│   ├── briefing/           # Briefing page sections: stance, pulse, changes, clusters,
│   │                       #   calibration, earnings, action_card, catalyst_playbook,
│   │                       #   contrarians, capex_pulse, macro, calendar
│   ├── watchlist/          # watchlist.py (list), row.py (ticker row), drilldown.py (detail)
│   ├── signal_tracker.py, retrospective.py, scenario_log.py,
│   ├── pipeline_stats.py, report_comparison.py, terminology.py,
│   ├── paper_book.py, trim_experiment.py
├── data/                   # morning_report_YYYY-MM-DD.json (one per trading day),
│                           #   changelog.json, capex_quarterly.json, earnings_cascades.json,
│                           #   market_data.csv, claude_analysis.csv
└── tests/                  # pytest: AppTest page tests, unit tests per component,
    └── visual/             #   Playwright/Docker pixel baselines (regen needed after UI edits)
```

## 3. How a page renders (the core pattern)

1. `dashboard.py` defines one `_page_*()` function per page and registers them
   with `st.navigation` (`position="hidden"`), giving each page a real URL
   (`/briefing`, `/watchlist`, …). The visible nav is a custom masthead
   (`components/masthead.py`) that mirrors into `st.switch_page`.
2. Page bodies that show live prices are wrapped in
   `@st.fragment(run_every=60 if LIVE_PRICES else None)` so the Yahoo fetch
   never blocks the masthead/sidebar paint and auto-refreshes in isolation.
3. Each section component is a `render_*(data)` function that **builds an HTML
   string** using CSS classes from `theme.css`, then emits it with a single
   `st.markdown(html, unsafe_allow_html=True)` call. Example
   (`components/briefing/pulse.py`): builds `.pulse-grid > .pulse-cell` divs
   with `aria-label`s, one markdown call at the end.
4. Sections that must sit side-by-side are concatenated into **one** markdown
   call inside a `.lane-wrapper` div, because CSS grid only sees siblings
   emitted in the same call.
5. Native Streamlit widgets (`st.selectbox`, `st.radio`, `st.toggle`,
   `st.button`, `st.plotly_chart`) are used **only for controls and charts** —
   all presentational content is custom HTML.
6. Data comes exclusively through `lib/data_loader.py` (`@st.cache_data`,
   mtime-keyed). Never read files directly in a component.

### Shared primitives — use these, don't reinvent

```python
from lib.cards import card_container, render_section_head

# Section header: serif <h2> left, mono sub right
render_section_head("The Watchlist", "31 names · click any row to expand")

# Card: returns an HTML string (caller does the st.markdown)
html = card_container(
    eyebrow="MACRO",            # mono, uppercase, letter-spaced
    headline="Macro note",      # serif, 22px
    body_html="...",            # escaped content
    lane="lede",                # "lede" | "ledger" | "strip" — grid placement
)
```

Lane grid (in `theme.css`): `.lane-wrapper` is a 12-column grid;
`data-lane="lede"` spans columns 1–7, `"ledger"` 8–12, `"strip"` full width.
Collapses to single column on narrow viewports.

### Escaping (security-tested)

All report-sourced text must pass through `html.escape` /
`lib.formatters._escape_attr` (and `_escape_dollars` for `$` in prose, which
Streamlit would otherwise render as LaTeX). `tests/test_rendering_security.py`
enforces this. Formatters in `lib/formatters.py` are pure (no streamlit
import) so they stay unit-testable.

## 4. The design system ("dark editorial broadsheet")

Everything is tokenized in `:root` of `assets/theme.css`. **New CSS must use
`var(--token)` — never hardcode colors, radii, or durations.**

**Surfaces (ink on newsprint):**
`--paper #14140F` (page) → `--paper-2 #1B1B16` (card) → `--paper-3 #25241E`
(nested) → `--surface-3 #2F2E26` (hover lift). Aliased as `--surface-0..3`.

**Ink ramp:** `--ink #F4EFE2` (headlines) → `--ink-2 #C9C2B2` (body) →
`--ink-3 #908A7C` (captions/eyebrows) → `--ink-4 #5E5A50` (disabled).

**Rules:** hairlines only — `--rule rgba(255,255,255,0.08)`,
`--rule-strong rgba(255,255,255,0.20)`. No heavy borders, minimal shadows
(`--shadow-card` is a 1px rule; elevation is used sparingly, Action Card only).

**Type:** three families with strict roles —
- `--serif` **Newsreader** — headlines, card headlines, editorial voice
- `--sans` **Inter Tight** — body/UI text
- `--mono` **JetBrains Mono** — all numbers, eyebrows, labels (uppercase +
  letter-spacing `0.13–0.18em`, 10–11px)

**Signal palette** (semantic, from `assets/catalog.json`; CSS mirrors it and
`tests/test_design_tokens.py` fails if they drift):
BUY `#22c55e` · ACCUMULATE `#3498db` · WATCH `#f59e0b` · HOLD `#6b7280` ·
CAUTION `#ef4444` · AVOID `#b91c1c`, each with an `rgba` tint for backgrounds.
Signal colors mean signals and **nothing else**.

**Chart palette** (in `lib/charts.py`) is deliberately different so a series
never reads as a signal: `CHART_ACCENT #C9A66B` (warm brass primary),
`CHART_MUTED #5E5A50`. All Plotly figures go through `style_fig()` and use
`PLOTLY_CONFIG` (modebar hidden, no zoom).

**Spacing/radii/motion:** `--card-pad-y/x 24px`, `--card-gap 32px` (compact
density swaps to 16/16/20 via an injected `:root` override), radii are small
(`--radius-card 4px`, `--radius-pill 3px`), motion tokens `--dur-fast 120ms /
--dur-base 200ms / --dur-slow 360ms` with `--ease-out`; `prefers-reduced-motion`
zeroes all durations. One-shot intro animations are gated by session state
(`is_first_mount()` in `dashboard.py`), not by CSS alone.

**Voice:** every band leads with a plain-English verdict — the "so what" —
before any metric grid. Dense jargon-first layouts get rejected.

## 5. Pages

| URL | Page | Notes |
|---|---|---|
| `/briefing` | Briefing (default) | Stance band → banners → pulse tape → changes → clusters → calibration → earnings → action card → catalyst playbook → contrarians → capex pulse → macro/risks/calendar band |
| `/watchlist` | Watchlist | Date selector, expandable ticker rows (`<details>` elements), drilldown |
| `/signal-tracker` | Signal Tracker | Date-filtered, memoized derived frames |
| `/retrospective` | Retrospective | Own month picker, not sidebar-filtered |
| `/scenario-log`, `/pipeline-stats`, `/report-comparison`, `/terminology` | Analysis/reference pages | Date-filtered where applicable |

Page modules other than Briefing/Watchlist are **lazily imported inside their
page functions** (and cached by Python) — an edit to them needs a Streamlit
server restart to show up.

## 6. Hard constraints for any new code

1. **No new dependencies.** `requirements.txt` is exactly: `streamlit
   (>=1.39,<1.59 — the cap is deliberate, 1.59 breaks nav-tab CSS)`, `pandas`,
   `plotly`, `yfinance`. No JS libraries, no CSS frameworks, no component
   packages. A strict environment means custom HTML + theme.css is the only
   styling channel.
2. **All CSS goes into `assets/theme.css`**, using existing tokens. Note the
   file ends with media queries — new selector blocks must be inserted
   **before** the trailing media-query section, or the responsive overrides
   stop winning.
3. **Do not touch the data contracts**: `data/morning_report_*.json` shape,
   `assets/catalog.json` schema, `live_prices.py`.
4. **Comments document deliberate choices.** Apparent inconsistencies in the
   UI are usually intentional and explained in an adjacent comment — read the
   rationale before "fixing" anything.
5. **Tests gate everything**: unit tests per component, `AppTest` page smoke
   tests (note: `AppTest` can't drive widgets on non-default pages through
   `dashboard.py` — test pages via `AppTest.from_function`), design-token
   drift test, rendering-security (escaping) test, and pixel-level visual
   baselines under `tests/visual/` that must be regenerated (Docker) after any
   visible change.
6. **User-visible changes require a `data/changelog.json` entry** in the same
   change (the UI shows the 10 newest entries), which in turn requires a
   visual-baseline regen.
7. **Accessibility is expected**: aria-labels on div-grids (see `pulse.py`),
   `role="group"`, self-describing cell labels, focus ring token, reduced-motion
   support.

## 7. Recipe: adding a new section to the Briefing

1. Create `components/briefing/my_section.py` with a pure
   `render_my_section(report_slice) -> None` (or a `*_card_html(...) -> str`
   returning a string if it must join a lane band). Build HTML with existing
   classes/tokens; escape every report-sourced string.
2. Add any new CSS classes to `assets/theme.css` (before the trailing media
   queries), built entirely from `var(--…)` tokens.
3. Export it from `components/briefing/__init__.py` and call it from
   `_page_briefing()` in `dashboard.py` at the right position in the reading
   order.
4. Add a unit test (`tests/test_my_section.py`) covering rendering + escaping,
   update visual baselines, and append a `data/changelog.json` entry.
