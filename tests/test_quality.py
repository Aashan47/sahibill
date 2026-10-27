"""The retake gate (sahibill/readers/quality.py): free, local, threshold frozen on the calibration half."""
import io

import pytest
from PIL import Image, ImageDraw, ImageFilter

from sahibill.readers import quality


def _bill_like(w=1600, h=2200) -> Image.Image:
    """Dark printed lines and digits on paper, roughly like a bill's ruled table."""
    im = Image.new("RGB", (w, h), (238, 240, 236))
    d = ImageDraw.Draw(im)
    for y in range(80, h - 80, 46):
        d.line([(60, y), (w - 60, y)], fill=(60, 64, 120), width=2)
        for x in range(80, w - 200, 170):
            d.text((x, y + 12), "1234.56", fill=(20, 24, 40))
    return im


def _damaged(im: Image.Image) -> Image.Image:
    return im.resize((im.width * 6 // 10, im.height * 6 // 10), Image.BILINEAR).filter(ImageFilter.GaussianBlur(4))


def test_threshold_is_the_frozen_value():
    assert quality.THRESHOLD == 3.0 and quality.LONG_SIDE == 1200


def test_sharp_photo_passes_and_damaged_photo_is_refused():
    sharp = _bill_like()
    ok, bad = quality.check(sharp), quality.check(_damaged(sharp))
    assert ok["ok"] and ok["reason"] is None
    assert not bad["ok"] and bad["reason"] and bad["sharpness"] < ok["sharpness"]


def test_accepts_bytes_and_is_scale_free_for_a_sharp_photo():
    buf = io.BytesIO()
    _bill_like().save(buf, "PNG")
    a = quality.check(buf.getvalue())
    b = quality.check(_bill_like(3200, 4400))      # a bigger phone photo of the same page
    assert a["ok"] and b["ok"]


def test_more_contrast_does_not_pass_a_blurred_photo():
    from PIL import ImageEnhance
    assert not quality.check(ImageEnhance.Contrast(_damaged(_bill_like())).enhance(2.5))["ok"]


@pytest.mark.xfail(strict=True, reason="known weakness (results/E2-RETAKE-GATE.md): on a washed-out photo, 8-bit "
                   "rounding noise divided by the small contrast inflates the score, so a blurred, faded photo can pass")
def test_a_washed_out_blurred_photo_is_refused():
    from PIL import ImageEnhance
    assert not quality.check(ImageEnhance.Contrast(_damaged(_bill_like())).enhance(0.5))["ok"]


def test_retake_text_in_both_languages():
    assert set(quality.RETAKE) == {"en", "ur"} and all(quality.RETAKE.values())
    assert "\u2014" not in quality.RETAKE["en"] + quality.RETAKE["ur"]
