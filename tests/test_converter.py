import os
import tempfile

from PIL import Image

from openconverter.core.converter import Converter


def test_convert_png_to_jpeg():
    with tempfile.TemporaryDirectory() as d:
        src = os.path.join(d, "a.png")
        dst = os.path.join(d, "a.jpg")
        Image.new("RGB", (64, 48), "green").save(src, format="PNG")
        conv = Converter()
        res = conv.convert(src, dst, format="jpeg", quality=80)
        assert os.path.exists(dst)
        assert res["size"] > 0
        # verify readable
        with Image.open(dst) as img:
            assert img.size == (64, 48)


def test_info():
    with tempfile.TemporaryDirectory() as d:
        src = os.path.join(d, "b.png")
        Image.new("RGB", (10, 10), "red").save(src, format="PNG")
        conv = Converter()
        info = conv.info(src)
        assert info["width"] == 10
        assert info["height"] == 10
        assert info["format"] == "png"
