# ─────────────────────────────────────────────────────────────────────────────
# Visual-regression harness — canonical Unix/CI entrypoint.
#
# Rendering (fonts, anti-aliasing, Plotly canvases) must be BYTE-STABLE across
# machines, so both `visual` and `visual-update` run inside the pinned Playwright
# image whose bundled chromium matches the pip-pinned playwright==1.60.0.
# Committing a baseline generated anywhere else (a Windows/mac host, a different
# image tag) will diff against CI — never do it.
#
# NOTE: `make` is not installed on the Windows dev host. Locally, run the same
# `docker run …` invocation by hand (see tests/visual/README.md); this Makefile
# stays the canonical entrypoint for Unix and CI.
# ─────────────────────────────────────────────────────────────────────────────

# Keep this tag IDENTICAL to .github/workflows/visual.yml so local and CI render
# pixel-for-pixel the same.
PW_IMAGE ?= mcr.microsoft.com/playwright/python:v1.60.0-jammy

DOCKER_RUN = docker run --rm -v "$(PWD)":/work -w /work $(PW_IMAGE) bash -lc

# requirements.lock = the app runtime (streamlit, pandas, plotly …) the harness
# boots as a subprocess. playwright is PINNED to 1.60.0 so the pip package can
# never drift away from the image's bundled chromium; pytest-playwright /
# pixelmatch / pillow are the harness's own deps.
PW_PIP = pip install -q -r requirements.lock playwright==1.60.0 pytest-playwright pixelmatch pillow && python -m playwright install chromium

# Always `python -m pytest` (module form): it puts the repo root on sys.path so
# the suite's `lib.*` / `tests.visual.*` imports resolve — bare `pytest` fails
# collection with ModuleNotFoundError. TEST_DATE is deliberately NOT set here:
# tests/visual/conftest.py injects TEST_DATE=2026-07-04 into the Streamlit server
# subprocess itself, so the frozen clock is inherited automatically.

.PHONY: visual visual-update

visual:  ## compare rendered pages against committed baselines (canonical, Linux)
	$(DOCKER_RUN) "$(PW_PIP) && python -m pytest tests/visual -q"

visual-update:  ## regenerate committed baselines — run ONLY after an intentional UI change
	$(DOCKER_RUN) "$(PW_PIP) && VISUAL_UPDATE=1 python -m pytest tests/visual -q"
