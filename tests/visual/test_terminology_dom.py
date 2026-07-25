"""Live-DOM assertions for the Terminology page (spec 2026-07-25 §4).

Not snapshots — these check three things a screenshot cannot, and that the
design would silently lose if the host disagreed with it:

  1. ``id`` attributes survive Streamlit's HTML sanitizer, so the index rail's
     ``href="#id"`` anchors have somewhere to land.
  2. The inline ``--label-w`` custom property reaches the grid, so a section's
     fixed label column is the width the content asked for and not the 132px
     fallback.
  3. ``position: sticky`` on the rail is not defeated by an ``overflow`` on some
     Streamlit ancestor — the rail is the page's whole finding story.

Plus the focus ring, because the framework's default primary is amber and amber
is WATCH: no signal hue may appear on a form control.

Selectors here are verified against the live DOM rather than guessed — the
``details[data-testid="stExpander"]`` selector that matched nothing for a whole
release is the reason that is a rule.
"""
import pytest

from tests.visual.harness import SETTLE_TIMEOUT_MS

EXPECTED_SECTIONS = 12


def _settle(page, url: str) -> None:
    """goto_and_settle without the viewport grow — these tests need a real
    viewport with real scrolling, which growing to full content removes."""
    page.goto(url, wait_until="networkidle")
    page.wait_for_selector("text=The Market Report", timeout=SETTLE_TIMEOUT_MS)
    page.wait_for_selector('[data-testid="stStatusWidget"]', state="detached",
                           timeout=SETTLE_TIMEOUT_MS)
    page.wait_for_selector(".term-layout", timeout=SETTLE_TIMEOUT_MS)


@pytest.mark.visual
def test_section_ids_and_index_anchors_survive_sanitization(streamlit_server, vpage):
    _settle(vpage, f"{streamlit_server}/terminology")

    got = vpage.evaluate("""() => {
      const secs = [...document.querySelectorAll('.term-section')].map(s => s.id);
      const links = [...document.querySelectorAll('a.term-index-item')]
        .map(a => a.getAttribute('href'));
      return {secs, links};
    }""")
    assert len(got["secs"]) == EXPECTED_SECTIONS
    assert all(got["secs"]), f"a section lost its id to the sanitizer: {got['secs']}"
    assert [f"#{sid}" for sid in got["secs"]] == got["links"], \
        "index anchors do not line up with the sections they target"


@pytest.mark.visual
def test_inline_label_width_custom_property_reaches_the_grid(streamlit_server, vpage):
    """R:R's term list asks for a 172px label column; if the sanitizer dropped
    the inline custom property every grid would silently fall back to 132px."""
    _settle(vpage, f"{streamlit_server}/terminology")

    cols = vpage.evaluate("""() => {
      const row = document.querySelector('#rr .term-grid[style*="172px"] .term-row');
      return row ? getComputedStyle(row).gridTemplateColumns : null;
    }""")
    assert cols, "no 172px grid found in the R:R section — inline style stripped?"
    assert cols.split()[0].startswith("172"), f"label column resolved to {cols}"


@pytest.mark.visual
def test_index_rail_actually_sticks(streamlit_server, vpage):
    _settle(vpage, f"{streamlit_server}/terminology")

    got = vpage.evaluate("""() => {
      const rail = document.querySelector('.term-index');
      let el = rail.parentElement, scroller = null;
      while (el && el !== document.documentElement) {
        const s = getComputedStyle(el);
        if (/(auto|scroll)/.test(s.overflowY) && el.scrollHeight > el.clientHeight + 10) {
          scroller = el; break;
        }
        el = el.parentElement;
      }
      const target = scroller || document.scrollingElement;
      const before = rail.getBoundingClientRect().top;
      target.scrollTop = 1400;
      const after = rail.getBoundingClientRect().top;
      return {position: getComputedStyle(rail).position, before, after,
              scrolled: target.scrollTop};
    }""")
    assert got["position"] == "sticky"
    assert got["scrolled"] > 600, "nothing scrolled — the probe found no scroller"
    # The rail starts below the masthead and search, then rises to its 20px
    # offset and pins there. A rail whose ancestor has an overflow that defeats
    # sticky travels with the content instead, so its top goes far negative.
    assert got["after"] >= 0, (
        f"rail scrolled off the top (top {got['before']} → {got['after']}); "
        "an ancestor overflow is defeating position:sticky"
    )
    assert got["after"] < 60, (
        f"rail is pinned at {got['after']}px, not its 20px sticky offset"
    )


@pytest.mark.visual
def test_formula_plates_render_as_blocks(streamlit_server, vpage):
    """A snapshot cannot catch this one — it would simply freeze the broken
    render as the baseline. Streamlit overrides the `pre` component for syntax
    highlighting, so a raw <pre> arrives with no class and its newlines
    collapsed, and the formula reads as a run-on italic sentence. The plates are
    <div>s for that reason; this asserts they stayed blocks with real monospace,
    preserved line breaks, and non-italic brass variables.
    """
    _settle(vpage, f"{streamlit_server}/terminology")

    got = vpage.evaluate("""() => {
      const p = document.querySelector('#rr .term-plate');
      if (!p) return null;
      const cs = getComputedStyle(p);
      const v = p.querySelector('var');
      const vs = v ? getComputedStyle(v) : null;
      return {
        count: document.querySelectorAll('.term-plate').length,
        whiteSpace: cs.whiteSpace,
        font: cs.fontFamily.toLowerCase(),
        height: p.getBoundingClientRect().height,
        lineHeight: parseFloat(cs.lineHeight),
        varStyle: vs && vs.fontStyle,
      };
    }""")
    assert got, "no .term-plate in the R:R section — the class was stripped"
    assert got["count"] == 5, f"expected 5 plates page-wide, saw {got['count']}"
    assert got["whiteSpace"].startswith("pre"), got["whiteSpace"]
    assert "mono" in got["font"] or "consolas" in got["font"], got["font"]
    # Two formula lines plus padding: a collapsed plate is one line tall.
    assert got["height"] > got["lineHeight"] * 1.8, (
        f"plate is {got['height']}px — its newline collapsed"
    )
    assert got["varStyle"] == "normal", "variables kept the browser's italic <var>"


@pytest.mark.visual
def test_index_rail_is_chrome_not_a_list_of_links(streamlit_server, vpage):
    """Underlined anchors make the rail read as content. Streamlit underlines
    every markdown-container link, so this is a real override being asserted."""
    _settle(vpage, f"{streamlit_server}/terminology")

    deco = vpage.evaluate(
        "() => getComputedStyle(document.querySelector('a.term-index-item'))"
        ".textDecorationLine"
    )
    assert deco == "none", f"index items are decorated: {deco}"


@pytest.mark.visual
def test_search_focus_ring_is_steel_not_a_signal_hue(streamlit_server, vpage):
    """Selection and search are structure, so they take the accent. Amber here
    would read as WATCH on a control that rates nothing."""
    _settle(vpage, f"{streamlit_server}/terminology")

    vpage.locator(".st-key-term_search input").focus()
    ring = vpage.evaluate("""() => {
      const wrap = document.querySelector('.st-key-term_search div[data-baseweb="input"]');
      const cs = getComputedStyle(wrap);
      const accent = getComputedStyle(document.documentElement)
        .getPropertyValue('--accent').trim();
      return {outline: cs.outlineColor, width: cs.outlineWidth, accent};
    }""")
    assert ring["width"] != "0px", "the search box has no visible focus ring"
    # --accent is a hex token; compare through a canvas-free channel by asking
    # the browser to resolve both to rgb().
    resolved = vpage.evaluate(
        "(hex) => { const d = document.createElement('div'); d.style.color = hex;"
        " document.body.appendChild(d);"
        " const c = getComputedStyle(d).color; d.remove(); return c; }",
        ring["accent"],
    )
    assert ring["outline"] == resolved, \
        f"focus ring {ring['outline']} is not the accent {resolved}"
