import io

import pytest
from PIL import Image

from tests.visual import harness
from tests.visual.harness import compare_png


def _png(color, size=(20, 20)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, format="PNG")
    return buf.getvalue()


class _StubPage:
    """Minimal browser-free stand-in: assert_snapshot only ever calls
    .screenshot(...), so that is all we implement."""

    def __init__(self, png: bytes):
        self._png = png

    def screenshot(self, **kwargs) -> bytes:
        return self._png


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
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    ok_strict, _ = compare_png(buf.getvalue(), base, max_diff_ratio=0.0)
    ok_loose, _ = compare_png(buf.getvalue(), base, max_diff_ratio=0.01)
    assert ok_strict is False and ok_loose is True


def test_small_height_jitter_within_tolerance_passes():
    """±2 rows of page-tail jitter (grow-until-stable wobble) must not fail a
    pixel-identical page: gap rows spend the normal diff budget instead of
    tripping a hard size gate. 2 rows / 1502 = 0.0013 < 0.002."""
    ok, _ = compare_png(_png((10, 20, 30), (10, 1502)), _png((10, 20, 30), (10, 1500)))
    assert ok is True


def test_large_height_gap_fails():
    """A real added band blows the same budget: 20 rows / 120 = 0.167."""
    ok, _ = compare_png(_png((10, 20, 30), (10, 120)), _png((10, 20, 30), (10, 100)))
    assert ok is False


def test_width_mismatch_always_fails():
    """The viewport width is pinned, so a width change is a real layout change —
    no tolerance applies."""
    ok, _ = compare_png(_png((10, 20, 30), (12, 100)), _png((10, 20, 30), (10, 100)),
                        max_diff_ratio=0.5)
    assert ok is False


def test_visual_update_skips_rewriting_within_tolerance_baseline(tmp_path,
                                                                 monkeypatch):
    """VISUAL_UPDATE=1 must NOT rewrite a baseline the capture still matches:
    within-tolerance rewrites churn binary jitter into commits that then diff
    against CI."""
    monkeypatch.setenv("VISUAL_UPDATE", "1")
    baselines = tmp_path / "baselines"
    baselines.mkdir()
    monkeypatch.setattr(harness, "BASELINE_DIR", baselines)
    monkeypatch.setattr(harness, "DIFF_DIR", tmp_path / "_diffs")
    old = _png((10, 20, 30), (10, 1500))
    (baselines / "steady.png").write_bytes(old)
    page = _StubPage(_png((10, 20, 30), (10, 1502)))  # 2-row jitter only

    harness.assert_snapshot(page, "steady")

    assert (baselines / "steady.png").read_bytes() == old  # untouched


def test_visual_update_rewrites_changed_baseline(tmp_path, monkeypatch):
    """VISUAL_UPDATE=1 still rewrites when the capture genuinely changed."""
    monkeypatch.setenv("VISUAL_UPDATE", "1")
    baselines = tmp_path / "baselines"
    baselines.mkdir()
    monkeypatch.setattr(harness, "BASELINE_DIR", baselines)
    monkeypatch.setattr(harness, "DIFF_DIR", tmp_path / "_diffs")
    (baselines / "changed.png").write_bytes(_png((0, 0, 0)))
    new = _png((255, 255, 255))
    page = _StubPage(new)

    harness.assert_snapshot(page, "changed")

    assert (baselines / "changed.png").read_bytes() == new


def test_missing_baseline_in_compare_mode_raises_and_writes_nothing(tmp_path,
                                                                    monkeypatch):
    """Compare mode (VISUAL_UPDATE unset) + missing baseline must FAIL LOUD and
    must NOT auto-create the baseline (silent write-and-pass tests nothing)."""
    monkeypatch.delenv("VISUAL_UPDATE", raising=False)
    monkeypatch.setattr(harness, "BASELINE_DIR", tmp_path / "baselines")
    monkeypatch.setattr(harness, "DIFF_DIR", tmp_path / "_diffs")
    page = _StubPage(_png((10, 20, 30)))

    with pytest.raises(AssertionError, match="missing"):
        harness.assert_snapshot(page, "never_committed")

    assert not (tmp_path / "baselines" / "never_committed.png").exists()


def test_missing_baseline_with_visual_update_writes_and_returns_none(tmp_path,
                                                                     monkeypatch):
    """VISUAL_UPDATE=1 + missing baseline writes the snapshot and returns None."""
    monkeypatch.setenv("VISUAL_UPDATE", "1")
    monkeypatch.setattr(harness, "BASELINE_DIR", tmp_path / "baselines")
    monkeypatch.setattr(harness, "DIFF_DIR", tmp_path / "_diffs")
    png = _png((10, 20, 30))
    page = _StubPage(png)

    result = harness.assert_snapshot(page, "fresh")

    assert result is None
    written = tmp_path / "baselines" / "fresh.png"
    assert written.exists() and written.read_bytes() == png


def test_existing_matching_baseline_passes(tmp_path, monkeypatch):
    """Compare mode + an existing identical baseline compares clean (returns
    None, no raise) — the unchanged happy path."""
    monkeypatch.delenv("VISUAL_UPDATE", raising=False)
    baselines = tmp_path / "baselines"
    baselines.mkdir()
    monkeypatch.setattr(harness, "BASELINE_DIR", baselines)
    monkeypatch.setattr(harness, "DIFF_DIR", tmp_path / "_diffs")
    png = _png((10, 20, 30))
    (baselines / "match.png").write_bytes(png)
    page = _StubPage(png)

    assert harness.assert_snapshot(page, "match") is None
