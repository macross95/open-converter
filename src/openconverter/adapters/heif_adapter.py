"""HEIC/HEIF adapter (optional dependency: pillow-heif)."""

from typing import Any, Dict, Optional

try:
    import pillow_heif
    pillow_heif.register_heif_opener()
    _AVAILABLE = True
except Exception:
    _AVAILABLE = False

from ..adapters.base import FormatAdapter, FormatCapabilities
from ..core.document import ImageDocument
from ..core.exceptions import DecodeError, EncodeError, UnsupportedFormatError


class HeifAdapter(FormatAdapter):
    id = "heif"
    extensions = [".heic", ".heif"]
    mime_types = ["image/heic", "image/heif"]
    capabilities = FormatCapabilities(lossless=False, alpha=True, animation=False, metadata_read=True, metadata_write=True)

    def __init__(self):
        if not _AVAILABLE:
            raise UnsupportedFormatError("pillow-heif not installed")

    def can_decode(self, data: bytes) -> bool:
        if not _AVAILABLE:
            return False
        try:
            from PIL import Image
            import io
            img = Image.open(io.BytesIO(data))
            return (img.format or "").upper() in ("HEIF", "HEIC")
        except Exception:
            return False

    def decode(self, data: bytes, options: Optional[Dict[str, Any]] = None) -> ImageDocument:
        if not _AVAILABLE:
            raise UnsupportedFormatError("pillow-heif not installed")
        # Delegate to pillow with heif registered
        from PIL import Image
        import io
        try:
            img = Image.open(io.BytesIO(data))
            img.load()
        except Exception as e:
            raise DecodeError(f"HEIF decode failed: {e}") from e
        from ..core.document import Frame
        from ..core.metadata import read_metadata
        frame = img.copy()
        doc = ImageDocument(frames=[Frame(width=frame.width, height=frame.height, mode=frame.mode, data=frame)], metadata=read_metadata(img), source_format="heif")
        return doc

    def encode(self, document, options=None):
        options = options or {}
        # Encode to HEIF via pillow-heif save
        if not _AVAILABLE:
            raise UnsupportedFormatError("pillow-heif not installed")
        import io
        buf = io.BytesIO()
        from ..core.metadata import clear_info_metadata, metadata_save_kwargs
        img = document.primary.data
        meta = metadata_save_kwargs(document.metadata, options.get("metadata", "preserve"), "HEIF", img.size)
        clear_info_metadata(img)
        try:
            img.save(buf, format="HEIF", quality=options.get("quality", 90), **meta)
        except Exception as e:
            raise EncodeError(f"HEIF encode failed: {e}") from e
        return buf.getvalue()
