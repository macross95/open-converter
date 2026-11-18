"""Pillow-backed adapter: covers all formats Pillow supports."""

import io
from typing import Any, Dict, List, Optional

# Optional plugins
try:
    import pillow_heif
    pillow_heif.register_heif_opener()
except Exception:
    pass
try:
    import pillow_jxl  # noqa: F401
except Exception:
    pass
try:
    import pillow_avif_plugin  # noqa: F401
except Exception:
    pass

from PIL import Image

Image.init()

from ..adapters.base import FormatAdapter, FormatCapabilities
from ..core.document import Frame, ImageDocument
from ..core.exceptions import DecodeError, EncodeError
from ..core.metadata import clear_info_metadata, metadata_save_kwargs, read_metadata


# Build format map dynamically from Pillow's registry.
# PILLOW_FORMATS: {pillow_format_name: (our_id, [extensions])}
PILLOW_FORMATS: Dict[str, tuple] = {}
for _fmt, _exts in [(f, [e for e, fr in Image.EXTENSION.items() if fr == f]) for f in Image.SAVE]:
    PILLOW_FORMATS[_fmt] = (_fmt.lower(), _exts)

# Ensure common aliases
# (already covered by Image.EXTENSION)


class PillowAdapter(FormatAdapter):
    id = "pillow"
    extensions = sorted({e for exts in (v[1] for v in PILLOW_FORMATS.values()) for e in exts})
    mime_types = ["image/*"]
    capabilities = FormatCapabilities(lossless=False, alpha=True, animation=True, metadata_read=True, metadata_write=True)

    def can_decode(self, data: bytes) -> bool:
        try:
            img = Image.open(io.BytesIO(data))
            img.verify()
            return True
        except Exception:
            return False

    def _normalize_format(self, fmt: Optional[str]) -> str:
        if not fmt:
            return "png"
        fmt = fmt.lower().lstrip(".")
        # map extension to pillow format id
        pf = Image.EXTENSION.get("." + fmt)
        if pf:
            return pf.lower()
        if fmt in (v[0] for v in PILLOW_FORMATS.values()):
            return fmt
        if fmt.upper() in PILLOW_FORMATS:
            return fmt
        return fmt

    def decode(self, data: bytes, options: Optional[Dict[str, Any]] = None) -> ImageDocument:
        options = options or {}
        try:
            img = Image.open(io.BytesIO(data))
        except Exception as e:
            raise DecodeError(f"Pillow decode failed: {e}") from e
        frames: List[Frame] = []
        n = getattr(img, "n_frames", 1)
        for i in range(n):
            try:
                img.seek(i)
            except EOFError:
                break
            frame = img.copy()
            try:
                from PIL import ImageOps
                frame = ImageOps.exif_transpose(frame)
            except Exception:
                pass
            frames.append(Frame(width=frame.width, height=frame.height, mode=frame.mode, data=frame, delay=img.info.get("duration", 0)))
        if not frames:
            raise DecodeError("No frames decoded")
        meta = read_metadata(img)
        doc = ImageDocument(frames=frames, metadata=meta, source_format=(img.format or "").lower())
        return doc

    def encode(self, document: ImageDocument, options: Optional[Dict[str, Any]] = None) -> bytes:
        options = options or {}
        fmt_raw = options.get("format") or document.source_format or "png"
        fmt_id = self._normalize_format(fmt_raw)
        # map id -> pillow format name
        reverse = {v[0]: k for k, v in PILLOW_FORMATS.items()}
        pillow_fmt = reverse.get(fmt_id)
        if pillow_fmt is None:
            # try direct
            pillow_fmt = fmt_id.upper()
            if pillow_fmt not in PILLOW_FORMATS:
                raise EncodeError(f"Unsupported output format: {fmt_id}")
        quality = options.get("quality", 90)
        save_kwargs: Dict[str, Any] = {}
        if pillow_fmt == "JPEG":
            save_kwargs["quality"] = int(quality)
            save_kwargs["optimize"] = True
        elif pillow_fmt == "PNG":
            save_kwargs["optimize"] = True
        elif pillow_fmt == "WEBP":
            save_kwargs["quality"] = int(quality)
            save_kwargs["method"] = 6
            if document.is_animated:
                save_kwargs["save_all"] = True
                save_kwargs["append_images"] = [f.data for f in document.frames[1:]]
                save_kwargs["duration"] = [f.delay for f in document.frames]
                save_kwargs["loop"] = options.get("loop", 0)
        elif pillow_fmt == "TIFF":
            save_kwargs["compression"] = options.get("compression", "tiff_lzw")
        elif pillow_fmt == "GIF":
            save_kwargs["save_all"] = document.is_animated
            save_kwargs["append_images"] = [f.data for f in document.frames[1:]] if document.is_animated else []
            save_kwargs["duration"] = [f.delay for f in document.frames] if document.is_animated else 0
            save_kwargs["loop"] = options.get("loop", 0)
        elif pillow_fmt == "AVIF":
            save_kwargs["quality"] = int(quality)
        elif pillow_fmt == "JPEG2000":
            save_kwargs["quality"] = int(quality)
        elif pillow_fmt == "PDF":
            save_kwargs["resolution"] = options.get("resolution", 100.0)

        buf = io.BytesIO()
        primary = document.primary.data
        if pillow_fmt == "JPEG" and primary.mode in ("RGBA", "P", "LA"):
            primary = primary.convert("RGB")
        if pillow_fmt == "BMP" and primary.mode in ("RGBA",):
            primary = primary.convert("RGB")
        if pillow_fmt in ("PDF", "PCX", "EPS") and primary.mode != "RGB":
            primary = primary.convert("RGB")
        if pillow_fmt == "ICNS" and primary.mode not in ("RGB", "RGBA"):
            primary = primary.convert("RGBA")

        # Metadatos según la política (preserve | selective | strip). Se limpian de
        # img.info para que formatos como TIFF o HEIF no copien el EXIF original por su cuenta.
        save_kwargs.update(metadata_save_kwargs(document.metadata, options.get("metadata", "preserve"),
                                                pillow_fmt, primary.size))
        clear_info_metadata(primary)

        try:
            primary.save(buf, format=pillow_fmt, **save_kwargs)
        except Exception as e:
            if "exif" not in save_kwargs:
                raise EncodeError(f"Pillow encode failed ({pillow_fmt}): {e}") from e
            # Algunos EXIF no caben en el formato (JPEG admite hasta 64 KB): se guarda sin EXIF.
            save_kwargs.pop("exif")
            document.warnings.append(f"EXIF omitido: {e}")
            buf = io.BytesIO()
            try:
                primary.save(buf, format=pillow_fmt, **save_kwargs)
            except Exception as e2:
                raise EncodeError(f"Pillow encode failed ({pillow_fmt}): {e2}") from e2
        return buf.getvalue()
