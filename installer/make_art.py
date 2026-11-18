"""Genera las imágenes del instalador con los colores del programa.

Uso:  python installer/make_art.py
Crea installer/art/: fondo con degradado, panel lateral con el logo y logo pequeño.
Las imágenes generadas se incluyen en el repositorio; solo hay que volver a correr
este script si cambian los colores o el logo (assets/logo.png).
"""

import os

from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(HERE, "art")
LOGO = os.path.join(ROOT, "assets", "logo.png")

# Paleta del programa (src/openconverter/gui/tk_app.py)
BG = (11, 16, 32)          # #0b1020
PANEL = (17, 24, 39)       # #111827
ACCENT = (59, 130, 246)    # #3b82f6
ACCENT_HOVER = (37, 99, 235)   # #2563eb
ACCENT_SOFT = (29, 78, 216)    # #1d4ed8
INDIGO = (79, 70, 229)     # #4f46e5
TEXT = (241, 245, 249)     # #f1f5f9
MUTED = (148, 163, 184)    # #94a3b8


def _lerp(a, b, t):
    return tuple(int(round(a[i] + (b[i] - a[i]) * t)) for i in range(3))


def _vertical_gradient(w, h, stops):
    """stops: [(posición 0..1, color)]"""
    img = Image.new("RGB", (w, h))
    px = img.load()
    for y in range(h):
        t = y / max(1, h - 1)
        for i in range(len(stops) - 1):
            p0, c0 = stops[i]
            p1, c1 = stops[i + 1]
            if p0 <= t <= p1:
                color = _lerp(c0, c1, (t - p0) / max(1e-6, p1 - p0))
                break
        for x in range(w):
            px[x, y] = color
    return img


def _glow(size, center, radius, color, alpha):
    """Brillo radial difuso (capa RGBA)."""
    layer = Image.new("RGBA", size, color + (0,))
    mask = Image.new("L", size, 0)
    d = ImageDraw.Draw(mask)
    cx, cy = center
    d.ellipse([cx - radius, cy - radius, cx + radius, cy + radius], fill=alpha)
    mask = mask.filter(ImageFilter.GaussianBlur(radius * 0.55))
    layer.putalpha(mask)
    return layer


def _font(size, bold=True):
    fonts = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts")
    for name in (("seguisb.ttf", "segoeuib.ttf") if bold else ("segoeui.ttf",)):
        path = os.path.join(fonts, name)
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def background(w=1192, h=864):
    """Fondo de todas las páginas: azul noche con brillos azules suaves."""
    base = _vertical_gradient(w, h, [(0, (14, 21, 42)), (0.55, BG), (1, (8, 12, 26))]).convert("RGBA")
    base.alpha_composite(_glow((w, h), (int(w * 0.92), int(h * 0.05)), int(w * 0.42), ACCENT_SOFT, 120))
    base.alpha_composite(_glow((w, h), (int(w * 0.05), int(h * 0.98)), int(w * 0.38), INDIGO, 70))
    base.alpha_composite(_glow((w, h), (int(w * 0.55), int(h * 0.45)), int(w * 0.30), ACCENT, 28))
    return base.convert("RGB")


def side_panel(w, h):
    """Panel lateral de las páginas de bienvenida y final: degradado azul con el logo."""
    img = _vertical_gradient(w, h, [(0, ACCENT_HOVER), (0.45, ACCENT_SOFT), (0.8, (23, 37, 84)), (1, BG)])
    img = img.convert("RGBA")
    img.alpha_composite(_glow((w, h), (int(w * 0.5), int(h * 0.36)), int(w * 0.62), (147, 197, 253), 90))
    img.alpha_composite(_glow((w, h), (int(w * 0.1), int(h * 0.92)), int(w * 0.7), INDIGO, 110))
    logo = Image.open(LOGO).convert("RGBA")
    size = int(w * 0.56)
    logo = logo.resize((size, size), Image.LANCZOS)
    shadow = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    lx, ly = (w - size) // 2, int(h * 0.36) - size // 2
    shadow.paste((0, 0, 0, 120), (lx, ly + size // 14), logo.getchannel("A"))
    img.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(size // 12)))
    img.alpha_composite(logo, (lx, ly))
    d = ImageDraw.Draw(img)
    f_title = _font(max(12, int(w * 0.105)))
    title = "Open Converter"
    tw = d.textlength(title, font=f_title)
    ty = ly + size + int(h * 0.05)
    d.text(((w - tw) / 2, ty), title, font=f_title, fill=TEXT)
    f_sub = _font(max(9, int(w * 0.058)), bold=False)
    sub = "JPG · PNG · WEBP · HEIC · AVIF"
    sw = d.textlength(sub, font=f_sub)
    d.text(((w - sw) / 2, ty + int(w * 0.15)), sub, font=f_sub, fill=(191, 219, 254))
    return img.convert("RGB")


def small_logo(size):
    """Logo del encabezado de las páginas internas (fondo transparente)."""
    logo = Image.open(LOGO).convert("RGBA")
    return logo.resize((size, size), Image.LANCZOS)


def main():
    os.makedirs(OUT, exist_ok=True)
    background().save(os.path.join(OUT, "background.png"), optimize=True)
    # Tamaños recomendados por Inno Setup para el estilo moderno (100 %, 150 %, 200 %)
    for w, h in ((202, 386), (336, 643), (430, 824)):
        side_panel(w, h).save(os.path.join(OUT, f"side_{w}.png"), optimize=True)
    for s in (55, 83, 110):
        small_logo(s).save(os.path.join(OUT, f"small_{s}.png"), optimize=True)
    print("Imágenes del instalador en", OUT)


if __name__ == "__main__":
    main()
