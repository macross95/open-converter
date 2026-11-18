from PIL import Image

from openconverter.core.document import Frame, ImageDocument
from openconverter.core.pipeline import apply_transforms


def make_doc():
    img = Image.new("RGB", (100, 80), "blue")
    return ImageDocument(frames=[Frame(width=100, height=80, mode="RGB", data=img)])


def test_resize_inside():
    doc = make_doc()
    apply_transforms(doc, [{"resize": {"width": 50, "height": 50, "fit": "inside"}}])
    f = doc.primary
    assert f.width <= 50 and f.height <= 50


def test_rotate():
    doc = make_doc()
    apply_transforms(doc, [{"rotate": {"angle": 90, "expand": True}}])
    f = doc.primary
    assert f.width == 80 and f.height == 100


def test_grayscale():
    doc = make_doc()
    apply_transforms(doc, [{"grayscale": {}}])
    assert doc.primary.mode == "L"


def test_crop():
    doc = make_doc()
    apply_transforms(doc, [{"crop": {"left": 10, "top": 10, "width": 30, "height": 20}}])
    f = doc.primary
    assert f.width == 30 and f.height == 20
