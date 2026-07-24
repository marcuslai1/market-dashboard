# Briefing Page Overhaul — Task Brief

Rebuild the Market Report **Briefing** page against `Market Report — Design Spec`.
Read the spec in full before writing any code. It is authoritative on structure,
colour, typography, and voice.

Work autonomously. Do not wait for confirmation between phases.

---

## Phase 0 — Plan (commit alone, no code)

Write `docs/overhaul-plan.md` containing:

1. **Section mapping.** Table of every section currently on the Briefing page,
   each marked `keep` / `move-to-tab` / `cut-as-duplicate`, with a one-line
   reason. Target is the seven blocks in spec §1. Flag anything that doesn't
   fit cleanly rather than forcing it.

2. **Component mapping.** Table mapping existing `render_*` functions to the
   §7 component inventory: `exists` / `create` / `delete`.

3. **Spacing scale.** The spec calls for hierarchy by hairlines and whitespace
   but doesn't define the steps. Propose a 4–6 step scale and state where each
   step is used.

4. **Responsive behaviour.** The spec fixes the Briefing body at `1.55fr / 1fr`
   but says nothing about narrow viewports. Propose the collapse behaviour and
   the breakpoint.

5. **Conflicts.** Anything in the spec that contradicts the existing codebase —
   state the conflict, the resolution chosen, and why. Do not resolve silently.

Commit this file on its own before starting Phase 1.

---

## Phase 1 — Token layer (commit)

- Both theme maps as flat CSS variable sets: `:root` and `[data-theme="dark"]`.
- All values from spec §3 and §4. Signal rails shared across themes; pill text,
  accent, brass, and up/down have per-theme values.
- Theme toggle swaps the map only. No per-component theme logic.

## Phase 2 — Layout skeleton and section restructure (commit)

- 1200px max-width, centred, ~28px side padding.
- Persistent top bar: wordmark + tagline · theme toggle · date. Tab row below;
  active tab = 2px accent underline.
- Briefing body as a `1.55fr / 1fr` grid. Action card and macro note left;
  risks and week-ahead right.
- Move sections off the Briefing per the Phase 0 mapping. Content moves to
  tabs — it is not deleted.

## Phase 3 — Components (commit)

Build the §7 inventory. Each block takes data in and renders verdict-first,
mapping to a `render_*` string pattern.

---

## Non-negotiable rules

**Two colour systems never mix (spec §3).** This is the load-bearing rule.
- Signal hues appear only on signal pills and their owning rails.
- Price deltas use the dedicated up/down values, never BUY/CAUTION hues.
- Charts, capex bars, and health axes use the data palette only.

**No hard-coded colour.** Every value is a CSS variable from §3/§4.

**Blueprint cards stay line drawings.** Transparent fill, square corners,
single hairline border, four `+` corner marks. No filled surfaces, no
border-radius, no shadows.

**Headlines are conclusions, not labels (spec §2).** If a heading is a noun
phrase naming a category, it is wrong. "Digesting — spending is outrunning the
revenue it funds", not "Capex Data". The posture sub-line states a decision,
not a tally.

**All numerals use `tabular-nums`.**

**Preserve the tabs and their contents.** This overhaul moves weight off the
Briefing; it does not reduce what the report shows.

---

## Verification

After each commit, verify with Playwright. Screenshot the Briefing at 1440px
and 768px, both themes. Save to `docs/screenshots/`.

Check:

- [ ] No signal-palette hue appears outside a signal pill or rail
- [ ] No hard-coded hex in component code
- [ ] Blueprint cards render transparent with four corner marks
- [ ] Every section heading is a conclusion, not a category noun
- [ ] Two-column grid holds at 1440 and collapses sanely at 768
- [ ] Numerals are tabular across tables and the metric tape

Fix failures within the phase before moving on. Note anything you could not
verify programmatically — the headline check in particular needs your own
reading of the output, not a DOM assertion.
