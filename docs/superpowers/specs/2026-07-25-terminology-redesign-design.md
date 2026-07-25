# Terminology & Method — redesign

**Date:** 2026-07-25
**Surface:** `components/terminology.py` (page), `assets/theme.css` (grammar)
**Status:** design approved, ready to plan

---

## 1. The premise

**A reference page is arrived at, not read.** Nobody scrolls 6,000 words to learn
something. They land here from a row on the Watchlist thinking *"what does
wide-stop R:R mean?"*, want the answer in ten seconds, and leave.

The current page is built for the opposite reader — someone reading top to
bottom, in order, once. That is why it has no index, no search, and eleven
sections of undifferentiated prose. Every decision below follows from inverting
that assumption.

Three problems, three answers:

| Problem | Answer |
| --- | --- |
| You can't find anything | A sticky index rail and a search box |
| Everything weighs the same | Three visual layers per entry |
| Definition and history are interleaved | Separate them; history gets a dated door |

Nothing is deleted. The page's whole claim on the reader is that it is auditable,
so every existing sentence survives — it is *re-shelved*, not cut.

---

## 2. Architecture

Split the page in two, because a 600-line module that is 95% copy is a module
where the layout is unreadable:

| Module | Owns |
| --- | --- |
| `components/terminology_content.py` | `SECTIONS` — the 12 section definitions (id, title, descriptor, keywords, layers). Pure data + copy, no Streamlit. |
| `components/terminology.py` | Rendering: index rail, search, section HTML, page assembly. No copy. |

**One array drives both the index and the body.** The index is generated from
`SECTIONS`, so a section can never exist without a nav entry or vice versa. This
is the single rule that keeps a twelve-section reference page honest over time.

### Section record

```python
{
  "id": "rr",                       # stable anchor target, kebab-case
  "title": "Risk : Reward",
  "descriptor": "The single most-cited number on this site",
  "kw": "rr r:r risk reward ratio headline wide stop ...",   # search index
  "answer": "<plain-language answer, 1–2 sentences>",
  "body": "<layer-2 HTML: plates, grids, bands>",
  "drawers": [("Caveat · distant-target inflation", "<html>"), ...],
  "history": [("2026-07-18", "distorted ratios", "<html>"), ...],
}
```

`drawers` and `history` render as the same door object; `history` summaries are
prefixed `Method history ·` and carry their date, so a reader can tell whether
it is relevant without opening it.

---

## 3. Layout

A `220px | 1fr` grid, `align-items: start`, gap 40px. Left column
`position: sticky; top: 20px`.

**Why sticky and not a top nav bar:** the sections have long names ("Entry Block
& Catalyst Context") and there are twelve. Horizontally they wrap into an
unreadable block; vertically they are a clean list that stays put through a long
scroll, so you always know both where you are and what else exists.

Index items: 10px uppercase Barlow Condensed in `--eyebrow`, a 2px
`--color-divider` left tick, `padding: 7px 0 7px 12px`. Same label grammar as
every other kicker on the site — navigation chrome, never content. Steel because
moving around a page is structural. `border-bottom: 1px solid var(--color-text)`
under "On this page": the strong rule opens the list the way it opens a data zone
elsewhere; one consistent meaning for that weight.

Plain `<a href="#id">` anchors — native, works with browser back, no scroll
hijack.

**Below 900px** the grid collapses to one column and the rail un-sticks, landing
above the content as a jump list. The rail is an accelerator, not a requirement.

---

## 4. Streamlit adaptations (deltas from the pure-HTML design)

Three constraints of this host change the implementation, not the intent. They
are recorded here because the obvious reading of the design would be wrong:

1. **No JavaScript.** `st.markdown(unsafe_allow_html=True)` strips `<script>`.
   The live keystroke filter becomes **`st.text_input` + a server-side Python
   filter** — Streamlit reruns on Enter/blur, so the placeholder says
   `Search terms — press Enter`. Filtering is still section-level and still
   decisive (non-matching sections stop rendering).
2. **The body is one `st.markdown` blob**, not `st.columns`. Nested Streamlit
   columns bring their own flex wrappers, which is exactly what crushed the
   Review rows into a 140px ribbon. One blob means the grid is ours.
3. **Doors are raw `<details>`**, as on the Watchlist drill-down — `st.expander`
   cannot live inside markdown-injected HTML. They take the site's existing door
   grammar (`.dd-drawer`) to the letter: transparent, 1px hairline, square, ~38px
   tall, 10.5px steel uppercase summary, an 8px caret that rotates rather than
   swapping glyphs.

**Verify at build time:** that `id` attributes survive Streamlit's HTML
sanitizer, and that `position: sticky` is not defeated by an `overflow` on a
Streamlit ancestor. Both are checked in the live DOM with Playwright — selectors
verified, never guessed (the `data-testid="stExpander"` lesson). If sticky fails,
the rail degrades to a static jump list and the page still works.

---

## 5. The three layers

The heart of the redesign. Every entry has three layers and they must *look*
different.

**Layer 1 — the plain answer.** 18px Barlow Condensed, regular weight, ~66ch,
immediately under the section head. One or two sentences, no jargon, no formula.

> Upside to the nearest resistance, divided by downside to the invalidation. An
> R:R of 2.4 offers 2.4 units of reward for every 1 at risk.

The heading font at body length reads as a *standfirst* — visibly larger and
airier than ordinary prose, which marks it as the answer rather than the first of
many paragraphs. Ninety percent of readers can stop here and the design should
let them.

**Layer 2 — the precise rule.** Formula plates, term grids, bands. Full-strength
text, 13–13.5px, structured as grid rows on hairlines, not paragraphs.

**Layer 3 — the audit trail.** Caveats, edge cases, method history — behind
doors with 10.5px steel uppercase summaries.

**The sorting test:** *does a first-time reader need this to understand the
term?* If no, it is layer 3. Distant-target inflation, the AND rationale in the
earnings archetype, the 2026-05-30 removal of the catalyst path — all real, all
layer 3.

---

## 6. Separating definition from history

The `(since 2026-07-18)` and `(since 2026-05-30)` notes currently sit inline as
ordinary paragraphs among the definitions, so someone learning what an entry
block *is* has to read about a rendering bug fixed last week.

**Rule:** history goes in a dated door, labelled as history —
`Method history · distorted ratios · 2026-07-18`.

Not deleted, because they are the audit trail and this page exists for readers
who want to audit. Not inline, because they answer a different question
("what changed?") from the one the page is for ("what does this mean?"). Same
content, correct shelf.

---

## 7. Prose that becomes a visual

Most of this page is genuinely prose and stays prose. Two passages are not:

**The three-tier wait gradient** — currently four sentences explaining that
HOLD / CAUTION / AVOID differ by time horizon. That is a timeline. Becomes three
rows of signal name + horizon word + a bar widening 20% → 55% → 100% in the
signal colour. Legitimate signal-palette use: these *are* signals.

**R:R quality bands** — currently a two-column table of equals. Each band gets a
3px left rail (green / brass / terracotta) so favourable, mixed and unfavourable
are distinguishable before reading. The middle band is **brass, not amber**:
amber is WATCH, and "mixed geometry" is a measurement reading, not a rating.

**How to spot these:** prose describing a *sequence, a scale, or a comparison*
becomes a visual. Prose describing reasoning or caveats stays prose.

---

## 8. Formula plates

1px `--color-divider` box, 2px `--accent` left rail, **transparent fill**,
monospace 12.5px, `white-space: pre-wrap`, `overflow-x: auto`.

Transparent, not `--paper-3`. The current plates are filled; filled surfaces
break the line-drawing rule. A hairline box plus one steel edge does the same
containment job in the system's own grammar.

Monospace is the one justified font exception on the site — formulas need
character alignment, and a proportional font makes the operators wander.
`overflow-x: auto` so a long line scrolls rather than reflowing and destroying
that alignment.

Variable names in brass where they are defined below (`entry`,
`nearest_resistance`). Brass is the data axis; a variable name is a data
reference, so it cannot be confused with a signal or a link.

---

## 9. Type scale

Three steps only, site-wide:

| Step | Size / rule | Use |
| --- | --- | --- |
| Page | 30px / 2px rule | the page masthead |
| Section | 21px / 1px rule | the twelve section heads |
| Label | 10px eyebrow | index items, door summaries, plate labels |

On a twelve-section page this is load-bearing: if sections wore the page weight
the scroll would read as twelve separate documents. Section heads keep the
right-aligned descriptor so the heading itself can stay two words.

---

## 10. Entry rows

Every list on this page — signals, technicals, valuation, verdicts, lanes, R:R
terms — is a grid with a **fixed label column** (124 / 132 / 172px by content)
and a **`1fr` content column**, rows separated by hairlines.

Fixed label column so every definition starts at the same x and the page has a
vertical reading edge you can scan by label alone. `align-items: start`, never
`center` — a two-line definition beside a one-word label top-aligns rather than
floating. Content capped at 74–78ch via `max-width` on the *text*, not by
narrowing the grid: measure control without wasting the column.

`1fr` on the content column is not decoration. A content column with no flexible
track collapses to its minimum — the same bug that crushed the Review rows.

---

## 11. Colour

Almost none, deliberately — this is a document, not an instrument panel.

| Role | Colour | Where |
| --- | --- | --- |
| Signal rating | signal palette | the six signal pills, the wait-gradient bars |
| Measurement / data reference | brass | formula variables, technical band chips, R:R mixed band |
| Trust limitation | terracotta | Limitations rails, the single-regime caveat |
| Structure / navigation | steel | index rail, section eyebrows, door summaries, plate rails |
| Everything else | `--color-text-2/3` | all definition prose |

**The test:** squint, and the page should be near-monochrome with a few coloured
pills. Colour marks *category*, never *emphasis* — emphasis comes from size and
weight. A reference page that uses colour for emphasis becomes unreadable at
length.

Consequence for the code: the page stops carrying raw hex literals and moves onto
the `--buy` / `--accumulate` / … tokens like every other component. See §13.

---

## 12. Bolding discipline

Inside layer-3 prose, bold **only the phrase that names the concept** — the
lead-in (`Closed-only.`, `Decay half-life, 90 days.`, `What this is not.`).

These paragraphs are scanned, not read. A bolded lead-in makes the paragraph
self-indexing: skim eight bold phrases, read the one that matters. Bolding
mid-sentence keywords as well destroys that, because the lead-ins stop standing
out.

The one exception is a phrase whose omission causes a *misreading* — "raw price
direction", "one corrected number", "both stretched and momentum-crowded". Bold
by what breaks comprehension if missed, never by what seems important.

---

## 13. Section inventory

Twelve sections, each with a stable id. "→ door" marks content moving to layer 3.

| # | id | Title | Notable re-shelving |
| --- | --- | --- | --- |
| 1 | `signals` | The Six Signals | wait gradient → timeline visual; "states not a ladder" and "writeup depth" → doors |
| 2 | `rr` | Risk : Reward | bands → railed bands; distant-target inflation → door; distorted ratios (2026-07-18) → history door |
| 3 | `technicals` | Technical Indicators | band cutoffs → brass chips in a label/def/bands grid |
| 4 | `valuation` | Valuation Metrics | straight label/definition grid |
| 5 | `earnings` | Earnings Setup | archetype grid keeps signal pills; the AND rationale and "what this is not" → doors; "binary event" ban → door |
| 6 | `episodes` | Signal Episodes & Verdicts | episode formula → plate; verdict table → grid; default filter + post-cutover caveat → doors |
| 7 | `calibration` | Aggregate Calibration | win-rate formulas → plate; closed-only/per-signal/HOLD → grid; decay + shrinkage → doors |
| 8 | `paper-book` | Paper Book | NAV formula → plate; buy/sell rules → grid; lanes → grid; single-regime caveat → terracotta rail |
| 9 | `macro` | Macro Scenarios & Odds | three bullets → grid |
| 10 | `entry-block` | Entry Block & Catalyst Context | plain-language blocks (2026-07-18) and wait-state phrasing (2026-07-18) → history doors; catalyst-path removal (2026-05-30) → history door |
| 11 | `pulse` | Pulse Strip | benchmark definitions → grid; VIX inversion stays in the answer |
| 12 | `limitations` | Limitations | five items on terracotta rails |

---

## 14. Testing

**Unit (`tests/test_app_pages.py`):**
- Index/section parity — every `SECTIONS` id appears once as an anchor target and once as an index href; ids are unique.
- Every section has a non-empty `answer` and `kw`.
- Search filters: a query matching one section renders that section and drops the others; the status line reports `N of 12`.
- An empty/no-match query renders the "no section matches" state, not a blank page.
- The existing decay-half-life / shrinkage assertion still passes (content preserved).
- Every `history` entry carries an ISO date in its summary.

**Tokens (`tests/test_design_tokens.py`):** the page joins the site's no-raw-hex
rule. Drop the `terminology.py` exemption from
`test_no_raw_hex_literals_in_components`, and replace
`test_terminology_hex_literals_match_sanctioned_palette` with a check that the
signal pills reference the canonical `--buy` / `--accumulate` / … tokens. This
tightens the rule; it does not relax it.

**Visual:** `terminology` is in `tests/visual/test_pages.py` PAGES, so its
baseline is regenerated through the Docker harness (PowerShell, not Git Bash).

**Changelog:** a `data/changelog.json` entry lands the same session; the strip
shows the 10 newest, so the pages carrying it need their baselines regenerated
too.

---

## 15. Out of scope

- Rewriting the *substance* of any definition. Copy is re-shelved and given a
  plain-language lead; the methodology it describes does not change.
- Any change to the pipeline, to other pages, or to the site's shared devices
  beyond reusing them.
- Search across other pages. Nothing else on the site needs it; this page does.
