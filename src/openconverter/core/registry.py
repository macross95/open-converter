"""Format registry: discovers adapters and resolves by data/extension."""

import os
from typing import Dict, List, Optional

from ..adapters.base import FormatAdapter
from ..core.exceptions import UnsupportedFormatError


class FormatRegistry:
    def __init__(self):
        self._adapters: List[FormatAdapter] = []
        self._by_id: Dict[str, FormatAdapter] = {}

    def register(self, adapter: FormatAdapter) -> None:
        self._adapters.append(adapter)
        self._by_id[adapter.id] = adapter

    def adapters(self) -> List[FormatAdapter]:
        return list(self._adapters)

    def get(self, format_id: str) -> FormatAdapter:
        if format_id not in self._by_id:
            raise UnsupportedFormatError(f"Unknown format: {format_id}")
        return self._by_id[format_id]

    def detect(self, data: bytes) -> Optional[FormatAdapter]:
        for adapter in self._adapters:
            try:
                if adapter.can_decode(data):
                    return adapter
            except Exception:
                continue
        return None

    def detect_from_path(self, path: str) -> Optional[FormatAdapter]:
        ext = os.path.splitext(path)[1]
        for adapter in self._adapters:
            if adapter.supports_extension(ext):
                return adapter
        return None

    def supported_extensions(self) -> List[str]:
        out = []
        for a in self._adapters:
            out.extend(a.extensions)
        return sorted(set(out))

    def supported_formats(self) -> List[Dict]:
        return [
            {
                "id": a.id,
                "extensions": a.extensions,
                "mime_types": a.mime_types,
                "capabilities": a.capabilities.to_dict(),
            }
            for a in self._adapters
        ]


def build_default_registry() -> FormatRegistry:
    reg = FormatRegistry()
    # Pillow adapter (covers most common formats)
    try:
        from ..adapters.pillow_adapter import PillowAdapter
        reg.register(PillowAdapter())
    except Exception:
        pass
    # Optional adapters
    try:
        from ..adapters.heif_adapter import HeifAdapter
        reg.register(HeifAdapter())
    except Exception:
        pass
    try:
        from ..adapters.raw_adapter import RawAdapter
        reg.register(RawAdapter())
    except Exception:
        pass
    try:
        from ..adapters.svg_adapter import SvgAdapter
        reg.register(SvgAdapter())
    except Exception:
        pass
    # imageio-backed formats (EXR, HDR, IFF, CUR, FITS, DICOM, etc.)
    try:
        import imageio
        from ..adapters.imageio_adapter import ImageIOFormatAdapter
        pillow_exts = {e.lower() for a in reg.adapters() for e in a.extensions}
        seen_ids = {a.id for a in reg.adapters()}
        existing_exts = set(pillow_exts)
        for fmt in imageio.formats:
            exts = list(getattr(fmt, "extensions", []))
            if not exts or len(exts) > 3:
                continue
            primary = exts[0].lower()
            # skip formats already covered by Pillow
            if primary in pillow_exts:
                continue
            try:
                adapter = ImageIOFormatAdapter(fmt)
            except Exception:
                continue
            if adapter.id in seen_ids:
                continue
            reg.register(adapter)
            seen_ids.add(adapter.id)
            existing_exts.update(e.lower() for e in exts)
    except Exception:
        pass
    return reg
