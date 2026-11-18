"""Generic adapter for imageio-supported formats (EXR, HDR, IFF, etc.)."""

import io
import os
import tempfile
from typing import Any, Dict, Optional

try:
    import imageio
    _AVAILABLE = True
except Exception:
    _AVAILABLE = False

import numpy as np
from PIL import Image

from ..adapters.base import FormatAdapter, FormatCapabilities
from ..core.document import Frame, ImageDocument
from ..core.exceptions import DecodeError, EncodeError, UnsupportedFormatError
from ..core.metadata import read_metadata


class ImageIOFormatAdapter(FormatAdapter):
    def __init__(self, fmt):
        if not _AVAILABLE:
            raise UnsupportedFormatError("imageio not installed")
        self._fmt = fmt
        exts = list(getattr(fmt, "extensions", []))
        if not exts:
            exts = [".bin"]
        self.extensions = exts
        self.id = exts[0].lstrip(".").lower()
        self.mime_types = ["image/*"]
        self.capabilities = FormatCapabilities(lossless=False, alpha=True, animation=False, metadata_read=True, metadata_write=False)
        self._writable = self._probe_write()

    def can_encode(self) -> bool:
        return self._writable

    def _probe_write(self) -> bool:
        if not self.extensions:
            return False
        ext = self.extensions[0]
        fd, path = tempfile.mkstemp(suffix=ext)
        os.close(fd)
        try:
            os.remove(path)
        except Exception:
            pass
        try:
            arr = (np.zeros((4, 4, 3)) * 255).astype("uint8")
            imageio.imwrite(path, arr)
            return os.path.exists(path) and os.path.getsize(path) > 0
        except Exception:
            return False
        finally:
            try:
                os.remove(path)
            except Exception:
                pass

    def can_decode(self, data: bytes) -> bool:
        if not _AVAILABLE:
            return False
        try:
            arr = imageio.imread(io.BytesIO(data))
            return arr is not None
        except Exception:
            return False

    def decode(self, data: bytes, options: Optional[Dict[str, Any]] = None) -> ImageDocument:
        if not _AVAILABLE:
            raise UnsupportedFormatError("imageio not installed")
        try:
            arr = imageio.imread(io.BytesIO(data))
        except Exception as e:
            raise DecodeError(f"imageio decode failed: {e}") from e
        try:
            img = Image.fromarray(arr)
        except Exception as e:
            raise DecodeError(f"imageio->PIL failed: {e}") from e
        if img.mode not in ("RGB", "RGBA", "L", "I", "F"):
            img = img.convert("RGB")
        doc = ImageDocument(frames=[Frame(width=img.width, height=img.height, mode=img.mode, data=img)], metadata=read_metadata(img), source_format=self.id)
        return doc

    def encode(self, document: ImageDocument, options: Optional[Dict[str, Any]] = None) -> bytes:
        if not self._writable:
            raise EncodeError(f"Format {self.id} is read-only")
        if not _AVAILABLE:
            raise UnsupportedFormatError("imageio not installed")
        ext = self.extensions[0]
        img = document.primary.data
        if img.mode not in ("RGB", "RGBA", "L"):
            img = img.convert("RGB")
        arr = np.asarray(img)
        fd, path = tempfile.mkstemp(suffix=ext)
        os.close(fd)
        try:
            os.remove(path)
        except Exception:
            pass
        try:
            imageio.imwrite(path, arr)
            with open(path, "rb") as f:
                return f.read()
        except Exception as e:
            raise EncodeError(f"imageio encode failed ({self.id}): {e}") from e
        finally:
            try:
                os.remove(path)
            except Exception:
                pass
