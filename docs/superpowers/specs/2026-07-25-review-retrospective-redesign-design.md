# Review / Retrospective — page redesign

**Date:** 2026-07-25
**Surface:** `components/retrospective.py`, `assets/theme.css` (`.retro-*` block)
**Supersedes the layout of:** `docs/superpowers/specs/2026-07-20-reader-retrospective-design.md`
(that spec's *data* rules — dedupe, verdict classification, frozen windows,
retired-names-stay — are unchanged and still authoritative)

---

## 1. What the page is for

The page answers one question honestly: **did the calls work?** That makes it
uniquely vulnerable to two failure modes — looking like a highlight reel, or
being so raw that nobody can extract a verdict.

The current version fails the second way. It prints
`14 new calls · 9 resolved · 6 went our way` and leaves the reader to do the
division. The redesign computes the verdict and shows the arithmetic under it.

**Order: caveat → time control → verdict → evidence → method.** The honesty
banner comes first, before any number, so no figure is ever read unqualified.
This is deliberately the opposite of a marketing page — the limitation leads.

Single-column, scrolls. A study page like the Tracker, not a glance page.

## 2. Scope and isolation

Built on branch `review-redesign` in a git worktree, because a second agent is
concurrently redesigning the Signal Tracker **in the same working tree**.

**Page-scoped only. Files touched:**

| File | Change |
|---|---|
| `components/retrospective.py` | rebuilt render + HTML builders; new `paper_month_stats` |
| `assets/theme.css` | the `.retro-*` block (~2307–2351) replaced in place |
| `tests/test_retrospective.py` | updated for the new signatures + new units |
| `data/changelog.json` | one entry (append last; conflict-prone, see §9) |

**Deliberately NOT touched** — every one of these is shared with the Tracker:

- `lib/cards.py` (`render_section_head`) — the page grows its own `.retro-head`
  rather than mutating the head used by every section on the site.
- `lib/pills.py` (`_signal_pill_html`) — consumed unchanged.
- `components/paper_book.py` (`select_policy`) — consumed unchanged.
- `dashboard.py` — `_page_retrospective` already passes the three frames needed.
- CSS custom properties — no new tokens, no token edits. Only existing
  `--color-*`, `--up`, `--down`, `--brass`, `--stress`, `--eyebrow`, `--space-*`.
- `.blueprint > .corner` CSS — reused read-only for the scoreboard's corner marks.

## 3. Page head

`h1` 30px/600 + right-aligned uppercase descriptor at 10px muted, both over a
**2px solid `--color-text`** rule.

The 2px full-strength rule is the masthead weight — reusing it says "this is a
top-level document surface." The descriptor ("What we called, and what actually
happened — month by month") carries the page's premise so the title can stay
one word.

**Implementation note.** The design account describes this as "identical to the
Tracker's section heads", but today `.section-head` is an `h2` at 1.4rem over a
**1px** `--rule`, shared by nearly every section on the site. Upgrading it would
change every page, invalidate all ten visual baselines, and contend with the
Tracker terminal. So the Review page gets a page-scoped `.retro-head` at the
target treatment now, and **unifying `.section-head` to the 2px masthead weight
is an explicit follow-up** for after the Tracker work merges.

## 4. The honesty banner

A 1px `--color-divider` box with a **3px `--stress`** (terracotta) left rail, a
`⚠` glyph, and the single-regime caveat at 13px / 78%.

- **Terracotta, not signal-red.** This is a trust limitation — the statement
  that the verdicts below are provisional. It is not a rating on any stock.
  Terracotta is the data palette's stress color: it reads as a warning at a
  glance yet can never be confused with a CAUTION signal. Same decision as the
  thin-sample warnings on the Tracker. It is what lets a warning look like a
  warning without spending the signal palette.
- **A left rail, not a filled tinted box.** Filled alert boxes are the AI-slop
  convention and they break the system's "line drawings, never surfaces" rule.
  A hairline box + one colored edge is the marker grammar used by every other
  row on the site.
- **Above the month picker, not below the scoreboard.** If it followed the 67%
  hit rate the reader would already have formed a judgment. First position makes
  it a precondition for reading rather than a disclaimer appended after the fact.
- The `⚠` is its own grid cell (flex row, `align-items: flex-start`) so a
  wrapping sentence stays aligned to the text column instead of tucking under
  the glyph.

This replaces the page's current use of `.briefing-banner[data-tone="warn"]`,
which is a filled, rounded, `--caution`-railed box — i.e. all three things the
above rules out. The `briefing-banner` class itself is left alone for its other
consumers.

Text source is unchanged: `banner_text()` — the pipeline's own
`confidence_banner` verbatim when present, else the fixed single-regime caution.
Never empty.

## 5. Month picker

A "Month" label, three joined segments, then the in-progress caveat inline.

- **A segmented control, not a dropdown.** The archive is short (a handful of
  months) and comparison is the point — you click between June and July and
  watch the scoreboard change. A `<select>` hides the options and adds a click;
  segments make the whole time axis visible.
- **Joined** (`gap: 0`), so they read as one control with three states rather
  than three buttons. Each 1px bordered, uppercase 11px/600 — the same label
  grammar as the nav tabs.
- **Active** = steel border + 14% accent wash + full-strength text;
  **inactive** = divider border + muted text. Steel because selection is
  navigation/structure, never a rating. The 14% wash is the one fill on the
  page, justified because a segmented control must show which segment is *inside*
  the selection, and a border change alone reads weakly between adjacent
  segments. Three redundant cues (border, fill, weight) make it unmistakable.
- The **"still in progress" note** sits inline to the right at 10px muted
  uppercase, and is conditional on the selected month being the newest in the
  ledger. Beside the control it ties to the act of selecting July; as a caption
  below it would read as a page-wide statement.

**Implementation.** `st.radio(horizontal=True, key="retro_month")` styled via the
`.st-key-retro_month` scoping pattern that the masthead top-nav already proves
across Streamlit versions — **not** `st.segmented_control`, whose internal DOM
is a moving target across local 1.50 / CI 1.58 / cloud-latest. The label renders
as the control's own widget label, flexed onto the same row. The in-progress note
goes in a second `st.columns` cell with `vertical_alignment="bottom"`.

"In progress" stays **data-derived** (the latest month present in the ledger),
never wall-clock — the visual baselines freeze `TEST_DATE`.

## 6. The month scoreboard

One blueprint card (transparent, square, corner marks) split
`190px | 1fr | 250px` with hairline dividers between panels.

Three panels in one card rather than three cards: these are three views of the
same month — the verdict, its composition, and the portfolio consequence. A
single frame with internal hairlines says "one subject, three readings"; three
cards would imply three independent topics.

### Left — the verdict

- **Hit rate at 48px in brass** — the largest element on the page. This is the
  redesign's central move: a percentage is the answer to the page's question, so
  it gets the loudest treatment.
- **Brass, not green or red.** A hit rate measures the signals' calibration —
  the same role as the Tracker's hit-rate bars and α figure. Green would
  editorialize (is 67% good?) and would collide with the outcome greens a few
  hundred pixels below. Brass says "instrument reading" and stays neutral about
  whether the number flatters.
- Eyebrow reads `{month} · hit rate` in steel, so the big number is never
  ambiguous about what it measures or which month it belongs to — important
  because the month changes under the reader's click.
- `6 of 9 resolved calls went our way` at 12px / 62% beneath. The arithmetic is
  always shown, so the percentage is never a bare assertion — the same discipline
  as `right 3 of 5 · 5d` on the Tracker tiles. It also names the denominator
  (**resolved**, not all 14), the one thing a hit rate can quietly lie about.
- 1px right divider + 28px padding — enough to mark a boundary, not enough to
  fragment the card.

### Middle — the composition

- A **stacked bar across all calls**: worked (`--up`) / failed (`--down`) /
  open (neutral at 22%). 14px tall, hairline-bordered, segments proportional.
- **Why it exists.** The hit rate deliberately excludes open calls, so it cannot
  show that 5 of July's 14 calls are still unjudged. The bar shows the whole
  month including the unresolved slice, so the reader sees the 67% rests on a
  partial month. The two together are honest in a way either alone isn't.
- **Green/red is correct here.** These segments are outcomes — what the market
  did — which is the up/down delta system, not the signal palette. The neutral
  grey third segment matters: pending calls must look like *absence* of a
  verdict, and any color would imply one.
- Three counts below in `repeat(3, 1fr)` — New calls / Resolved / Still open —
  20px value over a 9px muted uppercase label. All neutral, no color: they're
  inputs, and coloring a count would imply 5 open calls is good or bad. Same
  value-over-label pattern as every stat block on the site, so it's learnable.

### Right — the paper-book consequence

- The month's **paper return at 26px in brass**, `vs SPY / SOXX` beneath, behind
  a 1px left divider.
- **Why it's on this page.** The hit rate says the calls were directionally
  right; the paper book says whether following them made money. July is the case
  that proves the point — a 67% hit rate alongside −0.3% — and putting them in
  one frame stops the reader from taking either as the whole story.
- Brass again, matching the Tracker's paper-book treatment, so the same quantity
  wears the same color on both pages. Smaller than the hit rate (26 vs 48)
  because this page's subject is the calls; the book is the cross-check.

### Data plumbing

`paper_month_line()` returns prose, but the panel needs numbers. Extract:

```
paper_month_stats(nav_df, block, month) -> dict | None
    {"month_name": "June", "nav_pct": +3.0, "spy_pct": +2.0, "soxx_pct": +2.5}
```

`None` when the month has no NAV rows or no NAV read — the benchmarks alone say
nothing about whether following the calls made money, so a missing NAV read
suppresses the whole panel rather than showing SPY on its own.

`paper_month_line()` — the prose one-liner the old layout printed — is **deleted**
rather than kept as a formatter over the new function. Nothing else consumes it
(only this page and its own tests), and keeping an unused prose builder alive just
to avoid editing three tests would be cruft. Its three baseline tests move to
`paper_month_stats` unchanged in substance.

Baseline rule is unchanged: last NAV at-or-before month start, or the first
in-month observation for the seed month; same `select_policy` lane as the Paper
Book band, so the two surfaces always describe the same headline lane.

Each panel carries a steel eyebrow (`{month} · hit rate` / `Composition` /
`Paper book`). The account specifies one only for the verdict panel; giving all
three the same label grammar is what keeps the 26px brass figure on the right
from being ambiguous about what it measures.

### Edge cases the design account doesn't cover

| Case | Render |
|---|---|
| 0 resolved calls (pending-only month) | hit rate `—`, sub-line "no calls resolved yet"; no divide-by-zero |
| No NAV rows / no NAV read for the month | paper panel value `—`, sub-line "no paper-book rows" |
| 0 calls in month | scoreboard omitted; the existing "No calls this month." line stands |
| Bar with 0 calls | not rendered (no zero-width segment arithmetic) |

## 7. The verdict groups

Three groups — What worked / What didn't / Too early to judge — each a colored
sub-head over a list of call rows. **Empty groups are omitted** (June and May
have no pending calls, so that group simply doesn't render), preserving current
behavior.

### Group heads

`h2` 19px with the count beside it in muted tabular.

- 19px not 30px, and over a **1px** `--color-text` rule rather than 2px —
  a deliberate step down from the page head, so the hierarchy reads
  month → outcome bucket, not three more top-level sections.
- The head is **tinted by outcome** (green / red / muted) — the only colored
  headings on the site. Justified because the three groups are otherwise
  structurally identical, so color lets you jump to the bucket you want without
  reading. It also pre-loads the rail color about to repeat down the rows.

### Call rows — `22px | 96px | 1fr | 66px`

Fixed icon, fixed pill column, flexible content, fixed date. With a fixed 96px
pill column every ticker starts at the same x down the whole list, so the names
form a scannable vertical edge — impossible if the pill sized to its label
(CAUTION vs BUY differ in width).

- **3px left rail = the outcome** (green / red / faint neutral). Same rail
  grammar as watchlist rows and clusters, so "colored left edge = state" means
  one thing everywhere on the site.
- **The ✓ / ✗ / ⏳ glyph in the outcome color.** Redundant with the rail on
  purpose: two encodings of the same fact, so the row survives a reader who
  can't distinguish the greens, and it gives the list a scannable left margin
  of marks.
- **The signal pill keeps the full signal treatment** — tinted bg, rail text,
  dot. This is the page where the two color systems sit side by side by design.
  A CAUTION call that worked renders as an **amber pill on a green rail**. That
  is the honest encoding: the rating was CAUTION, the outcome was good. Merge
  the palettes and the row becomes unreadable — you would have to pick one
  meaning for green. Every other color rule on the site exists so that this row
  can be unambiguous.
- **Content line:** ticker in 700 tabular, `@ entry` at 60%, then `— outcome` at
  78% in plain prose ("fell 12.4% — staying out was right", "stopped out
  (−7.4%)"). One sentence per call, in the source component's own language. The
  outcome is the darkest text after the ticker because it's what you came for.
- **Target/stop levels move to a muted second line** at 9.5px uppercase. Inline
  in parentheses they interrupted the outcome sentence mid-read; demoted below,
  the sentence flows and the levels are still there for anyone auditing the call.
- **Date** right-aligned at 10px / 48% — the quietest thing in the row, since
  within a month the exact day rarely changes a judgment. Right-aligned so dates
  form their own clean column at the far edge.
- `align-items: baseline` across the row so pill, ticker and date sit on the
  text baseline despite different sizes — the row reads as one line of type
  rather than three stacked objects.

Verdict text and bucketing come from `classify_call()` unchanged, so the
Retrospective and the Tracker scorecard can never disagree on a verdict.

## 8. Method note and footer

- Closing note at 12.5px / 60%, `max-width: 104ch`, with **exactly two phrases
  bolded** to full strength: **"raw price direction"** and **"retired names stay
  on the record."** Those are the two facts that change how every row above is
  read — the first because outcomes are absolute, not benchmark-relative (the
  alpha view is on the Tracker); the second because it is the anti-survivorship
  commitment that makes the page credible. Everything else in the paragraph can
  be skimmed. **Bolding by what breaks comprehension if missed, never by
  keyword.**
- Footer states the two rules the page embodies — "Signal pills keep the rating ·
  rails state the outcome" and "Verdicts frozen to each call's own window" — at
  10px uppercase muted. It is the page's own legend, placed where someone
  confused by an amber-pill-on-green-rail row would go looking.

## 9. Color assignment for the whole page

| Role | Color | Where |
|---|---|---|
| Signal rating | signal palette | the pill on every call row |
| Outcome / market direction | `--up` / `--down` | row rails, ✓ ✗ glyphs, group heads, the stacked bar |
| Measurement | `--brass` | hit rate, paper-book month return |
| Trust limitation | `--stress` | the honesty banner |
| Structure / selection | steel (`--eyebrow` / `--accent`) | eyebrows, active month segment |
| Pending / no verdict | neutral 22–50% | the ⏳ rail, the bar's third segment, the pending group head |
| Metadata | neutral 45–62% | entry prices, levels, dates, counts |

Outcome color is applied as `var(--up)` / `var(--down)` in CSS, not the
fixed-hex `STATUS_POS` / `STATUS_NEG` constants the old inline styles used —
the account names these the delta system, and the tokens are theme-aware where
the hexes are not. (`test_no_raw_hex_literals_in_components` keeps hexes out of
components either way.)

**The distinguishing feature of this page** is that signal color and outcome
color appear on the same row, three inches apart, and mean different things.
That only works because the rule has been held everywhere else — and it is the
strongest argument for keeping it.

## 10. Testing

Existing `tests/test_retrospective.py` units for `dedupe_calls`,
`classify_call`, `month_label`, `build_month_digest` and `banner_text` stay
as-is and must stay green — the data layer is unchanged.

Updated / new:

- `paper_month_stats` — pre-month baseline, seed-month baseline, `None` when the
  month has no rows, `None` when the NAV column is unusable, and NAV preserved
  when only a benchmark is missing.
- `hit_rate` — divides by resolved not by all calls; `None` when nothing resolved.
- `month_label_short` — the segment label.
- `call_item_html` — keeps `data-bucket`, entity dollars, no raw `$`, levels
  present for longs / absent for CAUTION; now asserts levels render on the
  second line, not inside the outcome sentence.
- `month_scoreboard_html` — hit-rate percentage and its arithmetic line, the
  three counts, bar segment proportions, the `—` fallbacks from §6.
- `digest_html` — scoreboard + groups, empty groups omitted.
- AppTest page test — `at.radio(key="retro_month")` replaces
  `at.selectbox(...)`; still asserts banner-above-everything, default month is
  latest, and switching to June surfaces the resolved AMD call.
- Visual baseline `retrospective.png` regenerates. Docker regen contends with
  the Tracker terminal — run it once, at the end, and only for this page.
- `data/changelog.json` gets one entry, appended **last**, since both terminals
  will be prepending to the same array this session.
