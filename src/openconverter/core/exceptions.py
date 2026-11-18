"""Jerarquía de excepciones de OpenConverter."""

class OpenConverterError(Exception):
    """Base error."""


class UnsupportedFormatError(OpenConverterError):
    """No adapter can handle the requested format."""


class DecodeError(OpenConverterError):
    """Failed to decode the input image."""


class EncodeError(OpenConverterError):
    """Failed to encode the output image."""


class TransformError(OpenConverterError):
    """A transform step failed."""


class MetadataError(OpenConverterError):
    """Metadata read/write failure."""


class JobError(OpenConverterError):
    """Batch job failure."""
