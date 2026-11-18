"""SVG adapter (optional dependency: cairosvg)."""

from typing import Any, Dict, Optional

try:
    import cairosvg
    _AVAILABLE = True
except Exception:
    _AVAILABLE = False

from ..adapters.base import FormatAdapter, FormatCapabilities
from ..core.document import Frame, ImageDocument
from ..core.exceptions import DecodeError, EncodeError, UnsupportedFormatError
from ..core.metadata import read_metadata


class SvgAdapter(FormatAdapter):
    id = "svg"
    extensions = [".svg"]
    mime_types = ["image/svg+xml"]
    capabilities = FormatCapabilities(lossless=True, alpha=True, animation=False, metadata_read=True, metadata_write=False)

    def __init__(self):
        if not _AVAILABLE:
            raise UnsupportedFormatError("cairosvg not installed")

    def can_decode(self, data: bytes) -> bool:
        if not _AVAILABLE:
            return False
        try:
            return b"<svg" in data.lower()
        except Exception:
            return False

    def decode(self, data: bytes, options: Optional[Dict[str, Any]] = None) -> ImageDocument:
        if not _AVAILABLE:
            raise UnsupportedFormatError("cairosvg not installed")
        options = options or {}
        width = options.get("width")
        height = options.get("height")
        try:
            png_bytes = cairosvg.svg2png(bytestring=data, output_width=width, output_height=height)
        except Exception as e:
            raise DecodeError(f"SVG decode failed: {e}") from e
        from PIL import Image
        import io
        img = Image.open(io.BytesIO(png_bytes))
        img.load()
        doc = ImageDocument(frames=[Frame(width=img.width, height=img.height, mode=img.mode, data=img)], metadata=read_metadata(img), source_format="svg")
        return doc

    def encode(self, document, options=None):
        raise EncodeError("SVG is decode-only; rasterize to another format")
