/* MarketReport — Editorial Dashboard
   React application (single-file). Mounted by index.html.
*/

const { useState, useMemo, useEffect } = React;
const R = window.REPORT;

/* ───────────────────────── Tweaks defaults ───────────────────────── */
const TWEAK_DEFAULTS = /*EDITMODE-BEGIN*/{
  "theme": "paper",
  "density": "relaxed",
  "jargon": "plain",
  "accent": "amber"
}/*EDITMODE-END*/;

/* ───────────────────────── Helpers ───────────────────────── */
const fmt = (n, d = 2) => (n == null ? "—" : Number(n).toLocaleString("en-US", {
  minimumFractionDigits: d, maximumFractionDigits: d,
}));
const sign = (n) => (n > 0 ? "+" : "");
const deltaClass = (n, inverse = false) => {
  if (n == null || n === 0) return "flat";
  const up = n > 0;
  if (inverse) return up ? "down" : "up";
  return up ? "up" : "down";
};

const SIGNAL_ORDER = ["BUY", "ACCUMULATE", "WATCH", "HOLD", "CAUTION"];
const SIGNAL_VERB = {
  BUY: "Enter now",
  ACCUMULATE: "Add on strength",
  WATCH: "Wait for trigger",
  HOLD: "Maintain",
  CAUTION: "Trim / avoid",
};

const dayName = (iso) => {
  const d = new Date(iso + "T00:00:00");
  return d.toLocaleDateString("en-US", { weekday: "short" }).toUpperCase();
};
const fmtDate = (iso) => {
  const d = new Date(iso + "T00:00:00");
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
};

/* ───────────────────────── Masthead ───────────────────────── */
function Masthead({ tab, setTab, reportDate }) {
  const long = new Date(reportDate + "T00:00:00").toLocaleDateString("en-US", {
    weekday: "long", year: "numeric", month: "long", day: "numeric",
  });
  return (
    <header>
      <div className="masthead">
        <div className="masthead-l">
          <div className="kicker">Morning Briefing · Volume IV · No. 117</div>
          <h1 className="masthead-title">
            The <em>Market</em> Report
          </h1>
        </div>
        <div className="masthead-r">
          <div className="date">{long}</div>
          <div>Singapore · 11:30 SGT · Last close {R.meta.market_date}</div>
        </div>
      </div>
      <div className="masthead-meta">
        <div className="vol-no">Signal Intelligence · Daily</div>
        <div className="nav-tabs">
          {["Briefing", "Watchlist", "Calendar", "Macro"].map(n => (
            <button
              key={n}
              className={"nav-tab " + (tab === n ? "active" : "")}
              onClick={() => setTab(n)}
            >{n}</button>
          ))}
        </div>
        <div>Updated 11:30 SGT</div>
      </div>
    </header>
  );
}

/* ───────────────────────── Stance hero ───────────────────────── */
function Stance() {
  const total = Object.values(R.signal_counts).reduce((a, b) => a + b, 0);
  return (
    <section className="stance">
      <div>
        <div className="stance-deck">
          <span>Today's Posture</span>
          <span style={{ color: "var(--ink-3)" }}>· {total} names tracked</span>
        </div>
        <h2 className="stance-headline">{R.stance_plain}</h2>
        <div className="stance-byline">
          {R.stance.toUpperCase()} · By the signal desk
        </div>
      </div>
      <div className="stance-counts">
        {SIGNAL_ORDER.map(sig => {
          const n = R.signal_counts[sig] || 0;
          const cssVar = `var(--${sig.toLowerCase()})`;
          return (
            <div key={sig} className={"count-cell " + (n === 0 ? "has-zero" : "")}>
              <div className="label">
                <span className="dot" style={{ background: cssVar }}></span>
                {sig}
              </div>
              <div className="num" style={n > 0 ? { color: cssVar } : null}>{n}</div>
            </div>
          );
        })}
      </div>
    </section>
  );
}

/* ───────────────────────── Pulse strip ───────────────────────── */
function Pulse() {
  const order = ["SPY", "QQQ", "VIX", "WTI", "Gold", "DXY", "US10Y", "SOXX"];
  return (
    <section className="pulse">
      {order.map(k => {
        const b = R.benchmarks[k];
        const inverse = !!b.inverse;
        return (
          <div key={k} className="pulse-cell">
            <div className="label">{k} · {b.unit}</div>
            <div className="price">{fmt(b.price, b.price > 1000 ? 0 : 2)}</div>
            <div className={"delta " + deltaClass(b.chg, inverse)}>
              {sign(b.chg)}{fmt(b.chg, 2)}%
            </div>
          </div>
        );
      })}
    </section>
  );
}

/* ───────────────────────── Changes ribbon ───────────────────────── */
function Changes() {
  if (!R.changes.length) return null;
  return (
    <div className="changes-ribbon">
      <span className="label">Since yesterday</span>
      {R.changes.map(c => {
        const arr = c.direction === "up" ? "↑" : "↓";
        return (
          <span key={c.ticker} className="change-item">
            <strong>{c.ticker}</strong>
            <span className={`sig-pill sig-${c.from}`} style={{ padding: "1px 6px", fontSize: 9.5 }}>{c.from}</span>
            <span className={`arr ${c.direction}`}>{arr}</span>
            <span className={`sig-pill sig-${c.to}`} style={{ padding: "1px 6px", fontSize: 9.5 }}>{c.to}</span>
            <span className="change-note">— {c.note}</span>
          </span>
        );
      })}
    </div>
  );
}

/* ───────────────────────── Action card ───────────────────────── */
function ActionCallout() {
  // Pick the single most actionable name — first WATCH on the list
  const w = R.watchlist.find(t => t.signal === "WATCH") || R.watchlist[0];
  return (
    <div className={"action-card " + w.signal.toLowerCase()}>
      <div className="action-tag">
        <div>If you only do</div>
        <div>one thing today</div>
        <div className="pill">{SIGNAL_VERB[w.signal]}</div>
      </div>
      <div className="action-body">
        <div className="ticker">{w.display} · {w.name}</div>
        <div className="head">{w.headline}</div>
        <div className="plain">{w.plain}</div>
      </div>
      <div className="action-r">
        <div>Last</div>
        <div className="level">{w.ccy === "SGD" ? "S$" : "$"}{fmt(w.price, 2)}</div>
        <div style={{ marginTop: 8, color: deltaClass(w.chg) === "up" ? "var(--buy)" : "var(--caution)" }}>
          {sign(w.chg)}{fmt(w.chg, 2)}% today
        </div>
        <div style={{ marginTop: 8 }}>{w.next_event}</div>
      </div>
    </div>
  );
}

/* ───────────────────────── Watchlist row ───────────────────────── */
function vsSma50Color(v) {
  if (v == null) return "var(--ink-3)";
  if (v > 5) return "var(--caution)";
  if (v > 2) return "var(--watch)";
  if (v >= -2) return "var(--buy)";
  return "var(--accumulate)";
}

function GaugeSMA({ value }) {
  // -10..+10 mapped to 0..100%
  const v = Math.max(-10, Math.min(50, value ?? 0));
  // remap: -10 → 0%, 0 → 35%, +5 → 60%, +50 → 100%
  let pct;
  if (v <= 0) pct = (v + 10) / 10 * 35;
  else if (v <= 5) pct = 35 + (v / 5) * 25;
  else pct = 60 + Math.min(40, (v - 5) / 45 * 40);
  const color = vsSma50Color(value);
  return (
    <span style={{ display: "inline-flex", alignItems: "center" }}>
      <span className="gauge">
        <span className="gauge-track"></span>
        <span className="gauge-zero"></span>
        <span className="gauge-dot" style={{ left: pct + "%", background: color }}></span>
      </span>
      <span className="gauge-num" style={{ color }}>
        {value == null ? "—" : `${sign(value)}${fmt(value, 1)}%`}
      </span>
    </span>
  );
}

function RsiBar({ value }) {
  if (value == null) return <span className="t-num">—</span>;
  const pct = Math.max(0, Math.min(100, value));
  return (
    <span style={{ display: "inline-flex", alignItems: "center", gap: 8 }}>
      <span className="rsi-dot">
        <span className="marker" style={{ left: `calc(${pct}% - 1px)` }}></span>
      </span>
      <span className="t-num">{fmt(value, 0)}</span>
    </span>
  );
}

function WatchlistRow({ t, expanded, onToggle, jargon }) {
  const prevDifferent = t.prev && t.prev !== t.signal;
  return (
    <React.Fragment>
      <tr className={expanded ? "expanded" : ""} onClick={onToggle}>
        <td className="t-tk">{t.display}</td>
        <td className="t-name">{t.name}</td>
        <td className="t-sig">
          <span className={`sig-pill sig-${t.signal}`}>{t.signal}</span>
          {prevDifferent && (
            <div className="t-prev">
              from <span style={{ textTransform: "uppercase" }}>{t.prev}</span>
            </div>
          )}
        </td>
        <td className="num t-num">
          {t.ccy === "SGD" ? "S$" : "$"}{fmt(t.price, 2)}
          <div className={`delta ${deltaClass(t.chg)}`} style={{ fontSize: 10.5 }}>
            {sign(t.chg)}{fmt(t.chg, 2)}%
          </div>
        </td>
        <td className="num">
          <span className={`delta ${deltaClass(t.m1)}`} style={{ fontFamily: "var(--mono)", fontSize: 12 }}>
            {sign(t.m1)}{fmt(t.m1, 1)}%
          </span>
        </td>
        <td><GaugeSMA value={t.vs_sma50} /></td>
        <td><RsiBar value={t.rsi} /></td>
        <td className="num t-num">{t.rr == null ? "—" : `${fmt(t.rr, 1)}:1`}</td>
        <td style={{ color: "var(--ink-3)", fontSize: 12 }}>{t.next_event}</td>
      </tr>
      {expanded && (
        <tr className="expanded">
          <td colSpan="9" style={{ padding: 0 }}>
            <div className="wl-detail">
              <div className="wl-detail-grid">
                <div>
                  <h4>The headline</h4>
                  <div className="plain-txt">{t.headline}</div>
                  <div style={{ marginTop: 16 }}>
                    <h4>What to do</h4>
                    <div style={{ fontSize: 14.5, color: "var(--ink-2)", lineHeight: 1.55 }}>{t.plain}</div>
                  </div>
                  {t.block && (
                    <div className="detail-block">
                      <h4>Entry block</h4>
                      <ul className="block-list"><li>{t.block}</li></ul>
                    </div>
                  )}
                  {jargon === "tech" && (
                    <div className="detail-block">
                      <h4>Technical detail</h4>
                      <div className="tech-txt">{t.tech}</div>
                    </div>
                  )}
                </div>
                <div>
                  <h4>By the numbers</h4>
                  <div className="metric-grid">
                    <div className="m-row"><span className="m-label">Cluster</span><span className="m-val">{t.cluster}</span></div>
                    <div className="m-row"><span className="m-label">Signal</span><span className="m-val">{t.signal}</span></div>
                    <div className="m-row"><span className="m-label">Forward P/E</span><span className="m-val">{t.pe_fwd == null ? "—" : fmt(t.pe_fwd, 1) + "x"}</span></div>
                    <div className="m-row"><span className="m-label">PEG</span><span className="m-val">{t.peg == null ? "—" : fmt(t.peg, 2)}</span></div>
                    <div className="m-row"><span className="m-label">Revenue growth</span><span className="m-val">{t.rev_g == null ? "—" : sign(t.rev_g) + fmt(t.rev_g, 1) + "%"}</span></div>
                    <div className="m-row"><span className="m-label">1mo return</span><span className="m-val">{sign(t.m1)}{fmt(t.m1, 1)}%</span></div>
                    <div className="m-row"><span className="m-label">vs 50-day avg</span><span className="m-val">{sign(t.vs_sma50)}{fmt(t.vs_sma50, 1)}%</span></div>
                    <div className="m-row"><span className="m-label">RSI (14d)</span><span className="m-val">{fmt(t.rsi, 0)}</span></div>
                    <div className="m-row"><span className="m-label">Risk:Reward</span><span className="m-val">{fmt(t.rr, 1)}:1</span></div>
                    <div className="m-row"><span className="m-label">Next event</span><span className="m-val" style={{ fontSize: 11 }}>{t.next_event}</span></div>
                  </div>
                </div>
              </div>
            </div>
          </td>
        </tr>
      )}
    </React.Fragment>
  );
}

/* ───────────────────────── Watchlist ───────────────────────── */
function Watchlist({ jargon }) {
  const [filter, setFilter] = useState("All");
  const [expanded, setExpanded] = useState(null);
  const filters = ["All", "Actionable", "BigTech", "Semis", "SG Banks", "Other"];

  const filtered = useMemo(() => {
    let list = R.watchlist;
    if (filter === "Actionable") list = list.filter(t => ["BUY", "ACCUMULATE", "WATCH"].includes(t.signal));
    else if (filter === "BigTech") list = list.filter(t => t.cluster === "BigTech");
    else if (filter === "Semis") list = list.filter(t => t.cluster === "Semis");
    else if (filter === "SG Banks") list = list.filter(t => t.cluster === "SG Banks");
    else if (filter === "Other") list = list.filter(t => !["BigTech", "Semis", "SG Banks"].includes(t.cluster));
    // Sort: signal priority, then biggest 1mo move
    const order = { BUY: 0, ACCUMULATE: 1, WATCH: 2, HOLD: 3, CAUTION: 4 };
    return [...list].sort((a, b) => order[a.signal] - order[b.signal] || (b.m1 || 0) - (a.m1 || 0));
  }, [filter]);

  return (
    <section className="section">
      <div className="section-head">
        <h3 className="section-title">The Watchlist</h3>
        <div className="section-sub">{R.watchlist.length} names · {filtered.length} shown · click to expand</div>
      </div>
      <div className="wl-filters">
        <span>Filter</span>
        {filters.map(f => (
          <button
            key={f}
            className={"wl-chip " + (filter === f ? "active" : "")}
            onClick={() => setFilter(f)}
          >{f}</button>
        ))}
      </div>
      <table className="wl">
        <thead>
          <tr>
            <th>Ticker</th>
            <th>Name</th>
            <th>Signal</th>
            <th className="num">Last · Δ</th>
            <th className="num">1mo</th>
            <th>vs 50-day</th>
            <th>RSI</th>
            <th className="num">R:R</th>
            <th>Next event</th>
          </tr>
        </thead>
        <tbody>
          {filtered.map(t => (
            <WatchlistRow
              key={t.ticker}
              t={t}
              expanded={expanded === t.ticker}
              onToggle={() => setExpanded(expanded === t.ticker ? null : t.ticker)}
              jargon={jargon}
            />
          ))}
        </tbody>
      </table>
    </section>
  );
}

/* ───────────────────────── Macro ───────────────────────── */
function Macro() {
  const probs = R.geopolitical.probabilities;
  const probColors = {
    base: "var(--accumulate)",
    optimistic: "var(--buy)",
    pessimistic: "var(--caution)",
    wildcard: "var(--watch)",
  };
  const probLabels = {
    base: "Base case",
    optimistic: "Optimistic",
    pessimistic: "Pessimistic",
    wildcard: "Wildcard",
  };
  return (
    <section className="two-col">
      <div>
        <div className="section-sub" style={{ marginBottom: 6 }}>The Macro Note</div>
        <p className="lede">{R.macro_summary}</p>
        <div className="body-copy">
          <p><strong>Portfolio implication.</strong> {R.geopolitical.portfolio_action}</p>
        </div>
        <div style={{ marginTop: 24 }}>
          <div className="section-sub" style={{ marginBottom: 8 }}>Scenario odds</div>
          <div className="probs">
            <div className="probs-bar">
              {["base", "optimistic", "pessimistic", "wildcard"].map(k => (
                <div key={k} className="probs-seg" style={{ width: probs[k] + "%", background: probColors[k] }}>
                  {probs[k]}%
                </div>
              ))}
            </div>
            <div className="probs-key">
              {["base", "optimistic", "pessimistic", "wildcard"].map(k => (
                <div key={k}>
                  <span className="sw" style={{ background: probColors[k] }}></span>
                  {probLabels[k]}
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
      <div>
        <div className="section-sub" style={{ marginBottom: 8 }}>Active risks</div>
        <ul className="risk-list">
          {R.geopolitical.active_risks.map((r, i) => (
            <li key={i}>
              <div className="tag">{r.tag}</div>
              <div className="text">{r.text}</div>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}

/* ───────────────────────── Calendar ───────────────────────── */
function Calendar() {
  const grouped = useMemo(() => {
    const m = {};
    R.events.forEach(e => { (m[e.date] = m[e.date] || []).push(e); });
    return Object.entries(m).sort(([a], [b]) => a.localeCompare(b));
  }, []);
  return (
    <section className="section">
      <div className="section-head">
        <h3 className="section-title">The Week Ahead</h3>
        <div className="section-sub">Catalysts that move signals</div>
      </div>
      <div className="calendar">
        {grouped.map(([date, events]) => (
          <div key={date} className="cal-day">
            <div className="cal-date">
              {fmtDate(date)}
              <span className="dow">{dayName(date)}</span>
            </div>
            <div className="cal-events">
              {events.map((e, i) => (
                <div key={i} className="cal-event">
                  <span className="cal-tk">{e.ticker}</span>
                  <span className={`cal-impact ${e.impact}`}>{e.impact}</span>
                  <span className="cal-text">{e.text}</span>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

/* ───────────────────────── Tweaks panel ───────────────────────── */
function Tweaks({ tweaks, setTweak }) {
  return (
    <TweaksPanel title="Tweaks">
      <TweakSection title="Theme">
        <TweakRadio
          value={tweaks.theme}
          onChange={(v) => setTweak("theme", v)}
          options={[
            { value: "paper", label: "Paper" },
            { value: "ink", label: "Ink" },
          ]}
        />
      </TweakSection>
      <TweakSection title="Density">
        <TweakRadio
          value={tweaks.density}
          onChange={(v) => setTweak("density", v)}
          options={[
            { value: "relaxed", label: "Relaxed" },
            { value: "compact", label: "Compact" },
          ]}
        />
      </TweakSection>
      <TweakSection title="Detail mode" subtitle="Plain English or full technical jargon in row drill-downs.">
        <TweakRadio
          value={tweaks.jargon}
          onChange={(v) => setTweak("jargon", v)}
          options={[
            { value: "plain", label: "Plain" },
            { value: "tech", label: "Technical" },
          ]}
        />
      </TweakSection>
    </TweaksPanel>
  );
}

/* ───────────────────────── App shell ───────────────────────── */
function App() {
  const [tweaks, setTweak] = useTweaks(TWEAK_DEFAULTS);
  const [tab, setTab] = useState("Briefing");

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", tweaks.theme);
    document.documentElement.setAttribute("data-density", tweaks.density);
  }, [tweaks.theme, tweaks.density]);

  return (
    <div className="shell">
      <Masthead tab={tab} setTab={setTab} reportDate={R.meta.report_date} />

      {tab === "Briefing" && (
        <React.Fragment>
          <Stance />
          <Pulse />
          <Changes />
          <section className="section">
            <div className="section-head">
              <h3 className="section-title">If you only do one thing today</h3>
              <div className="section-sub">The desk's single highest-conviction action</div>
            </div>
            <ActionCallout />
          </section>
          <Macro />
          <Calendar />
        </React.Fragment>
      )}

      {tab === "Watchlist" && (
        <React.Fragment>
          <Pulse />
          <Watchlist jargon={tweaks.jargon} />
        </React.Fragment>
      )}

      {tab === "Calendar" && (
        <React.Fragment>
          <Stance />
          <Calendar />
        </React.Fragment>
      )}

      {tab === "Macro" && (
        <React.Fragment>
          <Pulse />
          <Macro />
        </React.Fragment>
      )}

      <footer className="colophon">
        <div>The MarketReport · Signal Desk</div>
        <div>Generated {R.meta.report_date} · {R.watchlist.length} names tracked</div>
      </footer>

      <Tweaks tweaks={tweaks} setTweak={setTweak} />
    </div>
  );
}

ReactDOM.createRoot(document.getElementById("root")).render(<App />);
