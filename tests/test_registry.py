import io
from PIL import Image

from openconverter.core.registry import build_default_registry


def test_registry_has_pillow():
    reg = build_default_registry()
    assert any(a.id == "pillow" for a in reg.adapters())


def test_detect_png():
    reg = build_default_registry()
    buf = io.BytesIO()
    Image.new("RGB", (4, 4), "red").save(buf, format="PNG")
    adapter = reg.detect(buf.getvalue())
    assert adapter is not None
    assert adapter.id == "pillow"


def test_supported_extensions():
    reg = build_default_registry()
    exts = reg.supported_extensions()
    assert ".png" in exts
    assert ".jpg" in exts or ".jpeg" in exts
