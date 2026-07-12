# AI Capex Cycle Tracking — Ideas & Design Notes

> Status: **brainstorm / living doc.** Not a build plan yet. Captures the thinking
> from the 2026-06-13 session so we can keep refining before writing code.

---

## 0. The question this serves

The whole dashboard answers one thing: **"Is the AI trade still intact, and what breaks it?"**
Almost everything on the watchlist is downstream of AI infrastructure spending —
the chips, the memory, the optics, the power, even the SG banks as the "relative
safety" hedge when the trade wobbles.

Capex is the **load-bearing variable** under that question. But capex alone is a
number; understanding comes from watching capex *together with* the demand it's
spent against, the earnings it's supposed to produce, and the financing that keeps
it going. This doc collates capex **and the family of metrics around it** that turn
"spending went up 8%" into "the cycle is intact / digesting / cracking."

Design principle for everything below: **a metric earns its place only if it can
change a position decision.** A chart that doesn't move a signal is decoration.

---

## 1. The capex cycle as a 3-layer mental model

Money flows in a loop. Track all three layers or you only see part of the picture.

```
  ┌─────────────────────────────────────────────────────────────┐
  │  LAYER 1 — THE SPENDERS (demand)                             │
  │  Hyperscalers commit capex → datacenters, GPUs, power        │
  │  Holdings: MSFT · GOOG · AMZN   (+ CRWV = debt-funded cloud) │
  └───────────────┬─────────────────────────────────────────────┘
                  │  their capex = others' revenue
                  ▼
  ┌─────────────────────────────────────────────────────────────┐
  │  LAYER 2 — THE BENEFICIARIES (supply)                        │
  │  Chips:    NVDA · AMD · AVGO · INTC                          │
  │  Foundry:  TSM · (ASML = the equipment behind TSM)           │
  │  Memory:   MU · 000660.KS (SK Hynix)  — HBM cycle           │
  │  Optics:   LITE        — interconnect / photonics           │
  │  Power:    BE · 2308.TW (Delta) · NVTS · IFX.DE             │
  └───────────────┬─────────────────────────────────────────────┘
                  │  did the spend produce returns?
                  ▼
  ┌─────────────────────────────────────────────────────────────┐
  │  LAYER 3 — THE JUSTIFICATION (returns / digestion)          │
  │  Cloud revenue growth, margins, FCF, backlog/RPO,           │
  │  ROIC proxies — does the money come back?                   │
  └─────────────────────────────────────────────────────────────┘
```

The bear case ("AI capex bubble") is simply: **Layer 1 keeps climbing while Layer 3
fails to keep up.** Today's report literally encodes this — the wildcard scenario is
*"OpenAI's IPO collapses the AI funding bubble,"* AMZN's `thesis_break_condition` is
*"if the $200B AI capex announcement is delayed/cancelled,"* and the semis cluster
summary reads *"capex confirmed, but tactical setups are poor."*

---

## 2. Reframe: we can't measure "justified" — we measure *digestion*

Be intellectually honest. **"Is the capex justified?" is unknowable in real time** —
it's a multi-year ROIC question (will $200B of GPUs throw off enough cash over their
depreciation life?). Nobody knows yet; that's *why* it's the market's central debate.

What we *can* measure are the **leading proxies for digestion** — the cracks that
show up 1–3 quarters before the ROI verdict. So the deliverable is not a green
"✅ justified" light; it's a **digestion scorecard** that reads something like:

> *Capex accelerating ▲ · Coverage gap widening ⚠ · Margins holding ✅ · Multiples
> still cheap ✅ → "Cycle intact, watch the coverage gap."*

---

## 3. The metric family — "what else, like capex, gives us understanding"

Capex is one input. Here is the broader set, grouped by what each reveals. Columns:
**Lead/Lag** = does it move before or after the cycle turns; **Have?** = is it in the
daily report schema today.

### Tier A — Demand side (the spenders)
| Metric | What it reveals | Lead/Lag | Cadence | Have? |
|---|---|---|---|---|
| **Capex ($, YoY/QoQ)** | Raw spending direction | Coincident | Quarterly | ✗ (free-text only) |
| **Forward capex guidance** | Next year's budget intent — often more market-moving than the print | **Leading** | Quarterly | ✗ |
| **Capex intensity** (capex / revenue) | Is the spend sustainable vs the business? | Coincident | Quarterly | ✗ |
| **Funding mix** (op-cash-flow vs debt vs equity) | Fragility — self-funded (MSFT/GOOG) vs debt-funded (CRWV/ORCL) | Leading | Quarterly | ✗ |
| **Cloud / AI segment revenue growth** (Azure, GCP, AWS) | Is the demand they're spending *against* real? | Coincident | Quarterly | partial |
| **Backlog / RPO** (remaining perf. obligations) | Contracted forward demand — MSFT/ORCL report it | **Leading** | Quarterly | ✗ |
| **Cloud operating margin** | Depreciation drag as GPUs age = capex biting earnings | Lagging | Quarterly | ✗ |
| **Depreciation useful-life assumptions** | Extending GPU life 5→6yr flatters EPS = earnings-quality red flag | Leading | Quarterly | ✗ |

### Tier B — Supply side (the beneficiaries)
| Metric | What it reveals | Lead/Lag | Cadence | Have? |
|---|---|---|---|---|
| **Datacenter revenue growth** (NVDA DC, AVGO AI rev) | Is the spend landing as sales? | Coincident | Quarterly | ✓ `revenue_growth_pct` |
| **Coverage gap** = beneficiary rev growth − spender capex growth | THE digestion signal: capex rising while sales decelerate = trouble | **Leading** | Quarterly | derivable (needs capex) |
| **Book-to-bill** (esp. ASML) | Orders vs shipments — forward demand | **Leading** | Quarterly | ✗ |
| **Gross margin** (NVDA ~75% is the canary) | Pricing power; compression = competition/soft demand | Leading | Quarterly | ✗ |
| **Inventory / channel inventory** | Building inventory = demand air-pocket forming | **Leading** | Quarterly | ✗ |
| **Customer concentration** (top-4 hyperscalers % of NVDA) | Fragility to any single budget cut | Structural | Quarterly | ✗ |
| **HBM ASP / memory pricing** | Clean leading gauge of AI demand intensity (MU, SK Hynix) | **Leading** | Monthly-ish | ✗ |
| **CoWoS / advanced-packaging utilization** (TSM) | The real physical bottleneck for accelerators | Leading | Quarterly | ✗ |

### Tier C — Justification / returns
| Metric | What it reveals | Lead/Lag | Cadence | Have? |
|---|---|---|---|---|
| **FCF trajectory of spenders** | Capex is crushing FCF — when does it inflect? | Coincident | Quarterly | ✓ `fcf_yield_pct` (sellers) |
| **Incremental rev / incremental capex** (ROIC proxy) | Crude "are returns there yet" | Lagging | Quarterly | derivable |
| **Power availability / grid interconnect queue** | Increasingly the *binding* constraint, not chips | **Leading** | Irregular | ✗ |
| **PPA / energy deals announced** | Hyperscalers locking power = forward commitment | Leading | Event | ✗ |
| **Token / inference cost trend** | Falling cost-per-token = better unit economics = capex more justifiable | Leading | Irregular | ✗ |

### Tier D — Financing & sentiment (the bubble plumbing)
| Metric | What it reveals | Lead/Lag | Cadence | Have? |
|---|---|---|---|---|
| **Credit spreads on debt-funded players** (CRWV, ORCL bonds) | First place stress shows up | **Leading** | Daily | ✗ |
| **Circular / vendor financing** | Late-cycle bubble tell (see §5) | Leading | Event | ✗ |
| **AI equity issuance / IPO pipeline** (OpenAI IPO) | Supply of paper = froth gauge; already in wildcard | Leading | Event | ✗ |
| **Valuation dispersion** (fwd PE vs growth / PEG, PE vs cluster) | Is the *market* losing faith? | Coincident | Daily | ✓ `forward_pe`, `peg_ratio`, `pe_vs_cluster_pct` |
| **Short interest / positioning** | Crowding | Coincident | Daily-ish | ✗ |

### Tier E — Macro overlays (mostly already present)
- **Rates / US10Y** — discount rate on long-duration AI cash flows + cost of debt-funded capex. *(have)*
- **Oil / geopolitics (Hormuz)** — current geo scenario driver. *(have, `geopolitical`)*
- **FX / DXY** — matters for TSM, ASML, SK Hynix, SG banks. *(have, `benchmarks`)*

---

## 4. The single sharpest signal: the **coverage gap**

If we build only one thing, build this.

```
  coverage_gap = (beneficiary revenue growth %)  −  (spender capex growth %)

  gap widening (capex outrunning sales) → digestion / air-pocket risk → ↑ pessimistic odds
  gap stable/closing (sales keeping pace) → cycle intact → base holds
```

We already have the beneficiary side *daily* (`revenue_growth_pct` per ticker,
snapshotted in every report). The only missing input is the spenders' capex — a
small quarterly series. That asymmetry is the whole feasibility story: **half of
this is free; one piece needs sourcing.**

---

## 5. Specific tell worth its own tracker: circular financing

NVDA invests in CoreWeave (**CRWV — which you hold**); CRWV uses that to buy NVDA
GPUs; NVDA books the revenue. The money loops. Classic late-cycle bubble pattern
(cf. telecom vendor financing, 1999-2000). Because **CRWV is in the book**, a
"circularity watch" — NVDA→customer investments, neo-cloud debt raises — is both
specific and directly relevant to a position you own. Worth flagging explicitly
rather than burying in narrative.

---

## 6. The earnings-cascade framework ("track earnings → understand the result")

This is the part you emphasized: track the important players' **earnings**, then
**understand what happens as a result.** Your reports already have the scaffolding —
`scheduled_tech_events`, per-ticker pre-earnings bands (MU "reports in 12 days"),
and `macro_trigger_map` (which maps catalysts → ticker signal changes for bull/bear
paths). Extend that pattern from *macro events* to *earnings events*:

For each key player, define **ex-ante** what the bull/bear earnings outcome is and
which of *your* positions it cascades to:

> **Example — MU earnings (Jun 25):**
> - **Read:** MU + SK Hynix are the memory cycle; HBM ASPs are a clean proxy for AI
>   demand intensity.
> - **Bull (beat + HBM guide raise):** confirms Layer-2 demand → SK Hynix (000660),
>   and reinforces NVDA/AVGO datacenter thesis → base/optimistic odds firm.
> - **Bear (guide miss, HBM ASPs soften):** earliest crack in the coverage gap →
>   cascades to 000660 (CAUTION), pressures the whole semis cluster → pessimistic ↑.
> - **Cascade map:** MU → {000660.KS, NVDA, AVGO, TSM}.

The dashboard already lists earnings dates; the missing layer is the **pre-wired
"if beat / if miss → these tickers, this scenario shift."** That turns each earnings
date from a calendar entry into a decision the dashboard has already war-gamed.

---

## 7. Map to the actual book (who to track, by role)

| Role | Holdings | Why track |
|---|---|---|
| **Spenders (capex demand)** | MSFT, GOOG, AMZN | Their capex = everyone else's revenue. Self-funded → durable. |
| **Debt-funded cloud** | CRWV | Fragile tier; first to crack; circular-financing node (§5). |
| **GPU / accelerator** | NVDA, AMD, AVGO | Direct beneficiaries; gross margin = canary. |
| **Foundry + equipment** | TSM, ASML | CoWoS packaging is the physical bottleneck; ASML book-to-bill leads. |
| **Memory (HBM cycle)** | MU, 000660.KS | HBM ASPs = leading demand-intensity gauge. |
| **Optics / interconnect** | LITE | Scales with cluster size; InP supply risk (China export — in wildcard). |
| **Power / electrical / cooling** | BE, 2308.TW (Delta), NVTS, IFX.DE | The emerging *binding constraint* — power, not chips. Underweighted in current macro note. |
| **AI software (demand pull-through)** | PLTR | Demand-side proof the apps monetize. |
| **Non-AI hedge** | D05.SI, O39.SI, U11.SI (DBS/OCBC/UOB) | "Relative safety" when the trade wobbles. |

Note: the current macro note barely mentions **power/energy**, yet you hold four
power-chain names. That's a gap a capex lens would naturally fill.

---

## 8. Data feasibility — have vs need

**Have today (daily, per ticker, from Yahoo `valuation`):**
`forward_pe`, `trailing_pe`, `ev_ebitda`, `peg_ratio`, `fcf_yield_pct`,
`revenue_growth_pct`, `analyst_consensus.earnings_growth_pct`,
`pe_vs_cluster_pct`. → the **beneficiary side and valuation/sentiment is free**, and
because every daily report is a snapshot, **time-series comes for free** (same
trick the Scenario Log already uses).

**Missing (the new dataset):** hyperscaler **capex**, **cloud segment revenue**,
**backlog/RPO**, **margins**, **book-to-bill**, **HBM ASPs** — all quarterly,
not in the pipeline.

**Sourcing options for the missing capex/segment data:**
| Option | Pros | Cons |
|---|---|---|
| **Hand-maintained file** (~5 names, 4×/yr) | Accurate; the curation *is* the analysis (deciding what counts as "AI capex" is judgment an API can't do) | Manual; rots if a quarter is skipped |
| **API** (FMP / Yahoo fundamentals) | Automated | Segment-level cloud revenue inconsistent across filers; capex includes non-AI spend to back out |

> Leaning: **start hand-maintained.** Curation is a feature, not a chore, at this
> scale. Revisit an API only if the name count grows.

---

## 9. Product / design options (where it lives)

- **The cadence mismatch:** daily dashboard vs quarterly capex. A quarterly series in
  a daily tool risks looking stale — solve with explicit "as of last earnings"
  framing (the macro-prints strip already does this for FRED data).
- **Don't default to a new page.** Instrumentation creep is the real risk — the
  dashboard's strength is that it's *decisive*. Options, cheapest first:
  1. **A single gauge** embedded in the scenario fork (ties capex to the odds — best).
  2. **A band on the Briefing** ("AI Capex Pulse").
  3. **Its own tab** — only once it's proven it moves decisions.

---

## 10. Open decisions (genuinely yours to make)

1. **Should the capex gauge *mechanically drive* the base/optimistic/pessimistic
   odds** (a widening coverage gap auto-raises pessimistic odds), or stay an
   **independent human-read check** you eyeball against Claude's narrative? → This
   one choice decides whether this is a small embedded gauge or a real modeling
   effort.
2. **Data source:** hand-maintained vs API (§8).
3. **Scope of spenders:** pure hyperscalers, or include the debt-funded neo-cloud
   tier (CRWV) that's the more fragile early-warning signal?
4. **Home:** embedded gauge vs Briefing band vs own page (§9).

---

## 11. Phased rollout (if/when we build)

- **v1 — free wins, no new data.** Time-series the beneficiary side we already have:
  revenue growth, earnings growth, FCF yield, forward-PE-vs-growth, per cluster.
  Add the earnings-cascade pre-wiring (§6) on top of existing `scheduled_tech_events`.
- **v2 — the coverage gap.** Add the hand-maintained hyperscaler capex file; compute
  and chart the coverage gap (§4); ship the digestion scorecard (§2).
- **v3 — the plumbing.** Power-chain tracking, credit spreads on debt-funded names,
  circular-financing watch (§5); optional wiring of the gauge into scenario odds.

---

### Appendix — connection to the Scenario Log work

The Scenario Log redesign (move ledger) gives the **time dimension**; the macro-fork
idea gives the **branches**; this capex work gives the **quantitative backbone** for
why those branches carry the odds they do. All three are facets of the same
"is the AI trade intact?" instrument — they should eventually reference each other,
not live as disconnected pages.
