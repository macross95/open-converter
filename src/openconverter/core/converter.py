"""High-level Converter facade."""

import os
import time
from typing import Any, Callable, Dict, List, Optional

from .registry import build_default_registry, FormatRegistry
from .pipeline import apply_transforms
from .exceptions import UnsupportedFormatError


class Converter:
    def __init__(self, registry: Optional[FormatRegistry] = None, concurrency: int = 1):
        self.registry = registry or build_default_registry()
        self.concurrency = concurrency

    def detect_format(self, data: bytes, path: Optional[str] = None):
        adapter = self.registry.detect(data)
        if adapter is None and path:
            adapter = self.registry.detect_from_path(path)
        return adapter

    def convert(
        self,
        input_path: str,
        output_path: str,
        *,
        format: Optional[str] = None,
        quality: int = 90,
        transforms: Optional[List[Dict[str, Any]]] = None,
        metadata: str = "preserve",
        preset: Optional[str] = None,
        on_progress: Optional[Callable[[int, str], None]] = None,
    ) -> Dict[str, Any]:
        if preset:
            from ..presets.defaults import get_preset
            p = get_preset(preset)
            format = format or p.get("format")
            quality = p.get("quality", quality)
            if "resize" in p:
                transforms = (transforms or []) + [{"resize": p["resize"]}]
            metadata = p.get("metadata", metadata)

        t0 = time.time()
        if on_progress:
            on_progress(5, "reading")
        with open(input_path, "rb") as f:
            data = f.read()

        adapter = self.registry.detect(data)
        if adapter is None:
            adapter = self.registry.detect_from_path(input_path)
        if adapter is None:
            raise UnsupportedFormatError(f"Cannot detect format for {input_path}")
        if on_progress:
            on_progress(15, "decoding")
        document = adapter.decode(data)
        document.source_path = input_path

        if transforms:
            if on_progress:
                on_progress(40, "transforming")
            apply_transforms(document, transforms)

        # Determine output format
        out_ext = os.path.splitext(output_path)[1].lower().lstrip(".")
        out_adapter = None
        if format:
            # find adapter by id or extension
            for a in self.registry.adapters():
                if a.id == format or format in [e.lstrip(".") for e in a.extensions]:
                    out_adapter = a
                    break
        if out_adapter is None:
            out_adapter = self.registry.detect_from_path(output_path)
        if out_adapter is None:
            # fallback: pillow
            out_adapter = self.registry.get("pillow")
        if on_progress:
            on_progress(70, "encoding")
        out_bytes = out_adapter.encode(document, {
            "format": format or out_ext,
            "quality": quality,
            "metadata": metadata,
        })
        # metadata policy apply (best-effort already in encode)
        with open(output_path, "wb") as f:
            f.write(out_bytes)
        dur = int((time.time() - t0) * 1000)
        if on_progress:
            on_progress(100, "done")
        return {
            "input": input_path,
            "output": output_path,
            "duration_ms": dur,
            "size": len(out_bytes),
            "warnings": document.warnings,
        }

    def info(self, path: str) -> Dict[str, Any]:
        with open(path, "rb") as f:
            data = f.read()
        adapter = self.registry.detect(data) or self.registry.detect_from_path(path)
        if adapter is None:
            raise UnsupportedFormatError(f"Cannot detect format for {path}")
        document = adapter.decode(data)
        primary = document.primary
        return {
            "path": path,
            "format": document.source_format,
            "adapter": adapter.id,
            "width": primary.width,
            "height": primary.height,
            "mode": primary.mode,
            "frames": len(document.frames),
            "animated": document.is_animated,
            "metadata": {
                "exif_count": len(document.metadata.exif),
                "has_icc": document.metadata.icc_profile is not None,
                "orientation": document.metadata.orientation,
            },
            "capabilities": adapter.capabilities.to_dict(),
            "warnings": document.warnings,
        }

    def supported_formats(self):
        return self.registry.supported_formats()

    def supported_output_formats(self):
        out = []
        try:
            from ..adapters.pillow_adapter import PILLOW_FORMATS
            out.extend(v[0] for v in PILLOW_FORMATS.values())
        except Exception:
            pass
        for a in self.registry.adapters():
            if a.id in ("pillow", "raw", "svg"):
                continue
            if hasattr(a, "can_encode") and not a.can_encode():
                continue
            out.append(a.id)
        out = sorted(set(out))
        # Common formats first
        common = ["jpg", "jpeg", "png", "webp", "gif", "tiff", "tif", "bmp", "avif", "heic", "heif", "wbmp", "ico", "jp2", "jxl", "qoi", "tga", "dds"]
        ordered = [f for f in common if f in out]
        ordered += [f for f in out if f not in common]
        return ordered
