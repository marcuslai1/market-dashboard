# Briefing Overhaul — Phase 0 Plan

Maps the current Briefing against `docs/design-spec.md`. Committed alone before
any code (per `docs/briefing-overhaul-prompt.md`). Nothing here is built yet.

**Guiding principle (owner steer, 2026-07-24):** "cut to ~7 blocks" is a
*guideline, not a target*. The goal is **clear showcasing and deliberate
information architecture**, not a block count. The current Briefing is bloated
because sections accreted as features shipped — it reads as a pile, not a
composition. We keep information that earns its place; we move (never delete)
what deserves room to breathe; we cut only true duplication.

---

## 1. Section mapping

Current Briefing render order (from `dashboard.py::_render_briefing_body`) and
its disposition. `keep` = stays on Briefing, `move` = relocates to a tab (content
preserved), `trim` = stays but sheds weight, `utility` = chrome, not a content
block.

| # | Current block | Component | Disposition | Reason |
|---|---|---|---|---|
| 1 | Stance / posture + signal-count ledger | `stance.stance_band_html` | **keep → §7 Posture header** | The 2-min glance opens on posture. Fold the distribution into a compact sub-fact; the full 6-cell ledger becomes a tighter strip, not a hero grid. |
| 2 | Data-coverage / paper / crisis banners | inline in `dashboard.py` | **keep (utility)** | Conditional trust caveats, rarely shown. Restyle to blueprint tone; keep behaviour. |
| 3 | Live-quote caption | `pills._render_live_caption` | **keep (utility)** | One-line freshness status above the tape. |
| 4 | Pulse tape (8 benchmarks) | `pulse.render_pulse` | **trim → §7 Metric tape (5)** | Spec §7 wants 5 decision-relevant benchmarks. Drop WTI, Gold, DXY (macro-context, not equity-book decisions); keep SPY, QQQ, VIX, US10Y, SOXX. *(judgment — see Conflicts)* |
| 5 | Overnight signal changes ribbon | `changes.render_changes` | **keep → §7 Signal-change chips** | Core "what changed" glance. Chip pass to match blueprint pills. |
| 6 | Cluster band | `clusters.render_clusters` | **move → Clusters tab** | Study block: per-cluster theses + anchor tables. No existing tab covers it. |
| 7 | Signal-calibration band | `calibration.render_calibration` | **move → Signal Tracker** | "How have signals performed" *is* the Tracker's subject; showcase it there beside the time-series. |
| 8 | Earnings scorecard | `earnings.render_earnings` | **move → Fundamentals tab** | Study block: EPS beat/miss trajectory. Pairs with Capex as a fundamentals cross-check. |
| 9 | Today's Trade (action card) | `action_card.render_action_card` | **keep → §7 Action/Trade card** | The one action — the dominant object of the Briefing. Add explicit entry/target/invalidation triplet (§7). |
| 10 | Macro Trigger Map (catalyst playbook) | `catalyst_playbook.render_catalyst_playbook` | **move → Scenario Log** | Study block: per-event bull/bear playbook. Belongs with scenarios/odds. |
| 11 | Contrarian candidates | `contrarians.render_contrarian_candidates` | **move → Watchlist** | Name-level actionable setups belong with the names page. Rare/conditional; flagged below. |
| 12 | AI Capex Pulse | `capex_pulse.render_capex_pulse` | **move → Fundamentals tab** | Spec §6 explicitly wants Capex as an *analytical page* (hero readout + 2×N grid). |
| 13 | Macro note (lede + odds bar + scenarios + FRED prints) | `macro.macro_card_html` | **trim → §7 Macro note** | Keep context + portfolio implication + next catalyst on Briefing. **Move scenario-odds bar + scenario narratives → Scenario Log.** FRED Core-5 prints → collapsed secondary. |
| 14 | Active risks | `macro.risks_card_html` | **trim → §7 Risk list** | Cap at 3 (currently 5), one line each. |
| 15 | Week-ahead calendar | `calendar.calendar_card_html` | **trim → §7 Compact calendar** | High-impact events only; forward-catalysts collapse. |
| 16 | Methodology footer | inline in `dashboard.py` | **keep (utility)** | Cross-link to Terminology. |

**Result:** Briefing = 7 content blocks (1, 4, 5, 9, 13, 14, 15) + 3 utility
elements (banners, live caption, footer). No block is a *duplicate* of an
existing tab, so "cut-as-duplicate" is N/A — everything moved is unique content
that gains a proper home.

### Target tab structure

Content moves off the Briefing into these homes (new tabs marked ★):

| Tab | Gains | Notes |
|---|---|---|
| **Briefing** | — (the 7 blocks) | 1.55fr / 1fr body |
| **Watchlist** | Contrarian candidates (section) | name-level setups |
| **Signal Tracker** | Signal calibration (section) | signal accuracy over time |
| **Clusters ★** | Cluster band | per-group theses + anchors |
| **Fundamentals ★** | Capex Pulse (hero) + Earnings scorecard | analytical page, §6 layout |
| **Scenario Log** | Macro Trigger Map + scenario odds/narratives | macro paths & probabilities |
| Retrospective / Pipeline Stats / Report Comparison / Terminology | unchanged | |

Two new tabs (Clusters, Fundamentals). The current cramped nav radio (already
overflowing — hence the short-label hack) is replaced by the spec §6 tab row
(2px accent underline), which has room and can scroll. *Alternative:* fold
Clusters into the Tracker to avoid a new tab — rejected for showcasing clarity,
but noted.

---

## 2. Component mapping (§7 inventory)

Spec §7 is the **whole-app** component library, not just the Briefing — that
resolves the apparent §1-vs-§7 mismatch (§1 lists 7 *Briefing* blocks; §7 lists
9 components, three of which live on tabs).

| §7 component | Current `render_*` | Status | Home |
|---|---|---|---|
| Posture header | `stance.stance_band_html` | **rebuild** | Briefing |
| Metric tape (5) | `pulse.render_pulse` | **rebuild + trim** | Briefing |
| Signal-change chips | `changes.render_changes` | **rebuild** | Briefing |
| Action / Trade card (entry/target/invalidation) | `action_card.render_action_card` | **rebuild** (→ string helper; add triplet) | Briefing |
| Shortlist rows (signal · vs-50D · R:R · trigger) | — | **create** | Watchlist / tab |
| Risk list (3) | `macro.risks_card_html` | **rebuild + cap** | Briefing |
| Compact calendar | `calendar.calendar_card_html` | **rebuild** | Briefing |
| Calibration bars (data palette) | `calibration._scorecard_table_html` | **rebuild** (table → bars, data palette) | Tracker |
| KPI readout cards (metric + verdict + note) | `capex_pulse._datasheet_html` (partial) | **rebuild** (→ §6 hero + KPI grid) | Fundamentals |

Deletions: none. Every current component is rebuilt or relocated. `lib/cards.py`
`card_container` is **rebuilt** into the blueprint primitive (transparent, square,
four corner marks) rather than deleted — every card in the app flows through it.

**Architectural note:** the `1.55fr/1fr` briefing grid must be emitted as a
single `st.markdown` string (CSS grid only sees siblings from one call — see
`DESIGN_HANDOFF §3.4`). So `action_card` and the pulse tape convert from
`render_* → *_html` string-returning helpers, and `_render_briefing_body`
composes left-column (Action, Macro) and right-column (Risks, Week-ahead) into
one `.briefing-grid` emission.

---

## 3. Spacing scale

Spec §5 asks for "hierarchy by hairlines + whitespace" but defines no steps.
Proposed **6-step, 4px-based** scale (new tokens in `:root`):

| Token | Value | Used for |
|---|---|---|
| `--space-1` | 4px | inline gaps, pill padding, dot-to-label |
| `--space-2` | 8px | label→value, tight metric stacks, chip rows |
| `--space-3` | 16px | intra-card element spacing, list-row rhythm |
| `--space-4` | 24px | card interior padding (blueprint inset) |
| `--space-5` | 40px | gap between Briefing blocks / grid gutter |
| `--space-6` | 64px | major section breaks, top-bar → body offset |

The existing density toggle (Relaxed/Compact) is preserved by swapping
`--space-4/5` down one step (24→16, 40→28) in the injected compact `:root`,
exactly as it swaps `--card-pad-*` today.

---

## 4. Responsive behaviour

Spec §6 fixes the body at `1.55fr / 1fr` and 1200px max-width but is silent on
narrow viewports. Proposed breakpoints (all authored **before** the trailing
media-query section of `theme.css`, per hard-constraint #2):

| Breakpoint | Behaviour |
|---|---|
| **≥ 1200px** | Container caps at 1200px, centred, `--space-6` (28px) side padding. Body = `1.55fr / 1fr`. |
| **900–1199px** | Container fluid to edges (28px pad). Body holds `1.55fr / 1fr`. |
| **< 900px** | Body collapses to a **single column**: Action → Macro → Risks → Week-ahead (lede stack first, then reference rail). Tab row becomes horizontally scrollable. |
| **< 640px** | Side padding 28→16px. Metric tape reflows 5→ wrap at 2–3 per row. Top bar wraps wordmark / toggle+date to two lines. |

Collapse order preserves the reading priority: the dominant lede (Action, Macro)
before the reference rail (Risks, Week-ahead).

---

## 5. Conflicts (spec vs. codebase) — stated, not silently resolved

Ordered by risk.

**C1 — Light/dark theme vs. dark-only Streamlit app (HIGHEST RISK).**
The app is dark-only; there is no `[data-theme]` and no runtime toggle. Streamlit
can't set an attribute on `<html>` from `st.markdown`. *Resolution:* reuse the
proven **density-override pattern** — base `:root` carries one theme; the toggle
(an `st` control in the top bar) writes `st.session_state.theme`, and
`dashboard.py` injects a later-cascade `<style>` var map for the other theme.
Signal *rails* are shared (spec §3a), so only pill-text/accent/brass/up-down/base
tokens swap. **Risk:** Streamlit's own widget chrome (selectbox, radio, toggle,
date_input, sidebar) is dark-tuned in `theme.css`; the light map must restyle
those too, or widgets look broken in light. This is the largest surface.
*Default theme:* **dark** (continuity with today's users); light is the toggle.
One-line flip if the owner prefers light-default.

**C2 — Two colour systems: the load-bearing rule is currently broken.**
Spec §3 forbids signal hues off signal pills/rails. Today: `action_card` paints
price deltas with `SIGNAL_COLORS["BUY"/"CAUTION"]`; `macro` scenario-odds bar
uses signal hues for base/optimistic/pessimistic/wildcard; `changes` arrows use
`SIGNAL_COLORS`; `stance` uses a signal hue as a decorative dot. *Resolution:*
add `--up/--down` (price deltas) and `--data-*` (brass/muted/stress) tokens per
spec §3b/§3c; sweep every non-signal use of a signal hue to the correct system.
Scenario odds move to Scenario Log and re-colour to the data palette. This is a
correctness sweep across ~6 files, not just new tokens.

**C3 — Fonts: Barlow Condensed/Barlow vs. Newsreader/Inter Tight/JetBrains Mono.**
*Resolution:* swap the Google-Fonts `@import` URL (line 6 of `theme.css`) to
`Barlow` + `Barlow Condensed`. **This is a CDN change, not a pip dependency** —
hard-constraint #1 ("no new dependencies") is satisfied. The three type roles
collapse: Barlow Condensed = headings + labels + **numbers** (with explicit
`font-variant-numeric: tabular-nums`, since it's not a mono), Barlow = body. The
`--serif/--sans/--mono` token *names* stay (dozens of selectors reference them)
but repoint to the Barlow families — so the sweep is one token block, not 40
selectors. Streamlit's Material Symbols icon font handling (theme.css ~L184)
must be preserved untouched.

**C4 — Blueprint cards vs. filled `.card`, broad blast radius.**
`card_container` renders a filled surface (bg, 4px radius, border). Spec §5 wants
transparent, square, single hairline, four `+` corner marks. *Resolution:*
rebuild `card_container` → `.blueprint` markup with four `<i class="corner">`.
Because *every* card flows through it, this changes all pages at once. Separately,
inline `background:var(--paper-2)` / `border-radius` in `contrarians`, `changes`
ribbon, `action_card` price rail, etc. must be swept to the blueprint idiom.

**C5 — Layout: 1200px + 1.55fr/1fr vs. 1280px + 12-col lane grid.**
`theme.css` sets `max-width:1280px` and a 12-col `.lane-wrapper` (lede/ledger/
strip). *Resolution:* max-width → 1200px; replace the lane grid with the briefing
`1.55fr/1fr` two-column grid. `.lane-wrapper` callers (stance, context band) move
to the new grid or to single-column stacks. Keeps the "one markdown string per
grid" rule.

**C6 — Metric tape 8→5: which five.** *Resolution (judgment):* SPY, QQQ, VIX,
US10Y, SOXX — the equity/rates/vol/semis a decision on this book turns on. WTI,
Gold, DXY are macro context, available on a tab. Owner can re-pick.

**C7 — Contrarians' home.** Moving to Watchlist is the tidy answer, but
contrarians is *rare and actionable* when it fires. *Resolution:* Watchlist
section, **plus** keep a one-line conditional pointer on the Briefing when it
fires so a live setup isn't buried. Flagged for owner.

**C8 — Test/baseline gates.** Every pixel baseline under `tests/visual/`
regenerates wholesale (expected). `tests/test_design_tokens.py` asserts CSS
mirrors `catalog.json` signal hues — **signal rails are unchanged** (spec §3a ==
catalog), so that test should hold; per-theme pill *text* colours are new and may
need the test extended. `tests/test_rendering_security.py` (escaping) must keep
passing — all rebuilt components keep routing report text through
`_escape_dollars`/`_escape_attr`. A `data/changelog.json` entry lands with the
user-visible change.

---

## 6. Phase sequence (unchanged from the brief)

1. **Phase 1 — Tokens.** `:root` + alternate-theme map; signal rails shared;
   pill-text/accent/brass/up-down per-theme. Fonts repointed. No component logic.
2. **Phase 2 — Layout skeleton + restructure.** 1200px shell, top bar (wordmark +
   tagline · theme toggle · date), tab row, `1.55fr/1fr` body. Move sections to
   their new tabs.
3. **Phase 3 — Components.** Rebuild the §7 inventory as blueprint, verdict-first
   string helpers.
4. **Verify.** Playwright at 1440/768 both themes → `docs/screenshots/`; run the
   §Verification checklist; regen baselines; changelog.

Verify after each phase; fix within the phase before moving on.
