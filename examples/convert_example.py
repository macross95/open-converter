"""Example: convert a folder of images to WebP."""
import os
from openconverter.core.converter import Converter

conv = Converter()
src_dir = "input"
out_dir = "output"
os.makedirs(out_dir, exist_ok=True)
for name in os.listdir(src_dir):
    if name.lower().endswith((".png", ".jpg", ".jpeg", ".tif", ".bmp")):
        src = os.path.join(src_dir, name)
        dst = os.path.join(out_dir, os.path.splitext(name)[0] + ".webp")
        try:
            r = conv.convert(src, dst, format="webp", quality=85, metadata="strip",
                            transforms=[{"resize": {"width": 2048, "fit": "inside"}}])
            print("OK", name, r["size"])
        except Exception as e:
            print("FAIL", name, e)
