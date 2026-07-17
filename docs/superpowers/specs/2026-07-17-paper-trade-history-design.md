# Paper-book trade history (round-trips) — design

- **Date:** 2026-07-17
- **Status:** Approved (brainstorm 2026-07-17; owner picked round-trips + same-drawer placement,
  then delegated remaining calls)
- **Origin:** The paper-book band shows *that* the book compounds, but not *how*: which day each
  position was bought and sold, and what each completed trade made or lost. `trade_counts` is
  aggregate-only, `trades_today` has been empty in every exported report (all fills predate the
  block's first export), and `paper_nav.csv` has no ticker-level rows — so there is nothing the
  dashboard can render today. This spec adds the missing export and the band's rendering of it.

## Decisions (brainstorm 2026-07-17)

1. **Row shape: round-trips.** One row per completed position — bought when/at what, sold
   when/at what, why it was sold, and the realized profit in dollars of the $10,000 display pot
   and in percent. A raw fills ledger makes the reader pair buys with sells themselves; the
   round-trip answers the actual question.
2. **Home: the existing drawer.** The "Positions & today's trades" expander becomes
   "Positions & trade history" *once history data exists* — open positions (now with P&L so far,
   when exported) followed by completed trades. One drawer for "what does the book hold and what
   has it done." Title and contents are byte-identical to today until the export lands.
3. **Pipeline stays the measurement engine.** Realized P&L per trade is computed upstream and
   exported; the dashboard's only new arithmetic is the same units→dollars presentation
   transform the NAV curve already uses, plus summing/counting the exported per-trade values for
   the drawer's verdict line.

## Data contract

- **`data/paper_trades.csv`** (new upstream export, same pattern as `paper_nav.csv`) — one row
  per **completed round-trip**, ordered by `policy_id, exit_date`:
  `policy_id, ticker, entry_date, avg_entry_price, tranches, exit_date, exit_price,
  exit_reason, pnl_pct, pnl_units`.
  - `entry_date` = first fill; `avg_entry_price` = cost-basis average across tranches;
    `tranches` = number of buys that built the position.
  - `exit_reason` ∈ the policy vocabulary (`stop`, `avoid_exit`, `delist_exit`, …) — rendered
    through a label map with the raw string as fallback, never invented dashboard-side.
  - `pnl_pct` = realized return on cost; `pnl_units` = realized P&L in book units (same integer
    units as `nav_units`).
  - Open positions are **not** rows here; they live in the report block (below).
- **`report.paper_portfolio.positions[]`** gains three optional fields: `entry_date`,
  `pnl_pct`, `pnl_units` (unrealized, marked-to-latest-close upstream). Positions without them
  render exactly as today.
- **Dashboard math budget** (extends the 2026-07-05 budget, same spirit): dollars of the pot =
  `pnl_units / first-valid nav_units of the same policy in paper_nav.csv × 10,000` — the
  identical rebase factor the NAV curve uses. The drawer verdict line may count winners/losers
  by the sign of exported `pnl_pct` and sum exported `pnl_units`. No pairing, no maturation, no
  cost-basis math dashboard-side.

## The rendering (components/paper_book.py, inside the drawer)

- **Order inside the drawer:** today's trades (unchanged) → open positions → completed trades.
- **Open positions table** gains two columns, only when at least one position carries the new
  fields: **Bought** (`entry_date`) and **P&L so far** (dollars when `pnl_units` is present and
  the rebase factor is available, else percent; "—" per-row when absent). Legend paragraph
  extends accordingly.
- **Completed trades table**, newest exit first:
  | Name | Bought | Sold | Why sold | Profit |
  - **Bought:** `Apr 22 @ $174.40`, with `avg · 3 buys` appended when `tranches ≥ 2`. Year is
    appended only when it differs from the latest report's as-of year.
  - **Sold:** `Jun 03 @ $216.10`.
  - **Why sold:** singular plain-language labels — `stop` → "stop-out (auto-sold)",
    `avoid_exit` → "AVOID exit", `delist_exit` → "delisted"; unknown reasons render raw.
  - **Profit:** `+$241 (+24.1%)` — dollars of the $10,000 pot (transform above) plus the
    exported return on cost. Percent-only when the rebase factor is unavailable (no usable
    `paper_nav.csv`). Positive/negative coloring follows the house STATUS tokens.
- **Verdict line first** (house style), directly above the completed-trades table: e.g.
  **"14 completed trades — 8 made money, 6 lost; together they added +$412 to the pot."**
- **Legend** (small print, `.pb-banner` style) explaining Bought/Sold/Why sold/Profit for the
  first-time reader, matching the positions legend's voice.
- **Policy scope:** the trades frame filters by the same selection rule as the NAV curve (block's
  `policy_id`; headline-book fallback; never blend multi-policy rows). Advisory-lane trades in
  the CSV are therefore invisible unless the block ever names such a lane.
- **Drawer title:** "Positions & trade history" when the completed-trades table renders,
  today's "Positions & today's trades" otherwise — the pre-export corpus renders byte-identical.
- **Expander presence:** renders when any of today's-trades / positions / completed-trades is
  non-empty (previously block-only; a trades CSV arriving before a block-bearing report still
  shows history).

## Error handling

- Missing/malformed `paper_trades.csv` → empty frame via `_safe_read_csv` → no history table,
  no title change; never raises.
- Malformed rows (missing ticker/dates/pnl) → skipped row-wise, matching the positions table's
  `.get()` tolerance. Unparseable dates render "—" rather than dropping the row only when the
  row is otherwise complete enough to be honest (ticker + profit); else skip.
- `pnl_units` present but NAV rebase factor unavailable → percent-only profit; no invented
  dollars.
- Tickers render through `display_ticker` (SKHY legacy-alias rename applies to history too).

## Testing

- Reducer tests (`tests/test_paper_book.py`): policy filtering (block-named, fallback,
  multi-policy-no-block → empty), newest-first ordering, dollar conversion against a known
  rebase factor, percent-only fallback, malformed-row skips, verdict line counts/sum, tranche
  suffix, reason labels + raw fallback, drawer-title switch, byte-identical absence tier.
- Loader test (`tests/test_data_loader.py`): `load_paper_trades()` missing-file → empty frame,
  present-file → frame (mirrors `load_paper_nav` tests).
- AppTest page walk stays green; current corpus asserts the history's absence.
- Visual baselines: one deliberate regen this session (the changelog strip changes); the band
  itself is unchanged until the export lands.
- `pytest -q` + `ruff check .` green.

## Upstream prerequisite (MarketReport repo)

Add a round-trips export to `export_to_dashboard` (`pipeline/output.py`): completed trades from
the paper-book SQLite → `data/paper_trades.csv` with the columns above, ordered by
`policy_id, exit_date`, plus an export-set test. Extend the report block's `positions[]` with
`entry_date` / `pnl_pct` / `pnl_units`. If the policy ever gains partial exits, export one row
per exit with its cost-basis share — the dashboard renders rows as given and needs no change.
Ships independently; the absence tiers make order irrelevant.

## Addendum 2026-07-17 — advisory ext-exit lanes' history

User request (same day, after the headline history shipped and deployed):
show the trade history of the exit-on-extension lanes so the *selling
behaviour* difference is visible against the headline book's stop-outs.

- **Scope: the `_ADVISORY_CURVES` allowlist**, exactly the two lanes already
  charted dashed (`v1_tc_ext_100` "ext-exit 10/5", `v1_tc_ext_100_b30`
  "ext-exit 30/15") — the same scoped exception to "no policy-variant
  comparison UI", not a generalization. `paper_trades.csv` already carries
  their round-trips; no upstream change.
- **Home: a sibling expander** directly under "Positions & trade history":
  **"Selling on extension — advisory trade history"**. Per lane: a heading
  with the exit-reason mix (e.g. "12 × stop-out · 3 × sold on extension"),
  the same verdict line, and the same round-trip table. One caveat line on
  top (hypothesis-grade, one regime — mirrors the chart's dashed-lane note);
  the shared history legend at the bottom. Renders only when at least one
  allowlisted lane has completed trades; otherwise the band is unchanged.
- **Labels:** within these lanes `caution_exit` renders as **"sold on
  extension"** — deterministic from the lane's trigger (the allowlist is
  ext-trigger by construction), not an invented semantic. `stop` keeps its
  headline label so the behavioural contrast is legible.
- **Dollars:** each lane converts `pnl_units` with **its own** NAV rebase
  factor (`trade_dollars_factor` with that lane's policy_id) — the same
  $10,000-pot each dashed curve plots. No cross-lane blending.

## Non-goals (v1)

- No per-fill ledger UI (round-trip rows carry the tranche count; the fills themselves stay
  upstream).
- No win-rate/expectancy analytics beyond the one verdict line — rendered only if/when the
  pipeline exports them.
- No history for advisory ext-exit lanes (headline-policy scope only, per the selection rule).
- No CSV download button beyond the house `chart_data_table` conventions elsewhere.
