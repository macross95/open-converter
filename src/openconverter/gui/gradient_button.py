"""Botones con degradado de estilo actual para Open Converter.

CustomTkinter no admite degradados, así que el fondo del botón se dibuja como imagen
(Pillow) en un Canvas y encima van el ícono y el texto de Tk (nítidos y traducibles).

Estilos:
- Sólidos ("primary", "danger"): degradado diagonal, línea de luz sutil arriba y un
  resplandor difuso del mismo color debajo del botón.
- Vidrio ("tint", "neutral", "ghost"): capa translúcida con borde fino de luz que se
  desvanece hacia abajo.
"""

import tkinter as tk

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageTk

STYLES = {
    "primary": dict(solid=True, stops=((56, 148, 255), (37, 99, 235), (99, 88, 240)), glow=(59, 110, 246),
                    glow_a=150, text="#ffffff", icon="#ffffff"),
    "danger": dict(solid=True, stops=((251, 113, 133), (239, 68, 68), (220, 38, 38)), glow=(239, 68, 68),
                   glow_a=140, text="#ffffff", icon="#ffffff"),
    "tint": dict(solid=False, fill=(59, 130, 246), fill_a=(78, 34), stroke=(147, 197, 253), stroke_a=(150, 36),
                 text="#dbeafe", icon="#93c5fd"),
    "neutral": dict(solid=False, fill=(255, 255, 255), fill_a=(24, 9), stroke=(255, 255, 255), stroke_a=(52, 12),
                    text="#f1f5f9", icon="#cbd5e1"),
    "ghost": dict(solid=False, fill=(255, 255, 255), fill_a=(11, 4), stroke=(255, 255, 255), stroke_a=(30, 8),
                  text="#94a3b8", icon="#94a3b8"),
    "disabled": dict(solid=False, fill=(255, 255, 255), fill_a=(8, 8), stroke=(255, 255, 255), stroke_a=(15, 15),
                     text="#475569", icon="#475569"),
}

# Margen alrededor del cuerpo del botón para el resplandor (px lógicos): lados, arriba, abajo
MARGIN_X, MARGIN_TOP, MARGIN_BOTTOM = 4, 2, 6

_SUPERSAMPLE = 3
_cache = {}


def _shade(color, amount):
    """amount > 0 aclara hacia blanco; < 0 oscurece hacia negro."""
    if amount >= 0:
        return tuple(int(c + (255 - c) * amount) for c in color)
    return tuple(int(c * (1 + amount)) for c in color)


def _lerp3(stops, t):
    a, b, c = stops
    if t < 0.5:
        s, x, y = t / 0.5, a, b
    else:
        s, x, y = (t - 0.5) / 0.5, b, c
    return tuple(int(x[i] + (y[i] - x[i]) * s) for i in range(3))


def _vertical_alpha(width, height, top, bottom, until=1.0):
    """Máscara L que va de `top` a `bottom` (alfa) hasta la fracción `until` de la altura."""
    col = Image.new("L", (1, height))
    limit = max(1.0, height * until)
    col.putdata([int(top + (bottom - top) * min(1.0, y / limit)) for y in range(height)])
    return col.resize((width, height))


def _diagonal(width, height, stops):
    """Degradado diagonal (arriba-izquierda a abajo-derecha) de tres tonos."""
    ramp = Image.linear_gradient("L")
    horizontal = ramp.rotate(90).resize((width, height))
    vertical = ramp.resize((width, height))
    t = Image.blend(horizontal, vertical, 0.35)
    lut = [_lerp3(stops, v / 255) for v in range(256)]
    channels = [t.point([lut[v][i] for v in range(256)]) for i in range(3)]
    return Image.merge("RGB", channels)


def render_button(width, height, kind="neutral", state="normal", radius=12, margins=(4, 2, 6)):
    """Imagen RGBA del botón completo (cuerpo + resplandor) en píxeles finales."""
    s = _SUPERSAMPLE
    pal = STYLES["disabled" if state == "disabled" else kind]
    W, H = width * s, height * s
    mx, mt, mb = (m * s for m in margins)
    press = s if state == "pressed" else 0
    x0, y0 = mx, mt + press
    bw, bh = max(4, W - 2 * mx), max(4, H - mt - mb)
    r = max(1, min(radius * s, bh // 2, bw // 2))
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))

    body_mask = Image.new("L", (bw, bh), 0)
    ImageDraw.Draw(body_mask).rounded_rectangle([0, 0, bw - 1, bh - 1], r, fill=255)
    stroke_mask = Image.new("L", (bw, bh), 0)
    ImageDraw.Draw(stroke_mask).rounded_rectangle([0, 0, bw - 1, bh - 1], r, outline=255, width=s)

    if pal["solid"]:
        stops = pal["stops"]
        glow_a = pal["glow_a"]
        if state == "hover":
            stops = tuple(_shade(c, 0.08) for c in stops)
            glow_a = int(glow_a * 1.35)
        elif state == "pressed":
            stops = tuple(_shade(c, -0.08) for c in stops)
            glow_a = int(glow_a * 0.55)
        # Resplandor difuso del color del botón, un poco más abajo
        glow = Image.new("L", (W, H), 0)
        ImageDraw.Draw(glow).rounded_rectangle(
            [x0 + 3 * s, y0 + 3 * s, x0 + bw - 1 - 3 * s, y0 + bh - 1 + 2 * s], r, fill=min(255, glow_a))
        glow = glow.filter(ImageFilter.GaussianBlur(4 * s))
        layer = Image.new("RGBA", (W, H), pal["glow"] + (0,))
        layer.putalpha(glow)
        img.alpha_composite(layer)
        body = _diagonal(bw, bh, stops).convert("RGBA")
        body.putalpha(body_mask)
        # Línea de luz sutil arriba (se desvanece hacia los costados de abajo)
        light = ImageChops.multiply(stroke_mask, _vertical_alpha(bw, bh, 95, 0, until=0.6))
        white = Image.new("RGBA", (bw, bh), (255, 255, 255, 0))
        white.putalpha(light)
        body.alpha_composite(white)
    else:
        fill_top, fill_bottom = pal["fill_a"]
        stroke_top, stroke_bottom = pal["stroke_a"]
        if state == "hover":
            fill_top, fill_bottom = fill_top + 14, fill_bottom + 10
            stroke_top, stroke_bottom = min(255, stroke_top + 40), stroke_bottom + 10
        elif state == "pressed":
            fill_top, fill_bottom = fill_top + 6, fill_bottom + 8
        body = Image.new("RGBA", (bw, bh), pal["fill"] + (0,))
        body.putalpha(ImageChops.multiply(body_mask, _vertical_alpha(bw, bh, fill_top, fill_bottom)))
        edge = Image.new("RGBA", (bw, bh), pal["stroke"] + (0,))
        edge.putalpha(ImageChops.multiply(stroke_mask, _vertical_alpha(bw, bh, stroke_top, stroke_bottom)))
        body.alpha_composite(edge)

    img.alpha_composite(body, (x0, y0))
    return img.resize((width, height), Image.LANCZOS)


def _photo(master, width, height, kind, state, radius, margins):
    key = (width, height, kind, state, radius, margins)
    photo = _cache.get(key)
    if photo is None:
        if len(_cache) > 400:
            _cache.pop(next(iter(_cache)))
        photo = ImageTk.PhotoImage(render_button(width, height, kind, state, radius, margins), master=master)
        _cache[key] = photo
    return photo


class GradientButton(tk.Canvas):
    """Botón con degradado. Se usa como un botón normal:
    configure(text=, state=, kind=, icon_name=, command=) y cget("state")."""

    def __init__(self, master, *, text="", command=None, kind="neutral", icon_name=None, height=34,
                 width=0, radius=12, font=None, bg="#111827", scale=1.0, icon_factory=None, padding=16):
        self._scale = scale or 1.0
        px = lambda v: int(round(v * self._scale))  # noqa: E731
        self._mx, self._mt, self._mb = px(MARGIN_X), px(MARGIN_TOP), px(MARGIN_BOTTOM)
        super().__init__(master, height=px(height) + self._mt + self._mb,
                         width=(px(width) if width else px(40)) + 2 * self._mx, bg=bg,
                         highlightthickness=0, bd=0, cursor="hand2")
        self._text = text
        self._command = command
        self._kind = kind
        self._icon_name = icon_name
        self._icon_factory = icon_factory
        self._font = font
        self._font_name = str(font) if font is not None else "TkDefaultFont"
        self._radius = radius
        self._fixed_width = bool(width)
        self._padding = px(padding)
        self._gap = px(8)
        self._icon_size = 16
        self._enabled = True
        self._hover = False
        self._pressed = False
        self._bg_item = self.create_image(0, 0, anchor="nw")
        self._icon_item = self.create_image(0, 0, anchor="center", state="hidden")
        self._text_item = self.create_text(0, 0, text="", font=font, anchor="center")
        tk.Canvas.bind(self, "<Configure>", lambda e: self._redraw(), "+")
        tk.Canvas.bind(self, "<Enter>", self._on_enter, "+")
        tk.Canvas.bind(self, "<Leave>", self._on_leave, "+")
        tk.Canvas.bind(self, "<ButtonPress-1>", self._on_press, "+")
        tk.Canvas.bind(self, "<ButtonRelease-1>", self._on_release, "+")
        self._update_width()

    # ---------------------------------------------------------------- API tipo botón

    def configure(self, cnf=None, **kw):
        changed = False
        for key in ("text", "kind", "icon_name", "command", "state"):
            if key not in kw:
                continue
            value = kw.pop(key)
            changed = True
            if key == "state":
                self._enabled = value != "disabled"
                if not self._enabled:
                    self._pressed = False
                tk.Canvas.configure(self, cursor="hand2" if self._enabled else "")
            elif key == "command":
                self._command = value
            else:
                setattr(self, "_" + key, value)
        if cnf or kw:
            tk.Canvas.configure(self, cnf, **kw)
        if changed:
            self._update_width()
            self._redraw()

    config = configure

    def cget(self, key):
        if key == "state":
            return "normal" if self._enabled else "disabled"
        if key in ("text", "kind", "icon_name"):
            return getattr(self, "_" + key)
        return tk.Canvas.cget(self, key)

    def grid(self, cnf=None, **kw):
        return tk.Canvas.grid_configure(self, cnf or {}, **self._scaled(kw))

    def pack(self, cnf=None, **kw):
        return tk.Canvas.pack_configure(self, cnf or {}, **self._scaled(kw))

    def _scaled(self, kw):
        for key in ("padx", "pady", "ipadx", "ipady"):
            if key in kw:
                v = kw[key]
                kw[key] = tuple(int(round(x * self._scale)) for x in v) if isinstance(v, (tuple, list)) \
                    else int(round(v * self._scale))
        return kw

    # ---------------------------------------------------------------- dibujo

    def _state_name(self):
        if not self._enabled:
            return "disabled"
        if self._pressed:
            return "pressed"
        return "hover" if self._hover else "normal"

    def _icon_width(self):
        return int(round(self._icon_size * self._scale)) if self._icon_name else 0

    def _content_width(self):
        text_w = int(self.tk.call("font", "measure", self._font_name, self._text)) if self._text else 0
        icon_w = self._icon_width()
        gap = self._gap if (text_w and icon_w) else 0
        return text_w, icon_w, gap

    def _update_width(self):
        if self._fixed_width:
            return
        text_w, icon_w, gap = self._content_width()
        tk.Canvas.configure(self, width=self._padding * 2 + icon_w + gap + text_w + 2 * self._mx)

    def _redraw(self):
        try:
            w, h = self.winfo_width(), self.winfo_height()
        except tk.TclError:
            return
        if w < 8 or h < 8:
            return
        state = self._state_name()
        pal = STYLES["disabled" if state == "disabled" else self._kind]
        margins = (MARGIN_X, MARGIN_TOP, MARGIN_BOTTOM)
        self.itemconfigure(self._bg_item, image=_photo(self, w, h, self._kind, state, self._radius, margins))
        body_h = h - self._mt - self._mb
        cy = self._mt + (max(1, round(self._scale)) if state == "pressed" else 0) + body_h / 2
        text_w, icon_w, gap = self._content_width()
        x = (w - (icon_w + gap + text_w)) / 2
        icon = self._icon_factory(self._icon_name, pal["icon"], self._icon_size) \
            if (self._icon_name and self._icon_factory) else None
        if icon is not None:
            self.itemconfigure(self._icon_item, image=icon, state="normal")
            self.coords(self._icon_item, x + icon_w / 2, cy)
        else:
            self.itemconfigure(self._icon_item, state="hidden")
        self.itemconfigure(self._text_item, text=self._text, fill=pal["text"])
        self.coords(self._text_item, x + icon_w + gap + text_w / 2, cy)

    # ---------------------------------------------------------------- eventos

    def _on_enter(self, _e=None):
        self._hover = True
        self._redraw()

    def _on_leave(self, _e=None):
        self._hover = False
        self._pressed = False
        self._redraw()

    def _on_press(self, _e=None):
        if self._enabled:
            self._pressed = True
            self._redraw()

    def _on_release(self, event):
        if not self._pressed:
            return
        self._pressed = False
        inside = 0 <= event.x < self.winfo_width() and 0 <= event.y < self.winfo_height()
        self._redraw()
        if inside and self._enabled and self._command:
            self._command()
