"""Fixtures for visual-regression tests: a deterministic Streamlit server + a
network-blocked, animation-disabled Playwright page."""
from __future__ import annotations

import os
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


# Determinism: the `vpage` fixture blocks the *browser's* non-localhost requests,
# but the live-price quote fetch (live_prices.fetch_live_quotes → Yahoo) runs in
# THIS Streamlit *server* process, which Playwright cannot intercept — so without
# this the pulse strip renders live, per-second-changing market prices and the
# snapshot flakes. Point outbound HTTP(S) at a dead port so every Yahoo fetch
# fails fast; the app falls back to its frozen report-JSON snapshot (the caption
# reads "FETCH FAILED — showing snapshot"). NO_PROXY keeps the server's own
# localhost socket + health check direct. This finishes the job the vpage
# network-block comment set out to do ("kills live-price fetches so the app
# renders its static snapshot data").
_DETERMINISTIC_ENV = {
    **os.environ,
    "HTTP_PROXY": "http://127.0.0.1:9",
    "HTTPS_PROXY": "http://127.0.0.1:9",
    "http_proxy": "http://127.0.0.1:9",
    "https_proxy": "http://127.0.0.1:9",
    "NO_PROXY": "127.0.0.1,localhost",
    "no_proxy": "127.0.0.1,localhost",
}


@pytest.fixture(scope="session")
def streamlit_server() -> str:
    port = _free_port()
    proc = subprocess.Popen(
        [sys.executable, "-m", "streamlit", "run", "dashboard.py",
         "--server.headless", "true", "--server.port", str(port),
         "--server.address", _HOST, "--browser.gatherUsageStats", "false"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        env=_DETERMINISTIC_ENV,
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
