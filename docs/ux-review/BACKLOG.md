# UX & Display Review — Ranked Backlog

> Living doc. Findings from the overnight review of the dashboard as a *presentation
> layer*. Ranked by severity × decision-impact. See `00-plan.md` for scope/method.

## How to read a finding
Each finding: **[ID] Title** — severity · effort · fix-safety · page/band
- **Severity:** `P0` broken/wrong · `P1` misleading or decision-harmful · `P2` clarity/polish that helps · `P3` subjective nit
- **Effort:** S (<30m) · M · L
- **Fix-safety:** ✅ objectively-correct (I may auto-fix on a branch) · 🧑‍⚖️ needs your judgment (proposal only)
- Body: what I saw (with screenshot), why it matters for a decision, proposed fix, and status.

---

## ★ Top findings (ranked) — filled during capstone
_(to be populated as the review progresses)_

---

## Findings by page

### Briefing

**[BR-1] Active-risks: a plain-sentence risk loses its severity badge and shows a mid-word–truncated fragment** — `P1` · S · ✅ auto-fix · Briefing → Active Risks
- **Saw:** the 3rd risk renders its tag as **"US‑China tech tensions p"** (see `screens/briefing-desktop-1440.png`) where every other row shows a `LOW` severity chip — and it's cut off mid-word.
- **Cause:** `components/briefing/macro.py:280` — `tag = text.split(":", 1)[0][:24] if ":" in text else sev`. The risk text *"US‑China tech tensions persist: Pentagon…"* is an ordinary sentence that happens to contain a colon, so the heuristic mistakes the 30-char first clause for a `Category:` tag and hard-truncates it to 24 chars. Only 1 of 4 risks today has an inline colon, so it's the lone broken-looking row.
- **Why it matters:** reads as a rendering bug, and the row silently loses its severity signal (should read `LOW`).
- **Fix:** only use the pre-colon text as a tag when it's genuinely tag-like (short — e.g. ≤ ~16 chars / ≤ 2 words, no trailing truncation); otherwise fall back to the severity badge.

**[BR-2] R:R is displayed as the very value the data flags as *distorted*** — `P1` · M · logic ✅ / treatment 🧑‍⚖️ · Action card + Watchlist row + Drilldown
- **Saw:** the "If you only do one thing today" card headlines **"R:R 46.5:1"** for NVDA while its own body says that ratio is *"distorted by a tight 0.2% stop … the sizing R:R … is 4.4:1."* The Watchlist R:R column and the drilldown show the same 46.5:1.
- **Cause:** the report's `risk_reward` object already carries `rr_distorted: true`, `tight_invalidation: true`, and a corrected `sizing_rr.ratio_label = "4.4:1"` — but **no component reads them.** `action_card.py:66`, `drilldown.py:298`, and `row.py:43/58` all use the raw `ratio_label`/`ratio`. The action card even *ranks* the "one thing" candidate by that raw ratio (`action_card.py:45`), so a tiny-stop 46.5:1 can win the slot.
- **Also (drilldown):** the drilldown *has* a dedicated "Wide-stop R:R" row (`drilldown.py:320`) built to contextualize a distorted headline — but it reads only the older `wide_stop_rr` key. `wide_stop_rr` and the newer `sizing_rr` coexist per-ticker across reports; NVDA today carries `sizing_rr` (4.4) and no `wide_stop_rr`, so the row shows **"—"** and the distorted 46.5:1 stands alone. `sizing_rr` is surfaced **nowhere** in the UI.
- **Why it matters:** the sharpest does-it-make-sense issue found. A headline stat overstates reward:risk ~10× vs the value the report itself says is real — on the single most prominent call of the day. 3 of 29 names carry `tight_invalidation` today, so it recurs.
- **Fix:** a shared helper that prefers `sizing_rr.ratio_label` when `rr_distorted` (with a subtle "tight-stop" marker), used by all three sites; rank action candidates by the corrected ratio. Exact visual treatment is yours to tune.

**[BR-3] Deep-linking to the default page `/briefing` shows a "Page not found" dialog and falls back to `/`** — `P2` · S–M · ✅ auto-fix · routing
- **Saw:** a hard load of `localhost:8501/briefing` (cold *and* warm) pops Streamlit's **"Page not found — Running the app's main page"** dialog and rewrites the URL to `/` (see `screens/briefing-desktop-1440.png`; console logs a `/briefing/_stcore/health` 404). `/watchlist`, `/signal-tracker`, … all deep-link cleanly.
- **Cause:** Briefing is the `default=True` page, which Streamlit serves canonically at `/`; also giving it `url_path="briefing"` (`dashboard.py:344`) creates a path the router won't accept as an entry point. In-app nav uses `st.radio` + `st.switch_page` (`masthead.py`), so clicking around is unaffected — only external/bookmarked/guessed `/briefing` links break.
- **Why it matters:** the module docstring sells "real URL per page so deep links work"; 6 of 7 pages honor it, the flagship page doesn't — and a shared `/briefing` link greets a colleague with an error dialog.
- **Fix:** drop `url_path="briefing"` on the default (accept `/` as its canonical URL), or otherwise make `/briefing` resolve; leave nav numerals/labels unchanged.

**[BR-4] The posture verdict is marked up as a single ~60-word `<h2>`** — `P3` · S · 🧑‍⚖️ proposal · Stance band
- **Saw:** the entire "7 of 29 names are hard-blocked … cluster resets." verdict is one `heading level=2`, producing a sentence-length heading anchor (`#7-of-29-names-are-hard-blocked-…`).
- **Why it matters:** leading with the verdict is great and deliberate — but as an `<h2>` it bloats the screen-reader headings outline and the anchor id. Consider a styled `<p>` for the big verdict plus a short real heading (e.g. "Today's posture") for the outline. Purely semantic; visual unchanged.

**[BR-5] Narrative counts don't tie to the computed distribution** — `P3` · — · 🧑‍⚖️ upstream · Stance
- **Saw:** the verdict says "7 … hard-blocked … another 15 are in CAUTION," directly above a Signal Distribution reading WATCH 3 / HOLD 2 / **CAUTION 24** (7+15 ≠ the grid).
- **Note:** the verdict text is authored upstream (report narrative); the grid is computed. The dashboard juxtaposes them, so the mismatch is visible even though its root is the report. Flagging for awareness — a reader can be briefly confused. Not a dashboard bug per se.

**[BR-6] Live-freshness caption differs between pages loaded seconds apart** — `P3` · — · observation · cross-page
- **Saw:** the Briefing benchmark strip read "● LIVE · FETCH FAILED — showing snapshot" while the Watchlist (same session, seconds later) read "● LIVE · 05:34 · 37/37 QUOTES." Per-page fetch + cache means freshness can diverge across pages. Low impact; inherent to the design — a glance only.

### Watchlist (+ drilldown)

The table and drilldown are **strong** — click-to-expand, report-date picker, per-name ACCUMULATE gates, thesis-break condition, and news pills all read clearly (`screens/watchlist-desktop-1440.png`, `screens/watchlist-nvda-drilldown.png`). The one substantive issue is the R:R display, tracked as **[BR-2]** — the Watchlist R:R column (`row.py:58`) and the drilldown "Headline R:R" both show the distorted 46.5:1, and the corrective "Wide-stop R:R" row shows "—" for `sizing_rr` names. No other blocking issues on this page.

**[WL-1] drilldown "Wide-stop R:R" misses the `sizing_rr` variant** — `P2` · S · ✅ auto-fix · folded into **BR-2** (make the corrective row recognize `sizing_rr`, not just `wide_stop_rr`).

### Signal Tracker

Rich and honest — a direction-aware calibration hero (BUY/ACC/WATCH = win rate, CAUTION = avoid rate), a per-name track-record ledger with episode drill-downs, and clear methodology notes (`screens/signal-tracker-desktop-1440.png`). The calibration cards deliberately keep the numeral neutral and ride performance on a meter (`signal_tracker.py:357-360`) — a thoughtful fix so "CAUTION-red" doesn't read as bad. One finding, plus two drawers left for a follow-up.

**[ST-1] By-name Avg/Best/Worst returns are colored by raw sign, so correct CAUTION calls render red/"bad"** — `P2` · S · treatment 🧑‍⚖️ (has in-file precedent) · Signal Tracker → By Name
- **Saw (rendered colors, from the live DOM):** every CAUTION name's returns are painted red `rgb(239,68,68)` — NVTS Avg **-34.8%**, Worst **-53.1%**; CRWV -21.4%; LITE -18.8%. But for a CAUTION ("trim/avoid") call a *fall* is the call being **right**. BE shows a green "100% trades won" bar next to red -3.4% / -18.5% returns in the *same row*. The coloring is in fact **inverted** for CAUTION: INTC (CAUTION, **+6.8%**) is green though a *rise* means the avoid-call was wrong so far, while NVTS (CAUTION, **-34.8%**) is red though the fall made it a great call. Today's list is mostly CAUTION, so the Avg column reads as a "sea of red" that mostly represents *correct* calls (`screens/signal-tracker-byname-table.png`).
- **Cause:** `_ret_num_cell` → `_ret_color` (`signal_tracker.py:326-329, 393-396`) = `STATUS_POS if v>0 else STATUS_NEG`, applied to all three columns regardless of signal direction. `avg` also blends BUY+CAUTION episodes for a name (`:459`), so one sign-colored number spans outcomes whose "good" direction differs.
- **Why it matters:** the page exists to give an honest read of how signals performed; coloring a correct CAUTION call red inverts that read. The author already solved this on the calibration cards — the ledger just wasn't brought in line.
- **Fix (matches the calibration-card precedent):** make Avg/Best/Worst numerals neutral (`--ink`) and let the direction-aware "Trades won" bar carry performance; or color by signal-correctness, not raw sign.
- **Counter-view considered:** if these columns are meant purely as "which way did the stock move" (factual), sign-coloring is internally defensible — but that conflicts with the correctness-colored winbar beside them and the blended average. Flagging for your call.

**Not deeply reviewed this pass:** the "Signal changes (155) — what flipped, and why" and "Paper trade outcomes — realised returns" drawers were left collapsed; worth a dedicated look.

### Pipeline Stats

Clean pipeline telemetry — token usage, generation time, and cache-aware API cost per report, with an honest cutover note (pre-2026-05-05 Claude rates excluded as ~10× overstated; now `deepseek-v4-pro`). Reads well (`screens/pipeline-stats-top.png`).

**[PS-1] API Cost chart's date span looks inconsistent with the 30-day filter — needs confirmation** — `P3` · S · 🔎 verify · Pipeline → API Cost
- **Saw:** with the sidebar on "30 days" (Jun 4 – Jul 4), the token & gen-time charts start ~Jun 4, but the **API Cost** chart's x-axis starts **May 10** (~55 days, outside the window).
- **Checked:** the page clips cost via `_clip(load_pipeline_stats())` (`pipeline_stats.py:91`), and a standalone repro of that same clip returns only in-window rows (25 rows, from Jun 4) — so it *should* limit cost to the window, yet the live chart shows May bars. There's also a design tension: the cost section's own comment wants to show the pre/post-**cutover** step-change (`:88-89`), which needs pre-cutover (< May 5) data that a 30-day clip would remove.
- **Why flagged, not asserted:** couldn't reconcile statically — either the clip isn't taking effect on the cost frame in the live render, or the active range differed at capture. Verify by toggling the Range control and watching whether the cost chart's start date moves. Low severity (telemetry page).

**[PS-2] The stats page silently inherits the global date range** — `P3` · — · observation. "Total Reports 25 / Avg Tokens / Avg Gen Time" reflect the 30-day window, not all-time (82 reports). Reasonable, but a first-time reader may expect all-time on a page titled "Statistics" — a small "(last 30 days)" qualifier would remove the ambiguity.

### Scenario Log

Strong and honest — a probability time-series (a distinct marker per series for colour-blind safety) plus a dated "days when probabilities moved" ledger with each shift's before→after and full narrative (`screens/scenario-log-top.png`). I verified the internal math: each day's shifts net to zero, and chaining Jul 2→3→4 lands exactly on the Briefing's current odds (Base 55 / Opt 20 / Pess 20 / Wild 5) — cross-page consistent. Clear disclaimer that these are uncalibrated narrative leans.

**[SC-1] "Wildcard" uses a different colour here than on the Briefing** — `P3` · S · 🧑‍⚖️ proposal · cross-page
- **Saw:** Base/Optimistic/Pessimistic read as the same blue/green/red on both pages, but **Wildcard is amber on the Briefing odds bar** (`macro.py:161`, `SIGNAL_COLORS["WATCH"]`) and **purple on the Scenario Log** chart + ledger (`scenario_log.py:213`, `ACCENT_WILDCARD`). The two pages source scenario colours from different constant sets.
- **Why it matters:** the same four scenarios ideally carry one colour language across the app; a reader cross-referencing sees wildcard flip amber→purple.
- **Nuance (may be deliberate):** the Scenario chart is thoughtfully colour-blind-aware (distinct markers; comment `:215-217`), and blue/green/red/purple are four maximally-distinct hues. If intentional, consider aligning the Briefing wildcard to purple (or documenting the divergence) rather than changing the chart. Your call — hence a proposal, not a fix.

### Report Comparison
_(pending)_

### Terminology
_(pending)_

### Cross-cutting (nav, theme, responsive, a11y)
_(pending)_

---

## Branches created
_(none yet)_
