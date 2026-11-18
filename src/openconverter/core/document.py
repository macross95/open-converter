"""In-memory representation of an image document."""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class Frame:
    width: int
    height: int
    mode: str  # Pillow mode, e.g. "RGB", "RGBA", "P"
    data: Any  # PIL.Image.Image
    delay: int = 0  # ms, for animation
    disposal: int = 0


@dataclass
class MetadataBag:
    exif: Dict[str, Any] = field(default_factory=dict)
    exif_raw: Optional[bytes] = None  # EXIF original en bytes, para volver a escribirlo al guardar
    xmp: Optional[str] = None
    iptc: Dict[str, Any] = field(default_factory=dict)
    icc_profile: Optional[bytes] = None
    orientation: int = 1
    extras: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ImageDocument:
    frames: List[Frame]
    metadata: MetadataBag = field(default_factory=MetadataBag)
    source_path: Optional[str] = None
    source_format: Optional[str] = None
    warnings: List[str] = field(default_factory=list)

    @property
    def is_animated(self) -> bool:
        return len(self.frames) > 1

    @property
    def primary(self) -> Frame:
        return self.frames[0]
