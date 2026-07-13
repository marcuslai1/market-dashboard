# Extended-Hours Quotes (PRE/POST) — Design

**Date:** 2026-07-13 · **Status:** approved (user picked "option 1" + everywhere-scope + Δ vs last regular close + SKHYV fallback bundled)

## Problem

During the Singapore afternoon/evening the US market is closed or in pre-market.
The live overlay uses `yfinance fast_info.last_price`, which only tracks the
regular session — so all ~26 US names sit frozen at Friday's close while
brokers (IBKR) show moving pre-market prices. Verified 2026-07-13: dashboard
NVDA $210.96 vs Yahoo pre-market $208.00 (−1.40%); non-US rows were updating
fine. Separately, SKHYV (days-old Nasdaq listing) gets **no** live quote at all
because Yahoo returns `last_price` without `previous_close` and `_fetch_one`
requires both.

## Decision summary

| Question | Decision |
|---|---|
| Scope | Everywhere the overlay applies: watchlist rows, pulse strip (SPY/QQQ/SOXX), Today's Trade card |
| Δ basis in PRE/POST | vs last regular close (matches IBKR and Yahoo's own pre/post %) |
| Data source | One batched `yf.download(us_syms, period="1d", interval="1m", prepost=True)` — measured 0.85s for 26 symbols; matches `.info` pre-market print exactly |
| Session detection | Clock-based ET windows via `zoneinfo` (PRE 4:00–9:30, POST 16:00–20:00, weekdays); no network. Holidays self-correct: no bars in window → no overlay |
| SKHYV | `_fetch_one` falls back to `{price, chg_pct: None}` when `previous_close` missing; renderers already show `None` Δ as "—" |

Rejected: per-ticker `.info` (0.61s × 26 ≈ blows the 4s deadline, rate-limit
prone); switching the whole fetch to `.info` (penalizes all 39 symbols).

## Fetch (`live_prices.py`)

- `_us_session_now(now=None) -> "PRE" | "POST" | None` — pure, testable via
  the `now` parameter (`America/New_York` via `zoneinfo`).
- `_us_symbols(mapping) -> dict` — subset of `TICKER_TO_YAHOO` whose Yahoo
  symbol has no `.` / `=` / `^` / `-` (excludes .KS/.SI/.DE/.PA listings,
  futures, indices, DXY). SPY/QQQ/SOXX pass.
- `_fetch_ext_bars(symbols)` — the batched prepost download; returns the raw
  frame or `None` on any exception (fail-soft).
- `_ext_quotes_from_bars(bars, session, now) -> {key: ext_price}` — pure merge:
  last valid 1-minute close per symbol **with a bar timestamp inside the
  current session window today (ET)**; symbols with no in-window bar are
  absent. Unit-testable with a synthetic frame, no network.
- `fetch_live_quotes()`: when a session is active (and quotes not disabled),
  submit the download to the same `ThreadPoolExecutor` **alongside** the
  per-ticker `fast_info` futures; harvest it within the same 4s deadline
  (measured: hides entirely inside the 1.7–3.3s fast_info batch). For each
  US key with both a regular quote and an in-window ext price:
  `quote["ext_price"]`, `quote["ext_chg_pct"] = (ext − last) / last × 100`
  (during PRE, `fast_info.last_price` *is* the last regular close — verified
  reproduces Yahoo's −1.40% for NVDA), `quote["ext_session"] = session`.
  `__meta__` gains `"session"`.
- `_fetch_one`: if `last` present but `prev` missing/0 → return
  `{"price": last, "chg_pct": None}` instead of `None`.
- `overlay_live`: when a quote carries ext fields, write `ext_price` → `price`,
  `ext_chg_pct` → `chg_pct`, and set `live_session` on the entry; otherwise
  behavior unchanged. Snapshot fields still never touched.

## Display

- `components/watchlist/row.py` — small mono tag (`.ext-tag`) after the Δ in
  the Last · Δ cell when `d["live_session"]` is set.
- `components/briefing/pulse.py` — same tag in the delta line of cells whose
  benchmark carries `live_session`.
- `components/briefing/action_card.py` — "`{Δ} today`" becomes
  "`{Δ} pre-mkt`" / "`{Δ} after-hrs`" when `live_session` set.
- `lib/pills.py` `_render_live_caption` — label becomes
  `LIVE · PRE-MARKET · 17:34 · 38/39 quotes` (or `AFTER-HOURS`) when
  `__meta__["session"]` set.
- `assets/theme.css` — `.ext-tag`: mono, ~9px, muted amber, tiny padding;
  no layout shift (inline-block inside existing cells).
- Visual baselines unaffected: harness runs `LIVE_QUOTES_DISABLED=1`, so ext
  fields never exist there.

## Error handling

Unchanged fail-soft philosophy: download error/timeout/empty → no ext fields →
today's behavior (regular-session live or snapshot). No new user-facing error
states.

## Testing

- `_us_session_now`: PRE/POST/closed/weekend boundaries via injected `now`.
- `_ext_quotes_from_bars`: in-window bar picked, stale (Friday) bars ignored,
  NaN tails handled, missing symbol absent.
- `_fetch_one` fallback: mocked yfinance — prev missing → price with `None` Δ.
- `overlay_live`: ext fields overlay price/Δ and set `live_session`; entries
  without ext unchanged; input not mutated.
- Renderers: tag present when `live_session` set, absent otherwise; action
  card "pre-mkt" suffix; caption session label. Δ `None` renders "—".
- End-to-end: run app during a live PRE session and confirm tagged pre-market
  prices in watchlist + pulse.
