# Market Report — Design Spec

Handoff for rebuilding the redesigned dashboard in code. Written to drop straight into the repo.

---

## 1. Core principle — glance vs. study

Every screen commits to one job.

- **Briefing = a 2-minute glance.** Posture → what changed → one action. Nothing that needs studying.
- Anything you'd *study* (Capex Pulse, Clusters, Scenarios, calibration history) lives on **its own tab**.
- When a block duplicates a tab, **cut it, don't shrink it**.
- Target density: **~7 blocks on the Briefing**, not 19.

Briefing block list (in order):
1. Posture headline (verdict + one distribution fact folded into the sub-line)
2. Metric tape (5 benchmarks)
3. Overnight signal changes (chips)
4. Today's Trade (the one action — dominant object)
5. Macro note (merged: context + portfolio implication + next catalyst)
6. Active risks (3, one line each)
7. Week ahead (compact calendar, high-impact only)

Everything else → tabs.

---

## 2. Voice — verdict first

Every block leads with the plain-English "so what," then numbers justify it.

- Headlines are **conclusions**, not labels. ✅ "Digesting — spending is outrunning the revenue it funds." ❌ "Capex Data."
- Posture sub-line states a decision, not a tally. ✅ "Net exposure — trim." ❌ "0 buy / 3 watch / 2 caution."
- This is the single most important non-visual rule.

---

## 3. Two color systems — NEVER mixed

The load-bearing rule of the whole design.

### a. Signal palette — reserved exclusively for signals
Only ever used for BUY / ACCUMULATE / WATCH / HOLD / CAUTION / AVOID. Nothing else on any screen may use these hues.

| Signal | Rail (light) | Pill bg (light) | Pill text (light) | Rail (dark) | Pill text (dark) |
| --- | --- | --- | --- | --- | --- |
| BUY | `#22c55e` | `rgba(34,197,94,0.15)` | `#15803d` | `#22c55e` | `#4ade80` |
| ACCUMULATE | `#3498db` | `rgba(52,152,219,0.16)` | `#1f6ea8` | `#3498db` | `#5dade2` |
| WATCH | `#f59e0b` | `rgba(245,158,11,0.16)` | `#8a5a00` | `#f59e0b` | `#f5b942` |
| HOLD | `#6b7280` | `rgba(107,114,128,0.16)` | `#4b5563` | `#6b7280` | `#9ca3af` |
| CAUTION | `#ef4444` | `rgba(239,68,68,0.14)` | `#b91c1c` | `#ef4444` | `#f87171` |
| AVOID | `#b91c1c` | `rgba(185,28,28,0.16)` | `#991b1b` | `#b91c1c` | `#e0a3a3` |

Rails are shared across themes; only the pill *text* lightens in dark so it stays legible on a dark tint.

### b. Data palette — charts, health axes, capex bars
Kept off the signal palette so a data bar is never misread as a signal. (Same rule as `lib/charts.py`.)

| Role | Light | Dark |
| --- | --- | --- |
| Brass (primary series) | `#7a5f2b` | `#d8b878` |
| Brass fill | `#c9a66b` | `#c9a66b` |
| Muted fill (secondary series) | `#b7b7ba` | `#5d5d60` |
| Stress (terracotta) | `#a3453b` | `#e08a80` |

Health axis reads steel → brass → terracotta = Healthy → Watch → Stress.

### c. Structure & deltas
Distinct from both systems above.

| Role | Light | Dark |
| --- | --- | --- |
| Accent (eyebrows, links, focus, tab underline) | `#5980a6` | `#94bce3` |
| Eyebrow text | `#416180` | `#9ec7ef` |
| Up (price delta) | `#1a7f4b` | `#4ade80` |
| Down (price delta) | `#c0392b` | `#f87171` |

Up/down deltas are their own green/red — do not reuse the BUY/CAUTION signal hues for price moves.

---

## 4. Base tokens (both themes)

| Token | Light | Dark |
| --- | --- | --- |
| `--color-bg` | `#f2f2f3` | `#17181b` |
| `--color-surface` | `#e9e9ea` | `#202126` |
| `--color-text` | `#1d1f20` | `#e9e8e2` |
| `--color-divider` | `#1d1f20` @16% | `#ffffff` @13% |

Everything is a CSS variable, swapped as one set for light/dark (`:root` + `[data-theme="dark"]`). Nothing hard-coded.

---

## 5. Visual grammar (Industry design system)

- **Blueprint cards** — square corners, single hairline border, `+` registration marks at all four corners, **transparent fill**. Line drawings, never filled/rounded surfaces. This is the aesthetic; don't soften it. (`.blueprint` + four `<i class="corner tl/tr/bl/br">`.)
- **Type** — Barlow Condensed for all headings/labels/numbers; Barlow for body.
  - Labels: uppercase, letter-spacing `0.08–0.16em`, 9.5–11px.
  - Headlines: 24–36px, weight 600, letter-spacing `-0.015em`.
  - Body: 13–15px, line-height ~1.55.
- **Numbers** — always `font-variant-numeric: tabular-nums`.
- **Signals render as pills** — tinted bg + rail text, with a matching **3px left border** on the owning row/card.
- **Hierarchy by hairlines + whitespace**, not boxes or shadows. Dividers 1px @~15% text opacity; section tops a heavier 1–2px full-text rule.

---

## 6. Layout skeleton

- Fixed max-width **1200px**, centered, ~28px side padding.
- Persistent top bar: wordmark + tagline · theme toggle · date. Below it, a row of section tabs; active tab = 2px accent underline, inactive = muted text.
- **Briefing body: a `1.55fr / 1fr` two-column grid.** Dominant lede left (Action card, Macro note); reference rail right (Risks, Week ahead).
- Analytical pages (Capex): hero readout (big number + comparison bars) then a 2×N card grid.

---

## 7. Component inventory

Each is a self-contained block: takes data in, renders verdict-first. Maps cleanly to a `render_*` string pattern.

- Posture header
- Metric tape (trimmed to 5 decision-relevant benchmarks)
- Signal-change chips
- Action / Trade card (with entry / target / invalidation triplet)
- Shortlist rows (actionable names only; signal · vs-50D · R:R · trigger)
- Risk list (3 max, one line each)
- Compact calendar (date · event · impact tag)
- Calibration bars (data palette)
- KPI readout cards (metric + verdict word + note)

---

## 8. Theming mechanics

Store both themes as flat token maps; apply the active one to `:root`. Signal rails are shared; pill text, accent, brass, and up/down all have per-theme values (above). Toggle just swaps the map — no per-component theme logic.
