"""Composable image processing pipeline."""

from typing import Any, Callable, Dict, List

from PIL import Image

from ..core.document import Frame, ImageDocument
from ..core.exceptions import TransformError


Transform = Callable[[Image.Image, Dict[str, Any]], Image.Image]


def _resize(img: Image.Image, params: Dict[str, Any]) -> Image.Image:
    w = params.get("width")
    h = params.get("height")
    fit = params.get("fit", "inside")  # inside | cover | exact
    resample = Image.LANCZOS
    if w and h and fit == "exact":
        return img.resize((int(w), int(h)), resample)
    if w or h:
        if w and not h:
            ratio = w / img.width
            h = int(img.height * ratio)
        elif h and not w:
            ratio = h / img.height
            w = int(img.width * ratio)
        else:
            if fit == "cover":
                # crop to fill
                ratio = max(w / img.width, h / img.height)
                nw, nh = int(img.width * ratio), int(img.height * ratio)
                img = img.resize((nw, nh), resample)
                left = (nw - w) // 2
                top = (nh - h) // 2
                return img.crop((left, top, left + w, top + h))
            # inside
            ratio = min(w / img.width, h / img.height)
            w, h = int(img.width * ratio), int(img.height * ratio)
        return img.resize((int(w), int(h)), resample)
    return img


def _crop(img: Image.Image, params: Dict[str, Any]) -> Image.Image:
    left = int(params.get("left", 0))
    top = int(params.get("top", 0))
    right = params.get("right")
    bottom = params.get("bottom")
    width = params.get("width")
    height = params.get("height")
    if width is not None and height is not None and right is None:
        right = left + int(width)
        bottom = top + int(height)
    if right is None or bottom is None:
        raise TransformError("crop requires right/bottom or width/height")
    return img.crop((left, top, int(right), int(bottom)))


def _rotate(img: Image.Image, params: Dict[str, Any]) -> Image.Image:
    angle = float(params.get("angle", 0))
    expand = bool(params.get("expand", True))
    return img.rotate(angle, expand=expand, resample=Image.BICUBIC)


def _flip(img: Image.Image, params: Dict[str, Any]) -> Image.Image:
    direction = params.get("direction", "horizontal")
    if direction == "horizontal":
        return img.transpose(Image.FLIP_LEFT_RIGHT)
    if direction == "vertical":
        return img.transpose(Image.FLIP_TOP_BOTTOM)
    raise TransformError(f"Unknown flip direction: {direction}")


def _grayscale(img: Image.Image, params: Dict[str, Any]) -> Image.Image:
    # Conserva la transparencia: grises en RGB + canal alfa original.
    if img.mode in ("RGBA", "LA", "PA") or (img.mode == "P" and "transparency" in img.info):
        rgba = img.convert("RGBA")
        gray = rgba.convert("L")
        return Image.merge("RGBA", (gray, gray, gray, rgba.getchannel("A")))
    return img.convert("L")


def _watermark(img: Image.Image, params: Dict[str, Any]) -> Image.Image:
    # Simple text watermark via PIL draw
    from PIL import ImageDraw, ImageFont
    text = params.get("text", "")
    opacity = int(params.get("opacity", 128))
    position = params.get("position", "bottom-right")
    out = img.convert("RGBA")
    overlay = Image.new("RGBA", out.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    try:
        font = ImageFont.truetype(params.get("font", ""), int(params.get("size", 24)))
    except Exception:
        font = ImageFont.load_default()
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    margin = int(params.get("margin", 10))
    if position == "bottom-right":
        x, y = out.width - tw - margin, out.height - th - margin
    elif position == "top-left":
        x, y = margin, margin
    elif position == "center":
        x, y = (out.width - tw) // 2, (out.height - th) // 2
    else:
        x, y = margin, margin
    draw.text((x, y), text, fill=(255, 255, 255, opacity), font=font)
    return Image.alpha_composite(out, overlay).convert(img.mode if img.mode in ("RGB", "RGBA") else "RGB")


TRANSFORMS: Dict[str, Transform] = {
    "resize": _resize,
    "crop": _crop,
    "rotate": _rotate,
    "flip": _flip,
    "grayscale": _grayscale,
    "watermark": _watermark,
}


def apply_transforms(document: ImageDocument, transforms: List[Dict[str, Any]]) -> ImageDocument:
    new_frames = []
    for frame in document.frames:
        img = frame.data
        for step in transforms:
            # step is like {"resize": {...}} or {"op": "resize", ...}
            if "op" in step:
                op = step["op"]
                params = {k: v for k, v in step.items() if k != "op"}
            else:
                # single-key form
                if len(step) != 1:
                    raise TransformError(f"Invalid transform step: {step}")
                op = list(step.keys())[0]
                params = step[op] or {}
            if op not in TRANSFORMS:
                raise TransformError(f"Unknown transform: {op}")
            try:
                img = TRANSFORMS[op](img, params)
            except Exception as e:
                raise TransformError(f"{op} failed: {e}") from e
        new_frames.append(Frame(width=img.width, height=img.height, mode=img.mode, data=img, delay=frame.delay, disposal=frame.disposal))
    document.frames = new_frames
    return document
