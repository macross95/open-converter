"""Base interface for format adapters."""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..core.document import ImageDocument


class FormatCapabilities:
    def __init__(
        self,
        lossless: bool = False,
        alpha: bool = False,
        animation: bool = False,
        metadata_read: bool = True,
        metadata_write: bool = True,
        max_width: Optional[int] = None,
        max_height: Optional[int] = None,
    ):
        self.lossless = lossless
        self.alpha = alpha
        self.animation = animation
        self.metadata_read = metadata_read
        self.metadata_write = metadata_write
        self.max_width = max_width
        self.max_height = max_height

    def to_dict(self) -> Dict[str, Any]:
        return {
            "lossless": self.lossless,
            "alpha": self.alpha,
            "animation": self.animation,
            "metadata_read": self.metadata_read,
            "metadata_write": self.metadata_write,
            "max_width": self.max_width,
            "max_height": self.max_height,
        }


class FormatAdapter(ABC):
    """A format adapter knows how to decode/encode one or more formats."""

    id: str = ""
    extensions: List[str] = []
    mime_types: List[str] = []
    capabilities: FormatCapabilities = FormatCapabilities()

    @abstractmethod
    def can_decode(self, data: bytes) -> bool:
        ...

    @abstractmethod
    def decode(self, data: bytes, options: Optional[Dict[str, Any]] = None) -> "ImageDocument":
        ...

    @abstractmethod
    def encode(self, document: "ImageDocument", options: Optional[Dict[str, Any]] = None) -> bytes:
        ...

    def supports_extension(self, ext: str) -> bool:
        return ext.lower().lstrip(".") in [e.lower().lstrip(".") for e in self.extensions]

    def can_encode(self) -> bool:
        """Whether this adapter can encode (write) images."""
        return True
