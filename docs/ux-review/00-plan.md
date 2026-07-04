# Overnight UX & "Does-It-Make-Sense" Review — Plan

> Autonomous session started 2026-07-04. Scope agreed with the user before they
> went to sleep. This doc is the design/approach; **BACKLOG.md** is the ranked
> findings; **PROGRESS.md** is the live checkpoint a resumed session reads first.

## Goal
The dashboard is a **presentation layer** over upstream daily *reports* (`data/morning_report_*.json`).
It does not compute signals — it renders them. So this review does **not** invent new
financial signals. It judges two things, page by page, band by band:

1. **UX quality** — clarity, hierarchy, decisiveness (lead with the verdict),
   readability, responsive behaviour, accessibility, dark/light consistency.
2. **Does what it displays make sense?** — is the presentation *faithful* to the
   report, *internally consistent* (no contradictory figures), and *decision-useful*
   (does every element earn its place, per the user's own bar)?

## Method
Run the real app (Streamlit @ localhost:8501) and *look* at it:
- For every page + major band: screenshot at **desktop (1440w)** and **narrow (~400w)**.
- Read the rendering code alongside the screenshot to explain *why* something looks
  the way it does and whether it can misrepresent the underlying report.
- Log a ranked finding with a concrete proposed fix.

## The safety bar (what I may auto-implement while unattended)
Design choices here are deliberate (see the user's memory). So:
- ✅ **Auto-fix on its own branch** only if the fix is *objectively correct*:
  genuine display bug, contradictory/incorrect figure, text overflow / broken
  responsive layout, accessibility violation, mislabeled or stale-without-framing
  data, a clear inconsistency that is **not** documented as intentional.
- 🧑‍⚖️ **Leave as a proposal** anything subjective: restyling, layout opinions,
  new visual treatments, information-hierarchy changes. These go in BACKLOG.md for
  the user to judge — I do not touch them.
- Before "fixing" anything that looks odd, I grep for a rationale comment. If the
  oddity is intentional and documented, it is **not** a bug — I note the rationale.

## Guardrails (hard)
- Never commit to `main`. Docs/screenshots live on `ux-review/overnight-2026-07-04`;
  each code fix gets its own `ux-fix/<slug>` branch off `main`.
- Never push to any remote. Never delete files. No paid/external calls.
- Everything is reversible: branches + new docs only.

## Deliverables (what the user wakes to)
1. **BACKLOG.md** — ranked findings, each with evidence (screenshot), severity,
   effort, safe-to-auto-fix flag, and a proposed fix.
2. **screens/** — annotated before/after screenshots.
3. A few **`ux-fix/*` branches** — objectively-correct fixes, ready to review/merge.
4. A **visual Artifact** capstone summarising the top findings (built near the end).

## Pages (7)
briefing (default, multi-band) · watchlist (+ drilldown) · signal-tracker ·
pipeline-stats · scenario-log · report-comparison · terminology
