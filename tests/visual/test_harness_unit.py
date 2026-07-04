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
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    ok_strict, _ = compare_png(buf.getvalue(), base, max_diff_ratio=0.0)
    ok_loose, _ = compare_png(buf.getvalue(), base, max_diff_ratio=0.01)
    assert ok_strict is False and ok_loose is True
