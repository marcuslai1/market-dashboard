# Visual Regression Harness — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. **Read the "Context primer" section first — it front-loads app-specific knowledge you would otherwise have to rediscover.**

**Goal:** Catch UI/display regressions automatically by screenshotting every dashboard page in a fixed environment and pixel-diffing against committed baselines, gated in CI.

**Architecture:** A pytest suite (`tests/visual/`) launches the real Streamlit app via a session-scoped fixture, drives it with Playwright (Python) in a *single canonical render environment* (the pinned Playwright Docker image, used identically in CI and for local baseline updates), and compares each page against a committed baseline PNG using an anti-aliasing-aware pixel diff. Determinism is engineered in: external network is blocked (no live prices), animations are disabled, the viewport is fixed, and the handful of clock/live-derived regions are masked. A dedicated CI job runs the suite and uploads diff images on failure.

**Tech Stack:** Python 3.10, pytest, Playwright for Python (`playwright` + `pytest-playwright`), `pixelmatch` (aa-aware diff) + Pillow, GitHub Actions, the `mcr.microsoft.com/playwright/python` Docker image.

## Global Constraints

- **Python floor:** `>=3.10` (`pyproject.toml`). Target `py310`.
- **ruff must stay green:** CI runs `ruff check .` (line-length 100, selects E/W/F/I/B/UP/SIM/C4/RUF). All new code must pass. Sort imports (I001).
- **Do not add runtime deps to `requirements.lock`** — it is the app's uv-compiled runtime lock. Visual-test deps are installed separately in the visual CI job and the local Docker wrapper.
- **Canonical render environment is Linux via the pinned Playwright Docker image.** Baselines are generated *only* there. **Never commit a baseline rendered on macOS/Windows** — font hinting differs and every diff will be a false positive.
- **Determinism before coverage:** a snapshot that isn't stable across 3 consecutive runs is worse than no snapshot. Prove stability on one page before expanding.
- **Existing test suite (229 tests, `pytest -q`) must keep passing** and stay fast — visual tests live under `tests/visual/` and are excluded from the default `pytest` run (they need a browser + server).

---

## Context primer (read before Task 1)

This is a **Streamlit** dashboard (`dashboard.py` at repo root). It is a *presentation layer* over static daily report JSON in `data/` — see `[[dashboard-is-presentation-layer]]` and `docs/ux-review/BACKLOG.md`.

**Launch command** (headless, deterministic port):
```
python -m streamlit run dashboard.py --server.headless true --server.port <PORT> --browser.gatherUsageStats false
```
Boot takes ~3–6s; the log line `Uvicorn server started on 0.0.0.0:<PORT>` and then `Local URL: http://localhost:<PORT>` signal readiness of the *server* (not the rendered page — see "ready detection" below).

**The 7 pages** (`st.navigation`, real URL per page — from `dashboard.py:344-350`):
| Page | URL path | Notes |
|---|---|---|
| Briefing (default) | **`/`** | ⚠️ `/briefing` 404s (finding BR-3) — **use `/`** |
| Watchlist | `/watchlist` | click-to-expand rows (`<details>`) |
| Signal Tracker | `/signal-tracker` | large; has a by-name `<details>` ledger |
| Pipeline Stats | `/pipeline-stats` | Plotly charts |
| Scenario Log | `/scenario-log` | Plotly chart + move-log |
| Report Comparison | `/report-comparison` | select-slider + diff tables |
| Terminology | `/terminology` | static reference |

**Streamlit rendering gotchas** (these make naive screenshotting flaky — the harness must handle all of them):
1. **Content streams in progressively.** The server being up ≠ the page being rendered. The main content is inside a scroll container `section.stMain` (NOT `window`; `window.scrollY` stays 0 — scroll `document.querySelector('.stMain').scrollTop` instead). Full-page screenshots can capture *before* the below-fold content mounts.
2. **Live prices are ON by default** ("Live prices (Yahoo)" sidebar checkbox) and hit the network → non-deterministic values + timestamps. **Block all non-localhost requests** via Playwright route interception; the app then shows its static snapshot data with a `FETCH FAILED — showing snapshot` caption.
3. **First-mount one-shot animations** (`dashboard.py:75-90`) run on the first script run of a session. Disable via injected CSS + `prefers-reduced-motion`.
4. **Clock/live-derived regions** vary by wall-clock date and must be **masked**. Known/likely ones — **verify empirically** by grepping components for `date.today()`, `datetime.now(`, `Timestamp.now`, `.today(`:
   - The live-price caption (`● LIVE · HH:MM · N/N QUOTES` or `FETCH FAILED …`) — `lib/pills.py` `_render_live_caption`.
   - Any "in N days" / countdown chips in the calendar / catalyst bands (`components/briefing/calendar.py`, `catalyst_playbook.py`).
   - The masthead date is derived from the *latest report filename* (static), **not** `today()` — likely safe, but confirm.
5. **Fonts:** the app uses **system fonts** + `assets/theme.css`. System font rendering differs across OSes → the mandate to render only in the pinned Linux Docker image.

**Determinism recipe (apply to every capture):** block external network · disable animations · fixed viewport `1440×900`, `device_scale_factor=1` · wait for a stable sentinel + settle · mask the dynamic regions from (4).

---

## File Structure

- **Create** `tests/visual/__init__.py` — marks the package.
- **Create** `tests/visual/conftest.py` — session-scoped `streamlit_server` fixture (launch/teardown, returns base URL) + a `page`-configuring fixture (viewport, block network, disable animations).
- **Create** `tests/visual/harness.py` — the reusable helpers: `goto_and_settle(page, url)`, `capture(page, *, mask)`, `assert_snapshot(page, name, *, mask)` (compare-or-write baseline), and the `pixelmatch`-based comparator.
- **Create** `tests/visual/test_pages.py` — the actual page snapshot tests (parametrized over the 7 pages) + a few component-state tests.
- **Create** `tests/visual/baselines/` — committed baseline PNGs (generated in Docker). Add a `.gitattributes` entry so PNGs are treated as binary.
- **Create** `tests/visual/README.md` — how to run + how to update baselines.
- **Create** `Makefile` targets (or extend if one exists): `visual`, `visual-update`.
- **Create** `.github/workflows/visual.yml` — the CI job (uses the Docker image).
- **Modify** `pyproject.toml` — add `[tool.pytest.ini_options]` `norecursedirs`/`addopts` so the default `pytest` run **excludes** `tests/visual` (needs `-m visual` or an explicit path).

**Boundaries:** `conftest.py` owns *process + browser lifecycle*; `harness.py` owns *capture + compare* (pure, unit-testable); `test_pages.py` owns *what to snapshot*. Keep the comparator in `harness.py` so it can be unit-tested without a browser.

---

## Task 1: Dev-dependency install + a page-driving smoke test

Proves the harness can launch the app and drive a rendered page before any screenshot logic.

**Files:**
- Create: `tests/visual/__init__.py`, `tests/visual/conftest.py`, `tests/visual/test_smoke.py`
- Modify: `pyproject.toml` (pytest marker + default-exclude)

**Interfaces:**
- Produces: fixture `streamlit_server` → `str` base URL (e.g. `http://localhost:8599`); fixture `vpage` → a configured Playwright `Page` (viewport set, external network blocked, animations disabled).

- [ ] **Step 1: Install the visual-test toolchain**

Run (local, inside the repo venv is fine for driving; CI/baselines use Docker — Task 6):
```bash
pip install playwright pytest-playwright pixelmatch pillow
python -m playwright install chromium
```
Expected: `chromium` downloads; `pytest-playwright` registers a `page` fixture.

- [ ] **Step 2: Mark the package and exclude it from the default run**

Create `tests/visual/__init__.py` (empty).

Modify `pyproject.toml`, add:
```toml
[tool.pytest.ini_options]
markers = ["visual: browser+server visual-regression tests (excluded from default run)"]
addopts = "--ignore=tests/visual"
```
Rationale: `pytest -q` (the existing 229-test run) must stay browser-free and fast. Visual tests run via `pytest tests/visual` explicitly.

- [ ] **Step 3: Write the server + page fixtures**

Create `tests/visual/conftest.py`:
```python
"""Fixtures for visual-regression tests: a deterministic Streamlit server + a
network-blocked, animation-disabled Playwright page."""
from __future__ import annotations

import socket
import subprocess
import sys
import time
from urllib.request import urlopen

import pytest

_HOST = "127.0.0.1"


def _free_port() -> int:
    with socket.socket() as s:
        s.bind((_HOST, 0))
        return s.getsockname()[1]


@pytest.fixture(scope="session")
def streamlit_server() -> str:
    port = _free_port()
    proc = subprocess.Popen(
        [sys.executable, "-m", "streamlit", "run", "dashboard.py",
         "--server.headless", "true", "--server.port", str(port),
         "--server.address", _HOST, "--browser.gatherUsageStats", "false"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    base = f"http://{_HOST}:{port}"
    deadline = time.time() + 60
    while time.time() < deadline:
        try:
            urlopen(f"{base}/_stcore/health", timeout=1)  # 200 when server is up
            break
        except Exception:
            time.sleep(0.5)
    else:
        proc.terminate()
        raise RuntimeError("Streamlit did not start within 60s")
    yield base
    proc.terminate()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()


@pytest.fixture()
def vpage(page):  # `page` comes from pytest-playwright
    page.set_viewport_size({"width": 1440, "height": 900})
    # Determinism: block every non-localhost request (kills live-price fetches,
    # remote fonts, telemetry) so the app renders its static snapshot data.
    page.route(
        "**/*",
        lambda route: route.abort()
        if _HOST not in route.request.url and "localhost" not in route.request.url
        else route.continue_(),
    )
    # Determinism: kill animations + transitions everywhere.
    page.add_init_script(
        "matchMedia = (q)=>({matches:/reduce/.test(q),media:q,addListener(){},"
        "removeListener(){},addEventListener(){},removeEventListener(){},"
        "dispatchEvent(){return false}});"
    )
    page.add_style_tag(content="*{animation:none!important;transition:none!important;"
                               "caret-color:transparent!important}")
    return page
```
Note: `page.add_style_tag` runs per-navigation; if a page reload drops it, re-add in `goto_and_settle` (Task 2).

- [ ] **Step 4: Write the smoke test**

Create `tests/visual/test_smoke.py`:
```python
import pytest


@pytest.mark.visual
def test_app_boots_and_renders_masthead(streamlit_server, vpage):
    vpage.goto(f"{streamlit_server}/", wait_until="networkidle")
    vpage.wait_for_selector("text=The Market Report", timeout=30_000)
    assert "MarketReport" in vpage.title()
```

- [ ] **Step 5: Run it**

Run: `pytest tests/visual/test_smoke.py -v`
Expected: PASS (server launches, masthead renders). If it times out, the server-ready or sentinel wait needs tuning — do not proceed until this is green.

- [ ] **Step 6: Confirm the default run is unaffected**

Run: `pytest -q`
Expected: still `229 passed` (visual dir ignored via `addopts`).

- [ ] **Step 7: Commit**

```bash
git add tests/visual/__init__.py tests/visual/conftest.py tests/visual/test_smoke.py pyproject.toml
git commit -m "test(visual): scaffolding — deterministic streamlit server + page fixtures + smoke test"
```

---

## Task 2: The capture + compare harness (unit-tested comparator)

The load-bearing logic. Built comparator-first (pure, testable without a browser), then the settle/capture wrappers.

**Files:**
- Create: `tests/visual/harness.py`, `tests/visual/test_harness_unit.py`
- Create: `tests/visual/baselines/` (dir; add `.gitkeep`)

**Interfaces:**
- Produces:
  - `compare_png(actual: bytes, baseline: bytes, *, max_diff_ratio: float = 0.002) -> tuple[bool, bytes]` — returns `(ok, diff_png)`; `ok` when the fraction of differing pixels ≤ `max_diff_ratio`.
  - `goto_and_settle(page, url: str) -> None`
  - `assert_snapshot(page, name: str, *, mask: list | None = None) -> None`
- Env flag: `VISUAL_UPDATE=1` makes `assert_snapshot` (over)write the baseline instead of comparing.

- [ ] **Step 1: Write the failing comparator unit test**

Create `tests/visual/test_harness_unit.py`:
```python
import io

from PIL import Image

from tests.visual.harness import compare_png


def _png(color, size=(20, 20)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, format="PNG")
    return buf.getvalue()


def test_identical_images_match():
    a = _png((10, 20, 30))
    ok, _diff = compare_png(a, a)
    assert ok is True


def test_fully_different_images_fail():
    ok, diff = compare_png(_png((0, 0, 0)), _png((255, 255, 255)))
    assert ok is False
    assert isinstance(diff, bytes) and len(diff) > 0  # a diff image was produced


def test_tiny_difference_within_tolerance_passes():
    # One changed pixel out of 400 = 0.0025; with a 1-pixel patch it's ~0.0025,
    # above the default 0.002 -> fails; loosen tolerance and it passes.
    base = _png((10, 20, 30), (20, 20))
    img = Image.open(io.BytesIO(base)).convert("RGB")
    img.putpixel((0, 0), (200, 200, 200))
    buf = io.BytesIO(); img.save(buf, format="PNG")
    ok_strict, _ = compare_png(buf.getvalue(), base, max_diff_ratio=0.0)
    ok_loose, _ = compare_png(buf.getvalue(), base, max_diff_ratio=0.01)
    assert ok_strict is False and ok_loose is True
```

- [ ] **Step 2: Run it — expect failure**

Run: `pytest tests/visual/test_harness_unit.py -v`
Expected: FAIL (`ImportError: cannot import name 'compare_png'`).

- [ ] **Step 3: Implement `harness.py`**

Create `tests/visual/harness.py`:
```python
"""Capture + compare helpers for visual-regression tests. The comparator is
pure (no browser) so it is unit-testable; the capture wrappers own the
Streamlit-specific settling."""
from __future__ import annotations

import io
import os
from pathlib import Path

from pixelmatch.contrib.PIL import pixelmatch
from PIL import Image

BASELINE_DIR = Path(__file__).parent / "baselines"
DIFF_DIR = Path(__file__).parent / "_diffs"


def compare_png(actual: bytes, baseline: bytes, *, max_diff_ratio: float = 0.002
                ) -> tuple[bool, bytes]:
    """Anti-aliasing-aware compare. Returns (ok, diff_png_bytes)."""
    a = Image.open(io.BytesIO(actual)).convert("RGBA")
    b = Image.open(io.BytesIO(baseline)).convert("RGBA")
    if a.size != b.size:  # size mismatch is always a fail; diff = the actual
        return False, actual
    diff = Image.new("RGBA", a.size)
    # includeAA=False -> anti-aliased pixels are detected and IGNORED (not counted
    # as diffs); critical for robustness against font/subpixel noise.
    n = pixelmatch(a, b, diff, includeAA=False, threshold=0.1)
    ok = n <= max_diff_ratio * (a.size[0] * a.size[1])
    buf = io.BytesIO(); diff.save(buf, format="PNG")
    return ok, buf.getvalue()


def goto_and_settle(page, url: str) -> None:
    """Navigate and wait until Streamlit has finished its script run."""
    page.goto(url, wait_until="networkidle")
    page.wait_for_selector("text=The Market Report", timeout=30_000)
    # Streamlit shows a "Running..." status while a script runs; wait it out.
    page.wait_for_selector('[data-testid="stStatusWidget"]', state="detached",
                           timeout=30_000)
    # Re-assert animation kill (survives reruns) and let layout settle.
    page.add_style_tag(content="*{animation:none!important;transition:none!important}")
    page.wait_for_timeout(600)


def assert_snapshot(page, name: str, *, mask: list | None = None) -> None:
    """Compare a full-page screenshot against baselines/<name>.png, or write it
    when VISUAL_UPDATE=1."""
    BASELINE_DIR.mkdir(exist_ok=True)
    actual = page.screenshot(full_page=True, animations="disabled",
                             mask=mask or [], scale="css", type="png")
    baseline_path = BASELINE_DIR / f"{name}.png"
    if os.environ.get("VISUAL_UPDATE") == "1" or not baseline_path.exists():
        baseline_path.write_bytes(actual)
        return
    ok, diff = compare_png(actual, baseline_path.read_bytes())
    if not ok:
        DIFF_DIR.mkdir(exist_ok=True)
        (DIFF_DIR / f"{name}.actual.png").write_bytes(actual)
        (DIFF_DIR / f"{name}.diff.png").write_bytes(diff)
        raise AssertionError(
            f"Visual diff for '{name}'. See tests/visual/_diffs/{name}.diff.png. "
            f"If intentional, regenerate with `make visual-update`."
        )
```

- [ ] **Step 4: Run the comparator tests**

Run: `pytest tests/visual/test_harness_unit.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Add `_diffs/` to `.gitignore`; keep `baselines/`**

Append to `.gitignore`:
```
tests/visual/_diffs/
```
Create `tests/visual/baselines/.gitkeep` (empty) so the dir exists.

- [ ] **Step 6: Commit**

```bash
git add tests/visual/harness.py tests/visual/test_harness_unit.py tests/visual/baselines/.gitkeep .gitignore
git commit -m "test(visual): capture+compare harness with aa-aware pixel diff (unit-tested)"
```

---

## Task 3: Prove one page is deterministic (Briefing)

Do NOT expand coverage until the Briefing snapshot is provably stable. This task finds and masks the dynamic regions.

**Files:**
- Create: `tests/visual/test_pages.py`
- Create: baseline `tests/visual/baselines/briefing.png` (generated in Docker — Task 6 provides the command; for local iteration you may generate provisionally, but the *committed* baseline must come from Docker)

- [ ] **Step 1: Enumerate the dynamic regions**

Run: `grep -rnE "date\.today|datetime\.now|Timestamp\.now|\.now\(|strftime\(.*%" components/ lib/ | grep -vi test`
Record every element whose text depends on wall-clock time. Cross-check against the "Context primer" item 4. Build a `mask` selector list for the Briefing page (at minimum: the live-price caption; any calendar/catalyst countdown).

- [ ] **Step 2: Write the Briefing snapshot test with masks**

Create `tests/visual/test_pages.py`:
```python
import pytest

from tests.visual.harness import assert_snapshot, goto_and_settle


@pytest.mark.visual
def test_briefing_snapshot(streamlit_server, vpage):
    goto_and_settle(vpage, f"{streamlit_server}/")
    mask = [
        vpage.locator("text=/LIVE ·|FETCH FAILED/"),  # live-price caption
        # add countdown/"in N days" locators discovered in Step 1, e.g.:
        # vpage.locator(".calendar-countdown"),
    ]
    assert_snapshot(vpage, "briefing", mask=mask)
```

- [ ] **Step 3: Generate a provisional baseline and run twice**

Run:
```bash
VISUAL_UPDATE=1 pytest tests/visual/test_pages.py::test_briefing_snapshot   # writes baseline
pytest tests/visual/test_pages.py::test_briefing_snapshot -v                # compares -> should PASS
pytest tests/visual/test_pages.py::test_briefing_snapshot -v                # run again -> PASS
```
Expected: both compare runs PASS. **If they flake**, inspect `tests/visual/_diffs/briefing.diff.png` — the highlighted region reveals what's non-deterministic (usually an un-masked timestamp, a chart re-layout, or an animation). Add the region to `mask`, or increase settle time, until 3 consecutive runs are clean. This is the crux of the whole harness.

- [ ] **Step 4: Stability under a different system date**

Temporarily set the system date forward (or run inside Docker with `-e TZ` / `date`), regenerate is NOT needed — just re-run the compare. It must still PASS (proves the masks cover all clock-derived text). If it fails, extend the mask list.

- [ ] **Step 5: Commit the test (baseline comes from Docker in Task 6)**

```bash
git add tests/visual/test_pages.py
git commit -m "test(visual): briefing page snapshot + dynamic-region masks (proven stable)"
```

---

## Task 4: All 7 pages

**Files:** Modify `tests/visual/test_pages.py`

- [ ] **Step 1: Parametrize over the pages**

Replace the single Briefing test with (keep the Briefing masks; add per-page masks as discovered):
```python
import pytest

from tests.visual.harness import assert_snapshot, goto_and_settle

PAGES = [
    ("briefing", "/"),
    ("watchlist", "/watchlist"),
    ("signal-tracker", "/signal-tracker"),
    ("pipeline-stats", "/pipeline-stats"),
    ("scenario-log", "/scenario-log"),
    ("report-comparison", "/report-comparison"),
    ("terminology", "/terminology"),
]


@pytest.mark.visual
@pytest.mark.parametrize("name,path", PAGES, ids=[p[0] for p in PAGES])
def test_page_snapshot(streamlit_server, vpage, name, path):
    goto_and_settle(vpage, f"{streamlit_server}{path}")
    mask = [vpage.locator("text=/LIVE ·|FETCH FAILED/")]  # extend per page
    assert_snapshot(vpage, name, mask=mask)
```

- [ ] **Step 2: Generate baselines + verify twice**

Run:
```bash
VISUAL_UPDATE=1 pytest tests/visual/test_pages.py
pytest tests/visual/test_pages.py -v   # PASS
pytest tests/visual/test_pages.py -v   # PASS again
```
Expected: 7 passing. Chart pages (`pipeline-stats`, `scenario-log`) are the highest flake risk (Plotly async render) — if they flake, increase settle or mask the plot area and rely on the surrounding chrome. Note any masked plots as a known coverage gap in `tests/visual/README.md`.

- [ ] **Step 3: Commit the tests** (baselines regenerated in Docker at Task 6)

```bash
git add tests/visual/test_pages.py
git commit -m "test(visual): snapshot all 7 pages"
```

---

## Task 5: Key interactive component states

Snapshots of states that only exist after interaction — where real display bugs hid (the watchlist drilldown, the tracker ledger).

**Files:** Create `tests/visual/test_states.py`

- [ ] **Step 1: Write the state tests**

Create `tests/visual/test_states.py`:
```python
import pytest

from tests.visual.harness import assert_snapshot, goto_and_settle


@pytest.mark.visual
def test_watchlist_nvda_drilldown(streamlit_server, vpage):
    goto_and_settle(vpage, f"{streamlit_server}/watchlist")
    vpage.get_by_text("NVDA", exact=False).first.click()  # expand the row
    vpage.wait_for_timeout(600)
    assert_snapshot(vpage, "watchlist-nvda-drilldown",
                    mask=[vpage.locator("text=/LIVE ·|FETCH FAILED/")])


@pytest.mark.visual
def test_signal_tracker_by_name_table(streamlit_server, vpage):
    goto_and_settle(vpage, f"{streamlit_server}/signal-tracker")
    vpage.locator(".tk-scroll").scroll_into_view_if_needed()
    vpage.wait_for_timeout(400)
    assert_snapshot(vpage, "signal-tracker-ledger")
```

- [ ] **Step 2: Generate + verify twice; Step 3: commit**

```bash
VISUAL_UPDATE=1 pytest tests/visual/test_states.py
pytest tests/visual/test_states.py -v   # twice, both PASS
git add tests/visual/test_states.py
git commit -m "test(visual): drilldown + tracker-ledger interactive states"
```

---

## Task 6: Canonical baselines + CI job (the source of truth)

Everything above used *provisional* local baselines. Now generate the **committed** baselines in the pinned Docker image and wire CI to compare in that same image.

**Files:** Create `Makefile`, `.github/workflows/visual.yml`, `tests/visual/README.md`, `tests/visual/baselines/*.png`

- [ ] **Step 1: Add Make targets**

Create/extend `Makefile` (choose a Playwright Python image tag matching your installed `playwright` version — check `pip show playwright`; e.g. `v1.49.0-jammy`):
```makefile
PW_IMAGE ?= mcr.microsoft.com/playwright/python:v1.49.0-jammy
DOCKER_RUN = docker run --rm -v "$(PWD)":/work -w /work $(PW_IMAGE) bash -lc

visual:  ## compare against committed baselines (canonical, Linux)
	$(DOCKER_RUN) "pip install -q -r requirements.lock playwright pytest-playwright pixelmatch pillow && python -m playwright install chromium && pytest tests/visual -q"

visual-update:  ## regenerate committed baselines (run after an intentional UI change)
	$(DOCKER_RUN) "pip install -q -r requirements.lock playwright pytest-playwright pixelmatch pillow && python -m playwright install chromium && VISUAL_UPDATE=1 pytest tests/visual -q"
```

- [ ] **Step 2: Generate the canonical baselines and commit them**

Run:
```bash
make visual-update      # writes Linux-rendered baselines into tests/visual/baselines/
make visual             # verify they compare clean in-image
git add tests/visual/baselines/*.png
git commit -m "test(visual): canonical Linux baselines (generated in playwright docker image)"
```
Expected: `make visual` reports all visual tests passing. These PNGs are the committed source of truth.

- [ ] **Step 3: Add the CI job**

Create `.github/workflows/visual.yml`:
```yaml
name: Visual

on:
  pull_request:
  push:
    branches: [main]

jobs:
  visual:
    runs-on: ubuntu-latest
    container:
      image: mcr.microsoft.com/playwright/python:v1.49.0-jammy
    steps:
      - uses: actions/checkout@v4
      - run: pip install -r requirements.lock playwright pytest-playwright pixelmatch pillow
      - run: python -m playwright install chromium
      - run: pytest tests/visual -q
      - if: failure()
        uses: actions/upload-artifact@v4
        with:
          name: visual-diffs
          path: tests/visual/_diffs/
```
Keep the image tag identical to the Makefile's `PW_IMAGE` so local `make visual` and CI render identically.

- [ ] **Step 4: Write the README**

Create `tests/visual/README.md`:
```markdown
# Visual regression tests

Screenshots every page/state and pixel-diffs against committed baselines, all in
the pinned Playwright Docker image so rendering is identical in CI and locally.

## Run (compare)
    make visual

## Update baselines (after an INTENTIONAL UI change)
    make visual-update
    git add tests/visual/baselines/*.png && git commit -m "test(visual): update baselines for <change>"

## Rules
- **Never** commit baselines generated outside the Docker image (font rendering differs).
- A failing run uploads diff images (CI: `visual-diffs` artifact; local: `tests/visual/_diffs/`).
- Masked/known-flaky regions (live caption, some charts) are listed in `test_pages.py`.
```

- [ ] **Step 5: Push and confirm CI is green**

```bash
git add Makefile .github/workflows/visual.yml tests/visual/README.md
git commit -m "ci(visual): run visual regression in playwright docker image, upload diffs on fail"
git push
```
Expected: the new **Visual** workflow runs and passes on the PR/branch. If it fails on first run, download the `visual-diffs` artifact — a real cross-environment render delta means the local `make visual-update` was not run in the identical image tag; reconcile the tag and regenerate.

---

## Verification checklist (run before declaring done)

- [ ] `pytest -q` still reports the original suite green (visual dir excluded).
- [ ] `make visual` passes locally (all pages + states, in Docker).
- [ ] The **Visual** CI job is green on a PR.
- [ ] Intentional-change loop works: tweak a colour in a component, `make visual` FAILS with a readable diff, `make visual-update` + commit makes it green.
- [ ] A deliberately-introduced regression (e.g. re-break BR-1's tag truncation on a scratch branch) is CAUGHT by `make visual`. This is the whole point — confirm it.

## Open decisions (safe defaults chosen; flag if you disagree)

1. **Python + Docker (chosen)** vs the JS Playwright test runner. JS `toHaveScreenshot` has richer built-in masking/reporting, but adds a Node toolchain to a Python repo. The plan stays single-language; revisit only if masking becomes unmanageable.
2. **Mask clock-derived regions (chosen)** vs freezing the app's clock via a `TEST_DATE` env override (a small `dashboard.py`/`masthead.py` change) for stricter coverage. Start with masking; add the freeze if masks proliferate.
3. **`max_diff_ratio=0.002` default** — tune per-page if aa noise causes false positives; keep as low as stays stable.
4. **Charts:** if Plotly proves irreducibly flaky, mask the plot canvas and rely on surrounding chrome; record it as a coverage gap rather than accepting flake.
