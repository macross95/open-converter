"""RAW camera adapter (optional dependency: rawpy)."""

from typing import Any, Dict, Optional

try:
    import rawpy
    _AVAILABLE = True
except Exception:
    _AVAILABLE = False

from ..adapters.base import FormatAdapter, FormatCapabilities
from ..core.document import Frame, ImageDocument
from ..core.exceptions import DecodeError, EncodeError, UnsupportedFormatError
from ..core.metadata import read_metadata


class RawAdapter(FormatAdapter):
    id = "raw"
    extensions = [".dng", ".cr2", ".cr3", ".nef", ".arw", ".raf", ".orf", ".rw2"]
    mime_types = ["image/x-adobe-dng", "image/x-canon-cr2"]
    capabilities = FormatCapabilities(lossless=True, alpha=False, animation=False, metadata_read=True, metadata_write=False)

    def __init__(self):
        if not _AVAILABLE:
            raise UnsupportedFormatError("rawpy not installed")

    def can_decode(self, data: bytes) -> bool:
        if not _AVAILABLE:
            return False
        # crude: try rawpy
        import io
        try:
            raw = rawpy.imread(io.BytesIO(data)) if hasattr(rawpy, "imread") else None
            return raw is not None
        except Exception:
            return False

    def decode(self, data: bytes, options: Optional[Dict[str, Any]] = None) -> ImageDocument:
        if not _AVAILABLE:
            raise UnsupportedFormatError("rawpy not installed")
        import io
        try:
            raw = rawpy.imread(io.BytesIO(data))
            rgb = raw.postprocess()
        except Exception as e:
            raise DecodeError(f"RAW decode failed: {e}") from e
        from PIL import Image
        img = Image.fromarray(rgb)
        doc = ImageDocument(frames=[Frame(width=img.width, height=img.height, mode=img.mode, data=img)], metadata=read_metadata(img), source_format="raw")
        return doc

    def encode(self, document, options=None):
        raise EncodeError("RAW is decode-only; encode to another format")
