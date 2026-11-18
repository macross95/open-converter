"""Built-in presets."""

PRESETS = {
    "web": {
        "format": "webp",
        "quality": 82,
        "resize": {"width": 2048, "fit": "inside"},
        "metadata": "strip",
    },
    "thumbnail": {
        "format": "jpeg",
        "quality": 75,
        "resize": {"width": 256, "height": 256, "fit": "cover"},
        "metadata": "strip",
    },
    "print": {
        "format": "tiff",
        "compression": "tiff_lzw",
        "metadata": "preserve",
    },
    "lossless": {
        "format": "png",
        "metadata": "preserve",
    },
    "social": {
        "format": "jpeg",
        "quality": 90,
        "resize": {"width": 1080, "height": 1080, "fit": "cover"},
        "metadata": "strip",
    },
}


def get_preset(name: str):
    if name not in PRESETS:
        raise KeyError(f"Unknown preset: {name}")
    return dict(PRESETS[name])
