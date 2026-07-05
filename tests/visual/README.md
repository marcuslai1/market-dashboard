# Visual regression tests

Full-page screenshots of every dashboard page (and two key interactive states),
pixel-diffed against committed baselines. Everything runs inside the pinned
Playwright image `mcr.microsoft.com/playwright/python:v1.60.0-jammy` so rendering
is identical in CI and locally — fonts, anti-aliasing, chromium version, and
Plotly canvas output all come from that image.

## What is covered

| Baseline | Source test | Notes |
|---|---|---|
| `briefing`, `watchlist`, `signal-tracker`, `pipeline-stats`, `scenario-log`, `report-comparison`, `terminology` | `test_pages.py` | the 7 pages, each captured full-page |
| `watchlist-nvda-drilldown` | `test_states.py` | NVDA row `<details>` expanded |
| `signal-tracker-ledger` | `test_states.py` | first by-name episode ledger row expanded |

`test_harness_unit.py` unit-tests the pure comparator (no browser); `test_smoke.py`
asserts the app boots. Comparison is anti-aliasing-aware (`pixelmatch
includeAA=False`) with a `max_diff_ratio=0.002` tolerance (see `harness.py`).
A small page-height gap spends that same budget (the grow-until-stable capture
wobbles the page tail by a row or two between runs) — only a width change or a
height gap big enough to be a real band fails outright. `VISUAL_UPDATE=1` only
rewrites baselines the capture no longer matches, so a regen run cannot churn
within-tolerance jitter into commits.

## Run (compare against committed baselines)

```
make visual
```

`make` is **not installed on the Windows dev host.** Run the same thing directly:

```
docker run --rm -v "$PWD":/work -w /work \
  mcr.microsoft.com/playwright/python:v1.60.0-jammy \
  bash -lc "pip install -q -r requirements.lock playwright==1.60.0 pytest-playwright pixelmatch pillow \
            && python -m playwright install chromium \
            && python -m pytest tests/visual -q"
```

(On Windows use a single line, or run it from Git Bash / WSL.)

Always invoke pytest as `python -m pytest tests/visual -q`. The module form puts
the repo root on `sys.path` so the suite's `lib.*` / `tests.visual.*` imports
resolve; bare `pytest` fails collection with `ModuleNotFoundError`.

## Update baselines (ONLY after an intentional UI change)

```
make visual-update        # sets VISUAL_UPDATE=1, rewrites tests/visual/baselines/*.png
git add tests/visual/baselines/*.png
git commit -m "test(visual): update baselines for <what changed>"
```

Directly (no `make`): same `docker run …` as above, but with
`VISUAL_UPDATE=1 python -m pytest tests/visual -q` as the final command.

### The one hard rule

**Never commit a baseline generated outside the `v1.60.0-jammy` image.** Host
font rendering (Windows/macOS) differs pixel-for-pixel from the image's Linux
freetype/fontconfig stack, so a locally-rendered baseline is guaranteed to diff
against CI. Baselines are canonical *only* when produced in that exact image tag.
The tag is pinned in three places that must stay in lockstep: the `Makefile`
(`PW_IMAGE`), `.github/workflows/visual.yml` (`container.image`), and the pinned
`playwright==1.60.0` pip package (its bundled chromium is what the image ships).

## Why the output is deterministic

Screenshots only work as regression tests if two runs of unchanged code produce
byte-identical pixels. Four mechanisms guarantee that:

### 1. Three-layer network block (kills live-price flicker)

The dashboard fetches live quotes from Yahoo. Left alone, the pulse strip renders
per-second-changing prices and every snapshot flakes. It is blocked at **three**
layers because the fetch happens in two different processes:

- **Kill switch (primary)** — `conftest.py` sets `LIVE_QUOTES_DISABLED=1` in the
  server subprocess's env; `live_prices.fetch_live_quotes` honors it and skips
  the batch entirely (same pattern as `TEST_DATE`). This exists because the
  dead-proxy layer below only makes each fetch *fail* fast, not *stop* fast:
  yfinance's per-ticker fallback chain keeps the worker threads hot-looping curl
  retries after the fetch deadline returns, starving the script thread — on
  2026-07-05 that pushed first render to ~36s and every page past the 30s settle
  timeout. The app falls back to its frozen report-JSON snapshot (caption:
  "FETCH FAILED — showing snapshot").
- **Browser layer** — `conftest.py`'s `vpage` fixture calls `page.route("**/*", …)`
  to abort every non-localhost request (remote fonts, telemetry, and any
  browser-side fetch).
- **Server-subprocess layer (defense-in-depth)** — `conftest.py` also launches
  the server with `HTTP(S)_PROXY` pointed at a dead port (`127.0.0.1:9`) and
  `NO_PROXY=127.0.0.1,localhost`, so any *other* outbound call fails rather than
  introducing nondeterminism.

### 2. `TEST_DATE=2026-07-04` clock freeze

Four pages — **signal-tracker, pipeline-stats, scenario-log, report-comparison** —
filter their content to a **today-anchored 30-day window** (`dashboard.py`:
`_default_end = clock_today(); _default_start = _default_end - timedelta(days=30)`,
feeding the sidebar `st.date_input`). If "today" moved with the wall clock, which
reports fall inside that window would change and these baselines would rot day by
day, unrelated to any code change.

`lib/clock.py::today()` returns `date.today()` in production but honors a
`TEST_DATE=YYYY-MM-DD` override. `conftest.py` injects `TEST_DATE=2026-07-04`
(the latest report date) into the Streamlit **server subprocess's** environment,
so the whole app renders a fixed window.

- **Do NOT add `TEST_DATE` to the Makefile or the workflow.** conftest already
  injects it into the subprocess that needs it; CI inherits the frozen clock
  automatically. Setting it again elsewhere is redundant and misleading.
- **When new reports are added** and you want the window to include them: bump
  `TEST_DATE` in `conftest.py` (`_DETERMINISTIC_ENV`) to the new latest report
  date, then regenerate baselines (`make visual-update`) and commit them together
  — the render date and the pixels must move as one commit.

### 3. Grow-until-stable full-page capture

Streamlit scrolls its body *inside* `<section data-testid="stMain">`, so the
document stays viewport-height and a naive `full_page` screenshot would capture
only the first fold. `harness.py::grow_viewport_to_content` measures the real
content height and grows the viewport (width preserved) until the whole app fits,
re-measuring after each grow because Streamlit lazy-mounts content near the
viewport (a tall page can render *more* once enlarged). Capped at 4 iterations.
The interactive-state tests grow a **second** time after the click, so the newly
revealed drill-down is captured rather than clipped by the pre-click viewport.

### 4. Animations disabled

`vpage` injects CSS killing all `animation`/`transition` (re-asserted after every
Streamlit rerun) and stubs `matchMedia` to report reduced-motion.

## What is masked (and what is deliberately NOT)

Masks cover **only** genuinely wall-clock-derived DOM regions — everything else
that looks date-stamped (masthead long-date, table dates, episode durations,
scenario day headers) is a *static* report-JSON value and stays UNMASKED so real
regressions in it are caught. The masked regions:

- **Sidebar date input** (`[data-testid="stDateInput"]`) — global, rendered on
  every page; its default range is today-anchored.
- **Live-price caption** (`text=/LIVE ·|FETCH FAILED/`) — Briefing + Watchlist.
- **Capex "CURATION OVERDUE — N d old" staleness banner** — Briefing only; its
  age-in-days is computed from `date.today()`.

**No charts are masked.** Plotly canvases render deterministically under the
frozen clock + network block and are captured in full, so there are **zero
coverage gaps from charts** — a chart regression is a real, catchable diff.

## When a run fails

The harness writes the offending render and the diff image next to each other:

- **Locally:** `tests/visual/_diffs/<name>.actual.png` and `<name>.diff.png`
  (this directory is git-ignored).
- **In CI:** the `visual.yml` job uploads `tests/visual/_diffs/` as the
  **`visual-diffs`** artifact on failure — download it from the run's summary.

If the diff is an intentional change, regenerate baselines as above. If it is a
cross-environment font delta, the baseline was generated outside the
`v1.60.0-jammy` image — regenerate it in the correct image and recommit.
