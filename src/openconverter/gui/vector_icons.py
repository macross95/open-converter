"""Íconos dibujados con Pillow, para macOS y Linux.

En Windows el programa usa la fuente de íconos del sistema (Segoe Fluent). Los otros
sistemas no la tienen ni se puede redistribuir, así que aquí se dibujan los mismos
íconos como líneas, a 8 veces el tamaño y reducidos, para que salgan suaves.
"""

from PIL import Image, ImageDraw

_SS = 8  # factor de supermuestreo


def _stroke(size):
    return max(1, round(size * _SS / 11))


def _draw_add(d, s, c, w):
    m = s * 0.2
    d.line([(s / 2, m), (s / 2, s - m)], fill=c, width=w)
    d.line([(m, s / 2), (s - m, s / 2)], fill=c, width=w)


def _draw_remove(d, s, c, w):
    d.line([(s * 0.2, s / 2), (s * 0.8, s / 2)], fill=c, width=w)


def _draw_close(d, s, c, w):
    m = s * 0.24
    d.line([(m, m), (s - m, s - m)], fill=c, width=w)
    d.line([(m, s - m), (s - m, m)], fill=c, width=w)


def _draw_check(d, s, c, w):
    d.line([(s * 0.18, s * 0.55), (s * 0.4, s * 0.76), (s * 0.82, s * 0.28)], fill=c, width=w, joint="curve")


def _draw_error(d, s, c, w):
    d.ellipse([s * 0.1, s * 0.1, s * 0.9, s * 0.9], outline=c, width=w)
    m = s * 0.34
    d.line([(m, m), (s - m, s - m)], fill=c, width=w)
    d.line([(m, s - m), (s - m, m)], fill=c, width=w)


def _draw_chevron(d, s, c, w):
    d.line([(s * 0.22, s * 0.38), (s * 0.5, s * 0.66), (s * 0.78, s * 0.38)], fill=c, width=w, joint="curve")


def _draw_stop(d, s, c, w):
    d.rounded_rectangle([s * 0.25, s * 0.25, s * 0.75, s * 0.75], radius=s * 0.06, fill=c)


def _draw_convert(d, s, c, w):
    # dos flechas en sentidos opuestos
    a, b = s * 0.15, s * 0.85
    d.line([(a, s * 0.34), (b, s * 0.34)], fill=c, width=w)
    d.line([(b - s * 0.16, s * 0.2), (b, s * 0.34), (b - s * 0.16, s * 0.48)], fill=c, width=w, joint="curve")
    d.line([(a, s * 0.68), (b, s * 0.68)], fill=c, width=w)
    d.line([(a + s * 0.16, s * 0.54), (a, s * 0.68), (a + s * 0.16, s * 0.82)], fill=c, width=w, joint="curve")


def _draw_trash(d, s, c, w):
    d.line([(s * 0.18, s * 0.28), (s * 0.82, s * 0.28)], fill=c, width=w)
    d.line([(s * 0.4, s * 0.28), (s * 0.4, s * 0.18), (s * 0.6, s * 0.18), (s * 0.6, s * 0.28)], fill=c, width=w)
    d.polygon([(s * 0.26, s * 0.34), (s * 0.74, s * 0.34), (s * 0.68, s * 0.84), (s * 0.32, s * 0.84)],
              outline=c, width=w)


def _draw_folder(d, s, c, w):
    pts = [(s * 0.1, s * 0.25), (s * 0.4, s * 0.25), (s * 0.48, s * 0.36), (s * 0.9, s * 0.36),
           (s * 0.9, s * 0.78), (s * 0.1, s * 0.78)]
    d.polygon(pts, outline=c, width=w)


def _draw_folder_open(d, s, c, w):
    d.line([(s * 0.1, s * 0.78), (s * 0.1, s * 0.25), (s * 0.4, s * 0.25), (s * 0.48, s * 0.36),
            (s * 0.86, s * 0.36), (s * 0.86, s * 0.46)], fill=c, width=w, joint="curve")
    d.polygon([(s * 0.1, s * 0.78), (s * 0.24, s * 0.46), (s * 0.94, s * 0.46), (s * 0.8, s * 0.78)],
              outline=c, width=w)


def _draw_max(d, s, c, w):
    d.rectangle([s * 0.2, s * 0.2, s * 0.8, s * 0.8], outline=c, width=w)


def _draw_restore(d, s, c, w):
    d.rectangle([s * 0.16, s * 0.3, s * 0.7, s * 0.84], outline=c, width=w)
    d.line([(s * 0.3, s * 0.3), (s * 0.3, s * 0.16), (s * 0.84, s * 0.16), (s * 0.84, s * 0.7), (s * 0.7, s * 0.7)],
           fill=c, width=w)


_DRAWERS = {
    "add": _draw_add, "remove": _draw_remove, "clear": _draw_trash, "check": _draw_check,
    "error": _draw_error, "chevron": _draw_chevron, "convert": _draw_convert, "stop": _draw_stop,
    "folder": _draw_folder, "folder_open": _draw_folder_open,
    "win_min": _draw_remove, "win_max": _draw_max, "win_restore": _draw_restore, "win_close": _draw_close,
}


def draw_icon(name, color, px):
    """Ícono RGBA de px × px píxeles, o None si no existe."""
    fn = _DRAWERS.get(name)
    if fn is None:
        return None
    big = px * _SS
    img = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    fn(ImageDraw.Draw(img), big, color, _stroke(px))
    return img.resize((px, px), Image.LANCZOS)
