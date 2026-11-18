"""Interfaz de escritorio de Open Converter (CustomTkinter).

Diseño oscuro azul con tarjetas: lista de imágenes con vista previa a la izquierda,
ajustes con scroll a la derecha y una barra de acción fija abajo. La distribución se
adapta al tamaño de la ventana, recuerda las últimas preferencias y acepta arrastrar
y soltar archivos y carpetas.
"""

import ctypes
import json
import os
import re
import sys as _sys
import threading
import tkinter as tk
import webbrowser
import tkinter.font as tkfont
from tkinter import filedialog, messagebox, ttk

import customtkinter as ctk
from PIL import Image, ImageDraw, ImageFont, ImageOps, ImageTk

from ..core.converter import Converter
from ..i18n import get_language, set_language, t
from ..platform_utils import IS_MAC, IS_WINDOWS, command_modifier, config_dir, font_candidates, open_path
from ..presets.defaults import PRESETS
from .gradient_button import GradientButton
from .vector_icons import draw_icon
from .win_frame import EDGE_CURSORS, FramelessWindow, apply_native_dark_caption

# ---------- Paleta (los mismos colores de siempre + tonos derivados) ----------
BG = "#0b1020"
PANEL = "#111827"
CARD = "#1a2236"
CARD_HOVER = "#232e48"
INPUT = "#1e2a44"
ACCENT = "#3b82f6"
ACCENT_HOVER = "#2563eb"
ACCENT_SOFT = "#1d4ed8"
ACCENT_TINT = "#172554"
ACCENT_TINT_HOVER = "#1e3a8a"
ACCENT_LIGHT = "#93c5fd"
TEXT = "#f1f5f9"
TEXT_SOFT = "#cbd5e1"
MUTED = "#94a3b8"
SUBTLE = "#64748b"
DISABLED = "#475569"
BORDER = "#2a3a5c"
DIVIDER = "#1c2742"
SUCCESS = "#22c55e"
SUCCESS_LIGHT = "#86efac"
DANGER = "#ef4444"
DANGER_LIGHT = "#fca5a5"
DANGER_TINT = "#3a1620"
DANGER_TINT_HOVER = "#4c1d27"
POPOVER_KEY = "#010203"  # color que Windows vuelve transparente (esquinas redondeadas de menús)


AUTHOR_NAME = "MacrosS"
AUTHOR_URL = "https://www.linkedin.com/in/felipelucero/"

# Formatos que usan el control de calidad al guardar (ver adapters/pillow_adapter.py y heif_adapter.py)
LOSSY_FORMATS = {"jpeg", "webp", "avif", "heif", "jpeg2000"}
# Formatos que guardan EXIF y perfil de color (ver core/metadata.py)
METADATA_FORMATS = {"jpeg", "mpo", "webp", "png", "tiff", "avif", "heif"}
POPULAR_FORMATS = ["webp", "jpeg", "png", "avif", "heif", "gif", "tiff", "bmp", "ico"]
FORMAT_LABELS = {"jpeg": "JPG", "jpeg2000": "JP2"}
OUTPUT_EXT = {"jpeg": "jpg", "jpeg2000": "jp2"}
# Pillow gira en sentido antihorario: los valores negativos giran a la derecha.
ROTATIONS = ["0", "-90", "90", "180", "-45", "45", "-135", "135"]

LABEL_W = 84          # ancho de la columna de etiquetas del panel de ajustes (px lógicos)
THUMB_W, THUMB_H = 168, 112
ICON_GLYPHS = {
    "add": "\uE710", "folder": "\uE8B7", "folder_open": "\uE838", "remove": "\uE738",
    "clear": "\uE74D", "check": "\uE73E", "error": "\uE783", "chevron": "\uE70D",
    "convert": "\uE8AB", "stop": "\uE71A",
    # Botones de la barra de t\u00EDtulo
    "win_min": "\uE921", "win_max": "\uE922", "win_restore": "\uE923", "win_close": "\uE8BB",
}


# ---------- Utilidades ----------

def _normalize_dropped_paths(root, data):
    out = []
    if not data:
        return out
    try:
        parts = root.tk.splitlist(data)
        for p in parts:
            out.append(str(p))
        if out:
            return out
    except Exception:
        pass
    s = data.strip()
    for m in re.finditer(r"\{([^}]*)\}|(\S+)", s):
        p = m.group(1) if m.group(1) is not None else m.group(2)
        if p:
            out.append(p)
    return out


def _human_size(n):
    if n is None:
        return "—"
    size = float(n)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            txt = f"{int(size)} {unit}" if unit == "B" else f"{size:.1f} {unit}"
            return txt.replace(".", ",") if get_language() == "es" else txt
        size /= 1024
    return f"{n} B"


def _settings_path():
    return os.path.join(config_dir(), "settings.json")


def _load_settings():
    try:
        with open(_settings_path(), "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _icon_font_path():
    if not IS_WINDOWS:
        return None  # fuera de Windows los íconos se dibujan (vector_icons.py)
    fonts = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts")
    for name in ("SegoeIcons.ttf", "segmdl2.ttf"):
        p = os.path.join(fonts, name)
        if os.path.exists(p):
            return p
    return None


def _checker(w, h, cell):
    """Fondo de cuadros para mostrar la transparencia en la vista previa."""
    img = Image.new("RGB", (w, h), "#1f2940")
    d = ImageDraw.Draw(img)
    cell = max(2, cell)
    for y in range(0, h, cell):
        start = cell if (y // cell) % 2 else 0
        for x in range(start, w, cell * 2):
            d.rectangle([x, y, x + cell - 1, y + cell - 1], fill="#28344f")
    return img


def _walk(widget):
    stack = [widget]
    while stack:
        w = stack.pop()
        yield w
        try:
            stack.extend(w.winfo_children())
        except Exception:
            pass


def _bind_raw(widget, sequence, func):
    """Enlaza un evento en el widget y todos sus hijos (una sola vez por widget Tk real)."""
    for w in _walk(widget):
        try:
            tk.Misc.bind(w, sequence, func, "+")
        except Exception:
            pass


def _set_cursor(widget, cursor="hand2"):
    for w in _walk(widget):
        try:
            w.tk.call(w._w, "configure", "-cursor", cursor)
        except Exception:
            pass


def _pointer_inside(widget):
    try:
        x, y = widget.winfo_pointerxy()
        wx, wy = widget.winfo_rootx(), widget.winfo_rooty()
        return wx <= x < wx + widget.winfo_width() and wy <= y < wy + widget.winfo_height()
    except Exception:
        return False


def _path_inside(path, ancestor):
    p, a = str(path), str(ancestor)
    return p == a or p.startswith(a + ".")


class SelectBox(ctk.CTkFrame):
    """Campo desplegable: texto a la izquierda, flecha a la derecha y estado hover."""

    def __init__(self, master, *, font, chevron, command, height=34):
        super().__init__(master, width=120, height=height, fg_color=INPUT, border_width=1,
                         border_color=BORDER, corner_radius=10)
        self.grid_propagate(False)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self._command = command
        self._enabled = True
        self._label = ctk.CTkLabel(self, text="", font=font, text_color=TEXT, anchor="w",
                                   height=height - 8)
        self._label.grid(row=0, column=0, sticky="ew", padx=(12, 4))
        self._arrow = ctk.CTkLabel(self, text="" if chevron else "▾", image=chevron,
                                   text_color=MUTED, width=16, height=height - 8)
        self._arrow.grid(row=0, column=1, padx=(0, 10))
        _bind_raw(self, "<Button-1>", self._on_click)
        _bind_raw(self, "<Enter>", self._on_enter)
        _bind_raw(self, "<Leave>", self._on_leave)
        _set_cursor(self)

    def set_text(self, text):
        self._label.configure(text=text)

    def set_enabled(self, enabled):
        self._enabled = enabled
        self._label.configure(text_color=TEXT if enabled else DISABLED)

    def _on_click(self, _e=None):
        if self._enabled and self._command:
            self._command()

    def _on_enter(self, _e=None):
        if self._enabled:
            self.configure(fg_color=CARD_HOVER)

    def _on_leave(self, _e=None):
        if not _pointer_inside(self):
            self.configure(fg_color=INPUT)


class App:
    def __init__(self, root):
        self.root = root
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        # Barra de título propia: la ventana se crea sin el marco de Windows (antes de mostrarse)
        self.frame = None
        self._edge = 0
        self._last_title_press = None
        self._max_state = None
        self._frameless = FramelessWindow.supported()
        if self._frameless:
            try:
                root.withdraw()
                root.overrideredirect(True)
            except Exception:
                self._frameless = False

        self.conv = Converter()
        self.cancel_flag = threading.Event()
        self.worker = None
        self.dnd_enabled = hasattr(root, "drop_target_register")
        self._root_is_ctk = isinstance(root, ctk.CTk)

        # Estado que sobrevive al cambio de idioma (la interfaz se reconstruye, los datos no)
        self.files = []
        self._file_set = set()
        self._sizes = {}
        self._row_status = {}
        self._errors = []
        self._result = None
        self._running = False
        self._status_text = ""
        self._progress_value = 0.0
        self._popover = None
        self._popover_anchor = None
        self._layout_job = None
        self._compact = None
        self._applying_preset = False
        self._entries = {}
        self._hints = []
        self._thumb_cache = {}
        self._thumb_photo = None
        self._preview_path = None
        self._icon_cache = {}
        self._logo_cache = {}
        self._last_dir = None
        self._formats = self.conv.supported_output_formats() or ["png"]
        self._input_exts = sorted({e.lower() for f in self.conv.supported_formats()
                                   for e in f.get("extensions", [])})

        saved = _load_settings()
        set_language(saved.get("lang", get_language()))
        fmt = saved.get("format", "webp")
        if fmt not in self._formats:
            fmt = "webp" if "webp" in self._formats else self._formats[0]
        try:
            quality = min(100, max(1, int(saved.get("quality", 85))))
        except Exception:
            quality = 85
        meta = saved.get("metadata", "preserve")
        if meta not in ("preserve", "strip", "selective"):
            meta = "preserve"

        self.output_var = tk.StringVar(value=saved.get("output", ""))
        self.format_var = tk.StringVar(value=fmt)
        self.quality_var = tk.IntVar(value=quality)
        self.preset_var = tk.StringVar(value="")
        self.width_var = tk.StringVar(value="")
        self.height_var = tk.StringVar(value="")
        self.fit_var = tk.StringVar(value="inside")
        self.rotate_var = tk.StringVar(value="0")
        self.flip_var = tk.StringVar(value="none")
        self.gray_var = tk.BooleanVar(value=False)
        self.meta_var = tk.StringVar(value=meta)

        self.output_var.trace_add("write", lambda *a: (self._sync_entry("output"), self._refresh_buttons()))
        self.format_var.trace_add("write", lambda *a: (self._preset_field_changed(), self._refresh_format_ui(),
                                                       self._refresh_meta_ui(), self._refresh_status()))
        self.quality_var.trace_add("write", lambda *a: (self._preset_field_changed(), self._refresh_quality_label()))
        self.width_var.trace_add("write", lambda *a: (self._sync_entry("width"), self._preset_field_changed(), self._refresh_fit_ui()))
        self.height_var.trace_add("write", lambda *a: (self._sync_entry("height"), self._preset_field_changed(), self._refresh_fit_ui()))
        self.fit_var.trace_add("write", lambda *a: (self._preset_field_changed(), self._refresh_fit_ui()))
        self.meta_var.trace_add("write", lambda *a: (self._preset_field_changed(), self._refresh_meta_ui()))
        self.rotate_var.trace_add("write", lambda *a: self._refresh_rotate_ui())
        self.flip_var.trace_add("write", lambda *a: self._refresh_flip_ui())

        self.scale = self._detect_scale()
        self._setup_fonts()
        self._setup_window()
        self._setup_tree_style()
        self._make_containers()
        self._build()
        self._bind_events()
        if self._frameless:
            self._install_frame()

    def _install_frame(self):
        """Quita la barra de Windows; si no se puede, usa la nativa con los colores del programa."""
        r = self.root
        try:
            r.attributes("-alpha", 0.0)  # evita parpadeos mientras se cambia el marco
        except Exception:
            pass
        r.deiconify()
        r.update_idletasks()
        frame = FramelessWindow(r, border_px=self.px(6))
        if frame.install(border_color=BORDER):
            self.frame = frame
            r.withdraw()      # ocultar y mostrar para que aparezca en la barra de tareas
            r.deiconify()
        else:
            self._frameless = False
            r.overrideredirect(False)
            self._build()
            apply_native_dark_caption(r, PANEL, BORDER)
        try:
            r.attributes("-alpha", 1.0)
        except Exception:
            pass
        self._refresh_max_icon()

    # ------------------------------------------------------------------ base

    def px(self, n):
        return int(round(n * self.scale))

    def _detect_scale(self):
        try:
            return float(ctk.ScalingTracker.get_window_dpi_scaling(self.root)
                         * ctk.ScalingTracker.widget_scaling)
        except Exception:
            return 1.0

    def _setup_fonts(self):
        try:
            families = set(tkfont.families(self.root))
        except Exception:
            families = set()
        normales, seminegritas = font_candidates()
        base = next((n for n in normales if n in families), normales[-1])
        semi = next((n for n in seminegritas if n in families), base)
        # Solo Segoe UI tiene un peso seminegrita propio; en el resto se usa la negrita normal
        semi_weight = "normal" if semi == "Segoe UI Semibold" else "bold"
        self._font_base, self._font_semi = base, semi

        def f(size, strong=False):
            return ctk.CTkFont(family=semi if strong else base, size=size,
                               weight=semi_weight if strong else "normal")

        self.f_title = f(18, True)
        self.f_h2 = f(15, True)
        self.f_body = f(13)
        self.f_body_semi = f(13, True)
        self.f_small = f(12)
        self.f_small_semi = f(12, True)
        self.f_caption = f(11)
        self.f_section = f(11, True)
        self.f_button = f(14, True)

        # Fuentes de Tk (en píxeles ya escalados) para los botones 3D dibujados en Canvas
        def tf(size):
            return tkfont.Font(root=self.root, family=semi, size=-self.px(size), weight=semi_weight)

        self.tf_button = tf(14)
        self.tf_body = tf(13)
        self.tf_small = tf(12)
        self.tf_caption = tf(11)

    def _setup_window(self):
        r = self.root
        r.title(t("app_title"))
        try:
            r.configure(fg_color=BG)
        except Exception:
            try:
                r.configure(bg=BG)
            except Exception:
                pass
        sw, sh = r.winfo_screenwidth(), r.winfo_screenheight()
        w = min(self.px(1140), int(sw * 0.92))
        h = min(self.px(780), int(sh * 0.86))
        x, y = max(0, (sw - w) // 2), max(0, (sh - h) // 2 - self.px(20))
        min_w, min_h = min(self.px(800), w), min(self.px(560), h)
        if self._root_is_ctk:  # CTk escala por su cuenta ancho y alto
            s = self.scale or 1
            r.geometry(f"{round(w / s)}x{round(h / s)}+{x}+{y}")
            r.minsize(round(min_w / s), round(min_h / s))
        else:
            r.geometry(f"{w}x{h}+{x}+{y}")
            r.minsize(min_w, min_h)
        r.protocol("WM_DELETE_WINDOW", self._on_close)

    def _setup_tree_style(self):
        style = ttk.Style(self.root)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("OC.Treeview", background=INPUT, fieldbackground=INPUT, foreground=TEXT_SOFT,
                        bordercolor=INPUT, lightcolor=INPUT, darkcolor=INPUT, borderwidth=0,
                        relief="flat", rowheight=self.px(30), font=(self._font_base, 10))
        style.map("OC.Treeview", background=[("selected", ACCENT_SOFT)],
                  foreground=[("selected", "#ffffff")])
        style.configure("OC.Treeview.Heading", background=INPUT, foreground=SUBTLE, bordercolor=INPUT,
                        lightcolor=INPUT, darkcolor=INPUT, borderwidth=0, relief="flat",
                        font=(self._font_semi, 8), padding=(self.px(6), self.px(6)))
        style.map("OC.Treeview.Heading", background=[("active", INPUT), ("pressed", INPUT)],
                  foreground=[("active", MUTED)], relief=[("pressed", "flat")])
        style.layout("OC.Treeview", [("Treeview.treearea", {"sticky": "nswe"})])

    def _make_containers(self):
        r = self.root
        r.grid_columnconfigure(0, weight=1)
        r.grid_rowconfigure(2, weight=1)

        self.header = ctk.CTkFrame(r, fg_color=PANEL, corner_radius=0)
        self.header.grid(row=0, column=0, sticky="ew")
        tk.Frame(r, height=1, bg=DIVIDER).grid(row=1, column=0, sticky="ew")

        self.body = tk.Frame(r, bg=BG)
        self.body.grid(row=2, column=0, sticky="nsew", padx=self.px(20), pady=self.px(16))
        self.body.grid_rowconfigure(0, weight=1)
        self.body.grid_columnconfigure(0, weight=1)
        self.body.grid_columnconfigure(1, weight=0, minsize=self.px(380))

        self.files_card = ctk.CTkFrame(self.body, fg_color=PANEL, corner_radius=16,
                                       border_width=1, border_color=BORDER)
        self.files_card.grid(row=0, column=0, sticky="nsew", padx=(0, 14))

        self.settings = ctk.CTkScrollableFrame(
            self.body, width=300, fg_color=PANEL, corner_radius=16, border_width=1,
            border_color=BORDER, scrollbar_fg_color=PANEL, scrollbar_button_color=BORDER,
            scrollbar_button_hover_color=SUBTLE)
        self.settings.grid(row=0, column=1, sticky="nsew")
        try:
            self.settings.bind("<Configure>", lambda e: self._schedule_scrollbar_sync(), add="+")
            self.settings._parent_canvas.bind("<Configure>", lambda e: self._schedule_scrollbar_sync(), add="+")
        except Exception:
            pass

        tk.Frame(r, height=1, bg=DIVIDER).grid(row=3, column=0, sticky="ew")
        self.actionbar = ctk.CTkFrame(r, fg_color=PANEL, corner_radius=0)
        self.actionbar.grid(row=4, column=0, sticky="ew")

    def _bind_events(self):
        r = self.root
        r.bind("<Button-1>", self._on_root_click, add="+")
        r.bind("<Motion>", self._on_root_motion, add="+")
        r.bind("<Configure>", self._on_root_configure, add="+")
        r.bind("<Escape>", lambda e: self._close_popover(), add="+")
        mod = command_modifier()
        r.bind(f"<{mod}-o>", lambda e: self._add_files(), add="+")
        r.bind(f"<{mod}-O>", lambda e: self._add_folder(), add="+")
        r.bind(f"<{mod}-Return>", lambda e: self._start_convert(), add="+")
        self.body.bind("<Configure>", lambda e: self._schedule_layout(), add="+")
        if self.dnd_enabled:
            try:
                r.drop_target_register("DND_Files")
                r.dnd_bind("<<Drop>>", self._on_drop_files)
                r.dnd_bind("<<DropEnter>>", lambda e: self._drop_highlight(True, e))
                r.dnd_bind("<<DropLeave>>", lambda e: self._drop_highlight(False, e))
            except Exception:
                self.dnd_enabled = False

    # --------------------------------------------------------------- recursos

    def _glyph(self, name, color, size):
        """Ícono de la fuente Segoe Fluent/MDL2 como imagen PIL del tamaño real en píxeles."""
        path = _icon_font_path()
        if not path:
            return draw_icon(name, color, max(8, self.px(size)))
        if name not in ICON_GLYPHS:
            return None
        try:
            px = max(8, self.px(size))
            font = ImageFont.truetype(path, px)
            img = Image.new("RGBA", (px, px), (0, 0, 0, 0))
            ImageDraw.Draw(img).text((px / 2, px / 2), ICON_GLYPHS[name], font=font, fill=color, anchor="mm")
            return img
        except Exception:
            return None

    def _icon(self, name, color=TEXT, size=16):
        """Ícono para widgets de CustomTkinter."""
        key = (name, color, size)
        if key not in self._icon_cache:
            img = self._glyph(name, color, size)
            self._icon_cache[key] = ctk.CTkImage(light_image=img, dark_image=img, size=(size, size)) if img else None
        return self._icon_cache[key]

    def _icon_photo(self, name, color=TEXT, size=16):
        """Ícono para los botones 3D (Canvas)."""
        key = ("photo", name, color, size)
        if key not in self._icon_cache:
            img = self._glyph(name, color, size)
            self._icon_cache[key] = ImageTk.PhotoImage(img, master=self.root) if img else None
        return self._icon_cache[key]

    def _logo(self, size):
        if size in self._logo_cache:
            return self._logo_cache[size]
        img = None
        for p in (_asset_path("logo.png"), _icon_path()):
            if not p:
                continue
            try:
                pil = Image.open(p).convert("RGBA")
                img = ctk.CTkImage(light_image=pil, dark_image=pil, size=(size, size))
                break
            except Exception:
                img = None
        self._logo_cache[size] = img
        return img

    def _fmt_label(self, fmt):
        return FORMAT_LABELS.get(fmt, fmt.upper())

    # ------------------------------------------------------------ construcción

    @staticmethod
    def _clear(container):
        internal = getattr(container, "_canvas", None)
        for w in container.winfo_children():
            if w is internal:
                continue
            w.destroy()

    def _build(self):
        self._close_popover()
        self._entries = {}
        self._hints = []
        self._preview_path = None
        self._tree_scroll_on = None
        for c in (self.header, self.files_card, self.settings, self.actionbar):
            self._clear(c)
        self.root.title(t("app_title"))
        self._build_header()
        self._build_files()
        self._build_settings()
        self._build_actionbar()
        self._fill_tree()
        self._refresh_all()
        try:
            self.settings._parent_canvas.yview_moveto(0)
        except Exception:
            pass
        self._compact = None
        self._schedule_layout()

    def _build_header(self):
        h = self.header
        h.grid_columnconfigure(2, weight=1)
        logo = self._logo(34)
        if logo is not None:
            ctk.CTkLabel(h, image=logo, text="").grid(row=0, column=0, rowspan=2, padx=(20, 12), pady=12)
        title_pad = 0 if logo is not None else 20
        ctk.CTkLabel(h, text="Open Converter", font=self.f_title, text_color=TEXT, anchor="w",
                     height=24).grid(row=0, column=1, sticky="sw", padx=(title_pad, 0), pady=(12, 0))
        ctk.CTkLabel(h, text=t("subtitle"), font=self.f_small, text_color=MUTED, anchor="w",
                     height=18).grid(row=1, column=1, sticky="nw", padx=(title_pad, 0), pady=(0, 12))
        self.credit_lbl = self._build_credit(h)
        self.credit_lbl.grid(row=0, column=3, rowspan=2, padx=(0, 16))
        self.lang_seg = ctk.CTkSegmentedButton(
            h, values=["ES", "EN"], command=self._on_lang, font=self.f_small_semi, height=30,
            width=96, corner_radius=8, border_width=2, fg_color=CARD, selected_color=ACCENT_SOFT,
            selected_hover_color=ACCENT_HOVER, unselected_color=CARD, unselected_hover_color=CARD_HOVER,
            text_color=TEXT, text_color_disabled=SUBTLE)
        self.lang_seg.set(get_language().upper())
        self.lang_seg.grid(row=0, column=4, rowspan=2, padx=(0, 12 if self._frameless else 20))

        if self._frameless:
            tk.Frame(h, width=1, height=self.px(24), bg=DIVIDER).grid(row=0, column=5, rowspan=2, padx=(0, 8))
            controls = ctk.CTkFrame(h, fg_color="transparent")
            controls.grid(row=0, column=6, rowspan=2, padx=(0, 10))
            self.btn_win_min = self._chrome_button(controls, "win_min", lambda: self.frame and self.frame.minimize())
            self.btn_win_max = self._chrome_button(controls, "win_max", self._toggle_maximize)
            self.btn_win_close = self._chrome_button(controls, "win_close", self._on_close, danger=True)
            for b in (self.btn_win_min, self.btn_win_max, self.btn_win_close):
                b.pack(side="left", padx=2)
            # Zona de arrastre: el fondo de la barra, el logo, el título y el crédito
            targets = [h]
            if getattr(h, "_canvas", None) is not None:
                targets.append(h._canvas)
            for label in h.grid_slaves():
                if isinstance(label, ctk.CTkLabel):  # logo, título, subtítulo y crédito
                    targets.extend(_walk(label))
            seen = set()
            for target in targets:  # cada widget una sola vez (si no, un clic contaría como doble)
                if str(target) in seen:
                    continue
                seen.add(str(target))
                try:
                    tk.Misc.bind(target, "<ButtonPress-1>", self._on_title_press, "+")
                    tk.Misc.bind(target, "<B1-Motion>", self._on_title_drag, "+")
                    tk.Misc.bind(target, "<ButtonRelease-1>", self._on_title_release, "+")
                except Exception:
                    pass
            self._max_state = None
            self._refresh_max_icon()

    def _build_credit(self, parent):
        """"Diseñado y desarrollado por MacrosS." con el nombre como enlace a LinkedIn."""
        line = ctk.CTkFrame(parent, fg_color="transparent")
        ctk.CTkLabel(line, text=t("designed_by"), font=self.f_caption, text_color=SUBTLE,
                     height=18).pack(side="left")
        link_font = ctk.CTkFont(family=self._font_semi, size=11)
        link_font_hover = ctk.CTkFont(family=self._font_semi, size=11, underline=True)
        author = ctk.CTkLabel(line, text=AUTHOR_NAME, font=link_font, text_color=ACCENT_LIGHT, height=18)
        author.pack(side="left", padx=(4, 0))
        ctk.CTkLabel(line, text=".", font=self.f_caption, text_color=SUBTLE, height=18).pack(side="left")
        _set_cursor(author)
        _bind_raw(author, "<Button-1>", lambda e: self._open_author_profile())
        _bind_raw(author, "<Enter>", lambda e: author.configure(font=link_font_hover, text_color="#bfdbfe"))
        _bind_raw(author, "<Leave>", lambda e: author.configure(font=link_font, text_color=ACCENT_LIGHT))
        self.author_link = author
        return line

    def _open_author_profile(self):
        self._close_popover()
        try:
            webbrowser.open(AUTHOR_URL, new=2)
        except Exception:
            pass

    def _chrome_button(self, parent, icon_name, command, danger=False):
        normal = self._icon(icon_name, TEXT_SOFT, 11)
        btn = ctk.CTkButton(parent, text="" if normal else icon_name, image=normal, width=40, height=32,
                            corner_radius=8, fg_color="transparent",
                            hover_color=DANGER if danger else CARD_HOVER, command=command)
        if danger:
            hover = self._icon(icon_name, "#ffffff", 11)
            btn.bind("<Enter>", lambda e: btn.configure(image=hover), add="+")
            btn.bind("<Leave>", lambda e: btn.configure(image=normal), add="+")
        return btn

    def _toggle_maximize(self):
        if self.frame is not None:
            self._close_popover()
            self.frame.toggle_maximize()

    def _refresh_max_icon(self):
        if self.frame is None or not hasattr(self, "btn_win_max"):
            return
        maximized = self.frame.is_maximized()
        if maximized == self._max_state:
            return
        self._max_state = maximized
        try:
            self.btn_win_max.configure(image=self._icon("win_restore" if maximized else "win_max", TEXT_SOFT, 11))
        except Exception:
            pass

    def _on_title_press(self, event):
        """Clic en la barra propia. El arrastre empieza al mover el mouse (_on_title_drag),
        así los clics llegan limpios y el doble clic maximiza o restaura."""
        if self.frame is None:
            return None
        if self.frame.edge_at(event.x_root, event.y_root):
            return None  # es un borde: lo maneja _on_root_click (redimensionar)
        self._close_popover()
        self._release_entry_focus(event)
        self._title_dragging = False
        last = self._last_title_press
        try:
            double_ms = ctypes.windll.user32.GetDoubleClickTime()
        except Exception:
            double_ms = 500
        if last and 0 <= event.time - last[0] <= double_ms \
                and abs(event.x_root - last[1]) < 5 and abs(event.y_root - last[2]) < 5:
            # Windows ignora maximizar mientras el botón sigue presionado: se hace al soltar.
            self._last_title_press = None
            self._toggle_on_release = True
            return "break"
        self._last_title_press = (event.time, event.x_root, event.y_root)
        return "break"

    def _on_title_release(self, event):
        if getattr(self, "_toggle_on_release", False):
            self._toggle_on_release = False
            self._toggle_maximize()
            return "break"
        return None

    def _on_title_drag(self, event):
        last = self._last_title_press
        if self.frame is None or last is None or getattr(self, "_title_dragging", False):
            return None
        if abs(event.x_root - last[1]) < 4 and abs(event.y_root - last[2]) < 4:
            return None
        try:  # solo si el botón sigue presionado de verdad
            if not ctypes.windll.user32.GetAsyncKeyState(0x01) & 0x8000:
                return None
        except Exception:
            pass
        self._title_dragging = True
        self._last_title_press = None
        self.frame.begin_move(event.x_root, event.y_root)
        return "break"

    def _on_root_motion(self, event):
        if self.frame is None:
            return
        edge = self.frame.edge_at(event.x_root, event.y_root)
        if edge != self._edge:
            self._edge = edge
            try:
                self.root.configure(cursor=EDGE_CURSORS.get(edge, ""))
            except Exception:
                pass

    def _button(self, parent, text, command, kind="neutral", icon_name=None, height=34, width=0, font=None,
                radius=12, bg=PANEL):
        """Botón con degradado de estilo actual (gui/gradient_button.py)."""
        return GradientButton(parent, text=text, command=command, kind=kind, icon_name=icon_name,
                              height=height, width=width, radius=radius, font=font or self.tf_body, bg=bg,
                              scale=self.scale, icon_factory=self._icon_photo)

    def _build_files(self):
        c = self.files_card
        c.grid_columnconfigure(0, weight=1)
        c.grid_rowconfigure(2, weight=1)

        top = ctk.CTkFrame(c, fg_color="transparent")
        top.grid(row=0, column=0, sticky="ew", padx=18, pady=(16, 10))
        top.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(top, text=t("files_title"), font=self.f_h2, text_color=TEXT,
                     height=24).grid(row=0, column=0, sticky="w")
        self.count_lbl = ctk.CTkLabel(top, text="", font=self.f_small, text_color=MUTED, height=24)
        self.count_lbl.grid(row=0, column=1, sticky="e")

        self.toolbar = ctk.CTkFrame(c, fg_color="transparent")
        self.toolbar.grid(row=1, column=0, sticky="ew", padx=18, pady=(0, 12))
        self.btn_add = self._button(self.toolbar, t("add_files"), self._add_files, "tint", "add")
        self.btn_folder = self._button(self.toolbar, t("add_folder"), self._add_folder, "neutral", "folder")
        self.btn_remove = self._button(self.toolbar, t("remove"), self._remove_selected, "ghost", "remove")
        self.btn_clear = self._button(self.toolbar, t("clear"), self._clear_files, "ghost", "clear")

        self.list_box = ctk.CTkFrame(c, fg_color=INPUT, corner_radius=12, border_width=1, border_color=BORDER)
        self.list_box.grid(row=2, column=0, sticky="nsew", padx=18, pady=(0, 16))
        self.list_box.grid_rowconfigure(0, weight=1)
        self.list_box.grid_columnconfigure(0, weight=1)

        cols = ("name", "type", "size", "status")
        self.tree = ttk.Treeview(self.list_box, style="OC.Treeview", columns=cols, show="headings",
                                 selectmode="extended")
        for col, key in zip(cols, ("col_name", "col_type", "col_size", "col_status")):
            self.tree.heading(col, text=t(key).upper(), anchor="e" if col == "size" else "w")
        self.tree.column("name", anchor="w", stretch=True, minwidth=self.px(120), width=self.px(240))
        self.tree.column("type", anchor="w", stretch=False, width=self.px(64))
        self.tree.column("size", anchor="e", stretch=False, width=self.px(84))
        self.tree.column("status", anchor="w", stretch=False, width=self.px(118))
        self.tree.grid(row=0, column=0, sticky="nsew", padx=(self.px(8), 0), pady=self.px(6))
        self.tree_scroll = ctk.CTkScrollbar(self.list_box, command=self.tree.yview, fg_color=INPUT,
                                            button_color=BORDER, button_hover_color=SUBTLE, width=12)
        self.tree_scroll.grid(row=0, column=1, sticky="ns", padx=(2, 6), pady=8)
        self.tree.configure(yscrollcommand=self._tree_yscroll)
        self.tree.bind("<Configure>", lambda e: self.root.after_idle(self._recheck_tree_scroll), add="+")
        self.tree.tag_configure("ok", foreground=SUCCESS_LIGHT)
        self.tree.tag_configure("fail", foreground=DANGER_LIGHT)
        self.tree.tag_configure("working", foreground=ACCENT_LIGHT)
        self.tree.bind("<<TreeviewSelect>>", lambda e: (self._update_preview(), self._refresh_buttons()))
        self.tree.bind("<Delete>", lambda e: self._remove_selected())
        if IS_MAC:  # en el Mac la tecla de borrar es BackSpace
            self.tree.bind("<BackSpace>", lambda e: self._remove_selected())
        self.tree.bind(f"<{command_modifier()}-a>", self._select_all)
        self.tree.bind("<Double-1>", self._open_row)

        # Estado vacío: zona para soltar o hacer clic
        self.empty = ctk.CTkFrame(self.list_box, fg_color=INPUT, corner_radius=11)
        inner = ctk.CTkFrame(self.empty, fg_color="transparent")
        inner.place(relx=0.5, rely=0.5, anchor="center")
        logo = self._logo(56)
        if logo is not None:
            ctk.CTkLabel(inner, image=logo, text="").pack(pady=(0, 12))
        self.empty_title = ctk.CTkLabel(inner, text=t("empty_title"), font=self.f_h2, text_color=TEXT)
        self.empty_title.pack()
        ctk.CTkLabel(inner, text=t("empty_body"), font=self.f_small, text_color=MUTED, wraplength=290,
                     justify="center").pack(pady=(4, 12))
        ctk.CTkLabel(inner, text=t("empty_formats"), font=self.f_caption, text_color=SUBTLE).pack()
        _bind_raw(self.empty, "<Button-1>", lambda e: self._add_files())
        _bind_raw(self.empty, "<Enter>", lambda e: self._empty_hover(not self.files))
        _bind_raw(self.empty, "<Leave>", lambda e: self._empty_hover(
            not self.files and self.empty.winfo_ismapped() and _pointer_inside(self.empty)))
        _set_cursor(self.empty)

        # Vista previa del archivo seleccionado
        self.preview = ctk.CTkFrame(c, fg_color=CARD, corner_radius=12)
        self.preview.grid_columnconfigure(1, weight=1)
        box = tk.Frame(self.preview, bg=CARD, width=self.px(THUMB_W), height=self.px(THUMB_H))
        box.grid_propagate(False)
        box.pack_propagate(False)
        box.grid(row=0, column=0, padx=self.px(12), pady=self.px(12))
        self.thumb = tk.Label(box, bg=CARD, fg=SUBTLE, bd=0, font=(self._font_semi, 12))
        self.thumb.place(relx=0.5, rely=0.5, anchor="center")
        info = ctk.CTkFrame(self.preview, fg_color="transparent")
        info.grid(row=0, column=1, sticky="nsew", padx=(0, 16), pady=12)
        self.pv_name = ctk.CTkLabel(info, text="", font=self.f_body_semi, text_color=TEXT, anchor="w",
                                    justify="left")
        self.pv_name.pack(anchor="w", fill="x")
        self.pv_meta = ctk.CTkLabel(info, text="", font=self.f_small, text_color=MUTED, anchor="w",
                                    justify="left", height=20)
        self.pv_meta.pack(anchor="w", fill="x")
        self.pv_path = ctk.CTkLabel(info, text="", font=self.f_caption, text_color=SUBTLE, anchor="w",
                                    justify="left")
        self.pv_path.pack(anchor="w", fill="x", pady=(4, 0))
        info.bind("<Configure>", self._wrap_preview_labels, add="+")

    def _section(self, title, help_cmd=None):
        s = self.settings
        if self._srow:
            tk.Frame(s, height=1, bg=DIVIDER).grid(row=self._srow, column=0, sticky="ew",
                                                   padx=self.px(18), pady=(self.px(6), 0))
            self._srow += 1
        hdr = ctk.CTkFrame(s, fg_color="transparent")
        hdr.grid(row=self._srow, column=0, sticky="ew", padx=18, pady=(16 if self._srow == 0 else 14, 10))
        self._srow += 1
        ctk.CTkLabel(hdr, text=title.upper(), font=self.f_section, text_color=MUTED, height=22).pack(side="left")
        if help_cmd is not None:
            btn = self._button(hdr, "?", None, "neutral", height=24, width=24, radius=12, font=self.tf_caption)
            btn.configure(command=lambda b=btn: help_cmd(b))
            btn.pack(side="left", padx=(8, 0))
        body = ctk.CTkFrame(s, fg_color="transparent")
        body.grid(row=self._srow, column=0, sticky="ew", padx=18, pady=(0, 6))
        self._srow += 1
        body.grid_columnconfigure(0, minsize=self.px(LABEL_W))
        body.grid_columnconfigure(1, weight=1)
        return body

    def _field_label(self, body, row, text):
        ctk.CTkLabel(body, text=text, font=self.f_body, text_color=TEXT_SOFT, anchor="w",
                     height=34).grid(row=row, column=0, sticky="w", pady=(0, 6))

    def _hint(self, body, row, span=False):
        lbl = ctk.CTkLabel(body, text="", font=self.f_caption, text_color=SUBTLE, anchor="w",
                           justify="left", height=16)
        lbl.grid(row=row, column=0 if span else 1, columnspan=2 if span else 1, sticky="ew", pady=(0, 10))
        self._hints.append((lbl, span))
        return lbl

    @staticmethod
    def _set_hint(lbl, text):
        lbl.configure(text=text)
        if text:
            lbl.grid()
        else:
            lbl.grid_remove()

    def _entry(self, parent, var, placeholder, key, width=120, digits=False, justify="left"):
        e = ctk.CTkEntry(parent, width=width, height=34, corner_radius=10, border_width=1,
                         fg_color=INPUT, border_color=BORDER, text_color=TEXT, font=self.f_body,
                         placeholder_text=placeholder, placeholder_text_color=SUBTLE, justify=justify)
        if var.get():
            e.insert(0, var.get())

        def push(_e=None):
            val = e.get()
            if var.get() != val:
                var.set(val)

        e.bind("<KeyRelease>", push, add="+")
        e.bind("<Return>", lambda _e: self.root.focus_set(), add="+")   # Enter o Esc: terminar de escribir
        e.bind("<Escape>", lambda _e: self.root.focus_set(), add="+")
        e.bind("<FocusIn>", lambda _e: e.configure(border_color=ACCENT), add="+")
        e.bind("<FocusOut>", lambda _e: (push(), e.configure(border_color=BORDER)), add="+")
        if digits:
            def valid(proposed):
                return proposed == "" or proposed == placeholder or (proposed.isdigit() and len(proposed) <= 5)
            try:
                e._entry.configure(validate="key", validatecommand=(e.register(valid), "%P"))
            except Exception:
                pass
        self._entries[key] = (e, var)
        return e

    def _segmented(self, parent, var, options, height=32):
        labels = [lbl for _, lbl in options]
        to_value = {lbl: val for val, lbl in options}

        def on_pick(lbl):
            var.set(to_value[lbl])

        seg = ctk.CTkSegmentedButton(
            parent, values=labels, command=on_pick, font=self.f_small_semi, height=height,
            corner_radius=10, border_width=3, fg_color=INPUT, selected_color=ACCENT_SOFT,
            selected_hover_color=ACCENT_HOVER, unselected_color=INPUT, unselected_hover_color=CARD_HOVER,
            text_color=TEXT, text_color_disabled=DISABLED)
        seg._oc_options = dict(options)
        return seg

    @staticmethod
    def _seg_select(seg, value):
        try:
            seg.set(seg._oc_options.get(value, ""))
        except Exception:
            pass

    def _build_settings(self):
        s = self.settings
        s.grid_columnconfigure(0, weight=1)
        self._srow = 0
        chevron = self._icon("chevron", MUTED, 12)

        # Destino
        body = self._section(t("section_output"))
        self.out_row = ctk.CTkFrame(body, fg_color="transparent")
        self.out_row.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 6))
        self.out_row.grid_columnconfigure(0, weight=1)
        self.out_entry = self._entry(self.out_row, self.output_var, t("output_placeholder"), "output")
        self.out_entry.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        entry = self.out_entry
        entry.after(100, lambda: entry.winfo_exists() and entry._entry.xview_moveto(1.0))
        self.btn_browse = self._button(self.out_row, "", self._pick_output, "neutral", "folder_open", width=38)
        self.btn_browse.grid(row=0, column=1)
        self._set_hint(self._hint(body, 1, span=True), t("drop_output_hint"))
        if self.dnd_enabled:
            try:
                self.out_row.drop_target_register("DND_Files")
                self.out_row.dnd_bind("<<Drop>>", self._on_drop_output)
                self.out_row.dnd_bind("<<DropEnter>>", lambda e: self._drop_output_highlight(True, e))
                self.out_row.dnd_bind("<<DropLeave>>", lambda e: self._drop_output_highlight(False, e))
            except Exception:
                pass

        # Formato y calidad
        body = self._section(t("section_format"))
        self._field_label(body, 0, t("format"))
        self.fmt_select = SelectBox(body, font=self.f_body_semi, chevron=chevron, command=self._open_format_menu)
        self.fmt_select.grid(row=0, column=1, sticky="ew", pady=(0, 6))
        self.fmt_hint = self._hint(body, 1)
        self._field_label(body, 2, t("quality"))
        qrow = ctk.CTkFrame(body, fg_color="transparent", height=34)
        qrow.grid(row=2, column=1, sticky="ew", pady=(0, 6))
        qrow.grid_columnconfigure(0, weight=1)
        self.q_slider = ctk.CTkSlider(qrow, from_=1, to=100, number_of_steps=99, variable=self.quality_var,
                                      height=18, fg_color=INPUT, progress_color=ACCENT, button_color=ACCENT,
                                      button_hover_color=ACCENT_HOVER)
        self.q_slider.grid(row=0, column=0, sticky="ew", pady=8)
        self.q_value = ctk.CTkLabel(qrow, text="", width=36, font=self.f_body_semi, text_color=TEXT, anchor="e")
        self.q_value.grid(row=0, column=1, padx=(6, 0))
        self.q_hint = self._hint(body, 3)
        self._field_label(body, 4, t("preset"))
        self.preset_select = SelectBox(body, font=self.f_body, chevron=chevron, command=self._open_preset_menu)
        self.preset_select.grid(row=4, column=1, sticky="ew", pady=(0, 6))
        self.preset_hint = self._hint(body, 5)

        # Tamaño y orientación
        body = self._section(t("section_transforms"))
        self._field_label(body, 0, t("size"))
        srow = ctk.CTkFrame(body, fg_color="transparent")
        srow.grid(row=0, column=1, sticky="ew", pady=(0, 6))
        srow.grid_columnconfigure((0, 2), weight=1)
        self._entry(srow, self.width_var, t("width"), "width", width=60, digits=True,
                    justify="center").grid(row=0, column=0, sticky="ew")
        ctk.CTkLabel(srow, text="×", font=self.f_body, text_color=SUBTLE, width=20).grid(row=0, column=1)
        self._entry(srow, self.height_var, t("height"), "height", width=60, digits=True,
                    justify="center").grid(row=0, column=2, sticky="ew")
        ctk.CTkLabel(srow, text="px", font=self.f_small, text_color=SUBTLE, width=24).grid(row=0, column=3, padx=(6, 0))
        self._set_hint(self._hint(body, 1), t("size_hint"))
        self._field_label(body, 2, t("fit"))
        frow = ctk.CTkFrame(body, fg_color="transparent")
        frow.grid(row=2, column=1, sticky="ew", pady=(0, 6))
        frow.grid_columnconfigure(0, weight=1)
        self.seg_fit = self._segmented(frow, self.fit_var, [("inside", t("fit_inside")), ("cover", t("fit_cover")),
                                                            ("exact", t("fit_exact"))])
        self.seg_fit.grid(row=0, column=0, sticky="ew")
        help_fit = self._button(frow, "?", None, "neutral", height=28, width=28, radius=14, font=self.tf_caption)
        help_fit.configure(command=lambda b=help_fit: self._open_fit_help(b))
        help_fit.grid(row=0, column=1, padx=(8, 0))
        self.fit_hint = self._hint(body, 3)
        self._field_label(body, 4, t("rotate"))
        self.rot_select = SelectBox(body, font=self.f_body, chevron=chevron, command=self._open_rotate_menu)
        self.rot_select.grid(row=4, column=1, sticky="ew", pady=(0, 10))
        self._field_label(body, 5, t("flip"))
        self.seg_flip = self._segmented(body, self.flip_var, [("none", t("flip_none")),
                                                              ("horizontal", t("flip_horizontal")),
                                                              ("vertical", t("flip_vertical"))])
        self.seg_flip.grid(row=5, column=1, sticky="ew", pady=(0, 10))
        self._field_label(body, 6, t("color"))
        self.gray_switch = ctk.CTkSwitch(body, text=t("grayscale"), variable=self.gray_var, onvalue=True,
                                         offvalue=False, font=self.f_body, text_color=TEXT_SOFT,
                                         fg_color=BORDER, progress_color=ACCENT, button_color="#e2e8f0",
                                         button_hover_color="#ffffff")
        self.gray_switch.grid(row=6, column=1, sticky="w", pady=(0, 8))

        # Metadatos
        body = self._section(t("section_metadata"), help_cmd=self._open_metadata_help)
        self.seg_meta = self._segmented(body, self.meta_var, [("preserve", t("preserve")), ("strip", t("strip")),
                                                              ("selective", t("selective"))])
        self.seg_meta.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 8))
        self.meta_hint = self._hint(body, 1, span=True)
        tk.Frame(s, height=self.px(10), bg=PANEL).grid(row=self._srow, column=0)

    def _build_actionbar(self):
        a = self.actionbar
        a.grid_columnconfigure(0, weight=1)
        left = ctk.CTkFrame(a, fg_color="transparent")
        left.grid(row=0, column=0, sticky="ew", padx=(20, 16), pady=14)
        left.grid_columnconfigure(0, weight=1)
        srow = ctk.CTkFrame(left, fg_color="transparent")
        srow.grid(row=0, column=0, sticky="ew")
        self.status_icon = ctk.CTkLabel(srow, text="", width=18, height=24)
        self.status_lbl = ctk.CTkLabel(srow, text="", font=self.f_body, text_color=TEXT_SOFT, anchor="w", height=24)
        self.status_lbl.pack(side="left")
        self.errors_btn = ctk.CTkButton(srow, text=t("see_errors"), width=0, height=24, corner_radius=8,
                                        fg_color="transparent", hover_color=CARD, text_color=DANGER_LIGHT,
                                        font=self.f_small_semi)
        self.errors_btn.configure(command=lambda: self._show_errors(self.errors_btn))
        self.progress = ctk.CTkProgressBar(left, height=6, corner_radius=3, fg_color=INPUT, progress_color=ACCENT)
        self.progress.grid(row=1, column=0, sticky="ew", pady=(8, 0))
        self.progress.set(0)
        self.btn_open = self._button(a, t("open_folder"), self._open_output, "neutral", "folder_open", height=44)
        self.btn_open.grid(row=0, column=1, padx=(0, 10), pady=14)
        self.btn_convert = self._button(a, t("convert"), self._on_convert_click, "primary", "convert", height=44,
                                        width=230, radius=12, font=self.tf_button)
        self.btn_convert.grid(row=0, column=2, padx=(0, 20), pady=14)

    # ---------------------------------------------------------------- refrescos

    def _refresh_all(self):
        self._refresh_format_ui()
        self._refresh_quality_label()
        self._refresh_preset_ui()
        self._refresh_fit_ui()
        self._refresh_rotate_ui()
        self._refresh_flip_ui()
        self._refresh_meta_ui()
        self._refresh_files_ui()

    def _refresh_files_ui(self):
        if not hasattr(self, "count_lbl"):
            return
        n = len(self.files)
        if n:
            total = sum(v for v in self._sizes.values() if v)
            key = "files_count_one" if n == 1 else "files_count_other"
            self.count_lbl.configure(text=t(key, n=n, size=_human_size(total)))
            self.empty.grid_remove()
            self._empty_hover(False)
        else:
            self.count_lbl.configure(text="")
            self.empty.grid(row=0, column=0, columnspan=2, sticky="nsew", padx=2, pady=2)
            self.empty.lift()
        self._update_preview()
        self._refresh_status()
        self._refresh_buttons()
        self._schedule_layout()

    def _refresh_format_ui(self):
        if not hasattr(self, "fmt_select"):
            return
        fmt = self.format_var.get()
        self.fmt_select.set_text(self._fmt_label(fmt))
        self._set_hint(self.fmt_hint, t("fmt_" + fmt) if ("fmt_" + fmt) != t("fmt_" + fmt) else "")
        lossy = fmt in LOSSY_FORMATS
        self.q_slider.configure(state="normal" if lossy else "disabled",
                                progress_color=ACCENT if lossy else BORDER,
                                button_color=ACCENT if lossy else SUBTLE,
                                button_hover_color=ACCENT_HOVER if lossy else SUBTLE)
        self.q_value.configure(text_color=TEXT if lossy else DISABLED)
        self._set_hint(self.q_hint, t("quality_hint") if lossy else t("quality_na", fmt=self._fmt_label(fmt)))
        self._refresh_quality_label()

    def _refresh_quality_label(self):
        if hasattr(self, "q_value"):
            lossy = self.format_var.get() in LOSSY_FORMATS
            self.q_value.configure(text=str(self.quality_var.get()) if lossy else "—")

    def _preset_desc(self, key):
        p = PRESETS.get(key, {})
        fmt = p.get("format")
        parts = [self._fmt_label(fmt)] if fmt else []
        if "quality" in p and fmt in LOSSY_FORMATS:
            parts.append(t("pd_quality", q=p["quality"]))
        r = p.get("resize") or {}
        w, h = r.get("width"), r.get("height")
        if w and h:
            parts.append(t("pd_box_cover" if r.get("fit") == "cover" else "pd_box", w=w, h=h))
        elif w:
            parts.append(t("pd_width", w=w))
        elif h:
            parts.append(t("pd_height", h=h))
        if p.get("metadata") == "strip":
            parts.append(t("pd_strip"))
        return " · ".join(parts)

    def _refresh_preset_ui(self):
        if not hasattr(self, "preset_select"):
            return
        key = self.preset_var.get()
        if key and key in PRESETS:
            self.preset_select.set_text(t("preset_" + key))
            self._set_hint(self.preset_hint, self._preset_desc(key))
        else:
            self.preset_select.set_text(t("preset_none"))
            self._set_hint(self.preset_hint, t("preset_hint_none"))

    def _refresh_fit_ui(self):
        if not hasattr(self, "seg_fit"):
            return
        self._seg_select(self.seg_fit, self.fit_var.get())
        both = bool(self.width_var.get().strip()) and bool(self.height_var.get().strip())
        self.seg_fit.configure(state="normal" if both else "disabled",
                               selected_color=ACCENT_SOFT if both else BORDER)
        if both:
            self._set_hint(self.fit_hint, t("fit_help_%s_desc" % self.fit_var.get()))
        else:
            self._set_hint(self.fit_hint, t("fit_disabled_hint"))

    def _rot_label(self, value):
        a = int(float(value))
        if a == 0:
            return t("rot_0")
        if abs(a) == 180:
            return t("rot_180")
        return t("rot_cw", d=abs(a)) if a < 0 else t("rot_ccw", d=a)

    def _refresh_rotate_ui(self):
        if hasattr(self, "rot_select"):
            self.rot_select.set_text(self._rot_label(self.rotate_var.get()))

    def _refresh_flip_ui(self):
        if hasattr(self, "seg_flip"):
            self._seg_select(self.seg_flip, self.flip_var.get())

    def _refresh_meta_ui(self):
        if not hasattr(self, "seg_meta"):
            return
        fmt = self.format_var.get()
        meta = self.meta_var.get()
        supported = fmt in METADATA_FORMATS
        self._seg_select(self.seg_meta, meta)
        self.seg_meta.configure(state="normal" if supported else "disabled",
                                selected_color=ACCENT_SOFT if supported else BORDER)
        if not supported:
            hint = t("meta_unsupported", fmt=self._fmt_label(fmt))
        elif fmt == "tiff" and meta != "strip":
            hint = t("meta_help_%s_desc" % meta) + " " + t("meta_tiff_note")
        else:
            hint = t("meta_help_%s_desc" % meta)
        self._set_hint(self.meta_hint, hint)

    def _refresh_status(self):
        if not hasattr(self, "status_lbl"):
            return
        icon, color, progress_color, show_errors = None, TEXT_SOFT, ACCENT, False
        show_progress = True
        if self._running:
            text = self._status_text
        elif self._result:
            kind, text = self._result
            if kind == "done":
                icon, color, progress_color = self._icon("check", SUCCESS, 16), SUCCESS_LIGHT, SUCCESS
            elif kind == "partial":
                icon, color, progress_color = self._icon("error", DANGER, 16), DANGER_LIGHT, DANGER
                show_errors = True
            else:
                color, progress_color = MUTED, SUBTLE
        else:
            show_progress = False
            n = len(self.files)
            if not n:
                text, color = t("status_empty"), MUTED
            else:
                key = "status_ready_one" if n == 1 else "status_ready_other"
                text = t(key, n=n, fmt=self._fmt_label(self.format_var.get()))
        self.status_icon.pack_forget()
        self.errors_btn.pack_forget()
        self.status_lbl.pack_forget()
        if icon is not None:
            self.status_icon.configure(image=icon)
            self.status_icon.pack(side="left", padx=(0, 6))
        self.status_lbl.configure(text=text, text_color=color)
        self.status_lbl.pack(side="left")
        if show_errors:
            self.errors_btn.pack(side="left", padx=(8, 0))
        if show_progress:
            self.progress.configure(progress_color=progress_color)
            self.progress.set(self._progress_value)
            self.progress.grid()
        else:
            self.progress.grid_remove()

    def _refresh_buttons(self):
        if not hasattr(self, "btn_convert"):
            return
        n = len(self.files)
        if self._running:
            self.btn_convert.configure(text=t("cancel"), state="normal", kind="danger", icon_name="stop")
        elif n:
            text = t("convert_one") if n == 1 else t("convert_other", n=n)
            self.btn_convert.configure(text=text, state="normal", kind="primary", icon_name="convert")
        else:
            self.btn_convert.configure(text=t("convert"), state="disabled", kind="primary", icon_name="convert")
        out = self.output_var.get().strip()
        self.btn_open.configure(state="normal" if out and os.path.isdir(out) else "disabled")
        has_sel = bool(self.tree.selection()) if hasattr(self, "tree") else False
        self.btn_remove.configure(state="normal" if has_sel and not self._running else "disabled")
        self.btn_clear.configure(state="normal" if n and not self._running else "disabled")
        self.lang_seg.configure(state="disabled" if self._running else "normal")

    def _preset_field_changed(self):
        if self._applying_preset or not self.preset_var.get():
            return
        self.preset_var.set("")
        self._refresh_preset_ui()

    def _apply_preset(self, key):
        p = PRESETS.get(key)
        if not p:
            return
        self._applying_preset = True
        try:
            if p.get("format") in self._formats:
                self.format_var.set(p["format"])
            if "quality" in p:
                self.quality_var.set(int(p["quality"]))
            r = p.get("resize") or {}
            self.width_var.set(str(r.get("width") or ""))
            self.height_var.set(str(r.get("height") or ""))
            self.fit_var.set(r.get("fit", "inside"))
            if p.get("metadata") in ("preserve", "strip", "selective"):
                self.meta_var.set(p["metadata"])
            self.preset_var.set(key)
        finally:
            self._applying_preset = False
        self._refresh_preset_ui()

    def _sync_entry(self, key):
        item = self._entries.get(key)
        if not item:
            return
        e, var = item
        try:
            if not e.winfo_exists():
                return
            val = var.get()
            if e.get() == val:
                return
            e.delete(0, "end")
            if val:
                e.insert(0, val)
                if key == "output":
                    e._entry.xview_moveto(1.0)  # mostrar el final de la ruta (la carpeta)
        except Exception:
            pass

    # ---------------------------------------------------------------- diseño adaptable

    def _schedule_layout(self):
        if self._layout_job is not None:
            try:
                self.root.after_cancel(self._layout_job)
            except Exception:
                pass
        self._layout_job = self.root.after(40, self._apply_layout)

    def _apply_layout(self):
        self._layout_job = None
        s = self.scale or 1
        W = self.body.winfo_width() / s
        H = self.body.winfo_height() / s
        if W < 100 or not hasattr(self, "tree"):
            return
        right = max(360, min(440, W * 0.37))
        self.body.grid_columnconfigure(1, minsize=self.px(right))
        left = W - right - 14

        buttons = (self.btn_add, self.btn_folder, self.btn_remove, self.btn_clear)
        needed = sum(b.winfo_reqwidth() for b in buttons) / s + 8 + 4 + 32
        compact = left - 2 * 18 < needed
        if compact != self._compact:
            self._compact = compact
            self._layout_toolbar(compact)

        cols = ("name", "size", "status") if left < 500 else ("name", "type", "size", "status")
        self.tree.configure(displaycolumns=cols)

        if self.files and H >= 470:
            self.preview.grid(row=3, column=0, sticky="ew", padx=18, pady=(0, 18))
            self.list_box.grid(pady=(0, 12))
        else:
            self.preview.grid_remove()
            self.list_box.grid(pady=(0, 18))

        # El crédito se oculta solo si la ventana es tan angosta que no cabe en la barra
        if self.root.winfo_width() / s >= 940:
            self.credit_lbl.grid()
        else:
            self.credit_lbl.grid_remove()


        wrap_col = max(120, right - 2 * 18 - LABEL_W - 48)
        wrap_span = max(160, right - 2 * 18 - 48)
        for lbl, span in self._hints:
            try:
                lbl.configure(wraplength=wrap_span if span else wrap_col)
            except Exception:
                pass
        self._schedule_scrollbar_sync()

    def _layout_toolbar(self, compact):
        tb = self.toolbar
        buttons = (self.btn_add, self.btn_folder, self.btn_remove, self.btn_clear)
        for b in buttons:
            b.grid_forget()
        for i in range(5):
            tb.grid_columnconfigure(i, weight=0, uniform="")
        if compact:
            tb.grid_columnconfigure((0, 1), weight=1, uniform="tb")
            for i, b in enumerate(buttons):
                b.grid(row=i // 2, column=i % 2, sticky="ew", padx=(0 if i % 2 == 0 else 4, 0 if i % 2 else 4),
                       pady=(0 if i < 2 else 6, 0))
        else:
            tb.grid_columnconfigure(2, weight=1)
            self.btn_add.grid(row=0, column=0)
            self.btn_folder.grid(row=0, column=1, padx=(8, 0))
            self.btn_remove.grid(row=0, column=3, padx=(0, 4))
            self.btn_clear.grid(row=0, column=4)

    def _schedule_scrollbar_sync(self):
        try:
            self.root.after_idle(self._sync_settings_scrollbar)
        except Exception:
            pass

    # Las barras de scroll no se quitan del grid (CTk las deja dibujadas); se vuelven
    # invisibles pintándolas del color del fondo cuando todo el contenido cabe.
    def _sync_settings_scrollbar(self):
        try:
            canvas = self.settings._parent_canvas
            need = self.settings.winfo_reqheight() > canvas.winfo_height() + 1
            if need != getattr(self, "_settings_scroll_on", None):
                self._settings_scroll_on = need
                self.settings.configure(scrollbar_button_color=BORDER if need else PANEL,
                                        scrollbar_button_hover_color=SUBTLE if need else PANEL)
                if not need:
                    canvas.yview_moveto(0)
        except Exception:
            pass

    def _tree_yscroll(self, first, last):
        try:
            self.tree_scroll.set(first, last)
            need = not (float(first) <= 0.0 and float(last) >= 1.0)
            if need != getattr(self, "_tree_scroll_on", None):
                self._tree_scroll_on = need
                self.tree_scroll.configure(button_color=BORDER if need else INPUT,
                                           button_hover_color=SUBTLE if need else INPUT)
        except Exception:
            pass

    def _recheck_tree_scroll(self):
        try:
            self._tree_yscroll(*self.tree.yview())
        except Exception:
            pass

    def _wrap_preview_labels(self, event):
        width = max(80, event.width / (self.scale or 1) - 4)
        for lbl in (self.pv_name, self.pv_path):
            try:
                lbl.configure(wraplength=width)
            except Exception:
                pass

    # ---------------------------------------------------------------- menús flotantes

    def _open_popover(self, anchor, width, build, align="left"):
        if self._popover is not None:
            same = self._popover_anchor is anchor
            self._close_popover()
            if same:
                return
        top = tk.Toplevel(self.root)
        top.withdraw()
        top.overrideredirect(True)
        key = PANEL
        try:
            top.configure(bg=POPOVER_KEY)
            top.attributes("-transparentcolor", POPOVER_KEY)
            key = POPOVER_KEY
        except Exception:
            top.configure(bg=PANEL)
        card = ctk.CTkFrame(top, fg_color=PANEL, corner_radius=14, border_width=1, border_color=BORDER,
                            bg_color=key, width=width)
        card.pack(fill="both", expand=True)
        build(card)
        top.update_idletasks()
        w = self.px(width)
        h = card.winfo_reqheight()
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        ax, ay = anchor.winfo_rootx(), anchor.winfo_rooty()
        x = ax + anchor.winfo_width() - w if align == "right" else ax
        win_right = self.root.winfo_rootx() + self.root.winfo_width() - self.px(10)
        if x + w > win_right:  # mantener el menú dentro de la ventana
            x = max(self.root.winfo_rootx() + self.px(10), win_right - w)
        x = max(4, min(x, sw - w - 4))
        y = ay + anchor.winfo_height() + self.px(6)
        if y + h > sh - self.px(48):
            above = ay - h - self.px(6)
            y = above if above >= 4 else max(4, sh - h - self.px(48))
        top.geometry(f"{w}x{h}+{x}+{y}")
        top.deiconify()
        top.lift()
        top.bind("<Escape>", lambda e: self._close_popover())
        self._popover = top
        self._popover_anchor = anchor

    def _close_popover(self):
        top = self._popover
        self._popover = None
        self._popover_anchor = None
        if top is not None:
            # Se oculta al instante y se destruye después de la animación de clic de CTk.
            try:
                top.withdraw()
                self.root.after(200, top.destroy)
            except Exception:
                pass

    def _release_entry_focus(self, event=None):
        """Un clic fuera de los campos de texto les quita el foco (Tk no lo hace solo)."""
        try:
            if event is not None and event.widget.winfo_class() in ("Entry", "TEntry", "Text", "Spinbox"):
                return
            focused = self.root.focus_get()
            if focused is not None and focused.winfo_class() in ("Entry", "TEntry", "Text", "Spinbox"):
                self.root.focus_set()
        except Exception:
            pass

    def _on_root_click(self, event):
        self._release_entry_focus(event)
        if self.frame is not None:
            edge = self.frame.edge_at(event.x_root, event.y_root)
            if edge:
                self._close_popover()
                self.frame.begin_resize(edge, event.x_root, event.y_root)
                return "break"
        if self._popover is None:
            return
        anchor = self._popover_anchor
        try:
            if anchor is not None and _path_inside(event.widget, anchor):
                return
        except Exception:
            pass
        self._close_popover()

    def _on_root_configure(self, event):
        if str(event.widget) != str(self.root):
            return
        if self._popover is not None:
            self._close_popover()
        self._refresh_max_icon()

    def _menu_row(self, parent, title, subtitle, selected, on_pick):
        base = ACCENT_TINT if selected else PANEL
        row = ctk.CTkFrame(parent, fg_color=base, corner_radius=8)
        row.pack(fill="x", pady=1)
        row.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(row, text=title, font=self.f_body_semi if selected else self.f_body,
                     text_color=TEXT, anchor="w", height=22).grid(row=0, column=0, sticky="ew",
                                                                  padx=(12, 6), pady=(7, 0 if subtitle else 7))
        if subtitle:
            ctk.CTkLabel(row, text=subtitle, font=self.f_caption, text_color=MUTED, anchor="w", justify="left",
                         height=16, wraplength=230).grid(row=1, column=0, sticky="ew", padx=(12, 6), pady=(0, 7))
        if selected:
            check = self._icon("check", ACCENT_LIGHT, 14)
            ctk.CTkLabel(row, text="" if check else "✓", image=check, width=18,
                         text_color=ACCENT_LIGHT).grid(row=0, column=1, rowspan=2, padx=(0, 10))

        def enter(_e=None):
            row.configure(fg_color=ACCENT_TINT_HOVER if selected else CARD_HOVER)

        def leave(_e=None):
            if not _pointer_inside(row):
                row.configure(fg_color=base)

        _bind_raw(row, "<Button-1>", lambda e: on_pick())
        _bind_raw(row, "<Enter>", enter)
        _bind_raw(row, "<Leave>", leave)
        _set_cursor(row)

    def _anchor_width(self, anchor, minimum):
        return max(minimum, int(anchor.winfo_width() / (self.scale or 1)))

    def _open_format_menu(self):
        current = self.format_var.get()
        popular = [f for f in POPULAR_FORMATS if f in self._formats]
        others = [f for f in self._formats if f not in popular]

        def pick(value):
            self._close_popover()
            self.format_var.set(value)

        def chips(parent, items, cols):
            grid = ctk.CTkFrame(parent, fg_color="transparent")
            grid.pack(fill="x")
            for c in range(cols):
                grid.grid_columnconfigure(c, weight=1, uniform="chips")
            for i, f in enumerate(items):
                sel = f == current
                self._button(grid, self._fmt_label(f), lambda v=f: pick(v), "primary" if sel else "neutral",
                             height=32, width=40, radius=8, font=self.tf_small).grid(
                    row=i // cols, column=i % cols, sticky="ew", padx=3, pady=3)

        def build(card):
            wrap = ctk.CTkFrame(card, fg_color="transparent")
            wrap.pack(fill="both", expand=True, padx=12, pady=12)
            ctk.CTkLabel(wrap, text=t("format_popular").upper(), font=self.f_section, text_color=MUTED,
                         anchor="w", height=20).pack(fill="x", padx=3, pady=(0, 4))
            chips(wrap, popular, 3)
            if others:
                ctk.CTkLabel(wrap, text=t("format_other").upper(), font=self.f_section, text_color=MUTED,
                             anchor="w", height=20).pack(fill="x", padx=3, pady=(12, 4))
                chips(wrap, others, 4)

        self._open_popover(self.fmt_select, self._anchor_width(self.fmt_select, 300), build)

    def _open_preset_menu(self):
        current = self.preset_var.get()

        def pick(key):
            self._close_popover()
            if key:
                self._apply_preset(key)
            else:
                self.preset_var.set("")
                self._refresh_preset_ui()

        def build(card):
            wrap = ctk.CTkFrame(card, fg_color="transparent")
            wrap.pack(fill="both", expand=True, padx=8, pady=8)
            self._menu_row(wrap, t("preset_none"), t("preset_hint_none"), not current, lambda: pick(""))
            for key in PRESETS:
                self._menu_row(wrap, t("preset_" + key), self._preset_desc(key), key == current,
                               lambda k=key: pick(k))

        self._open_popover(self.preset_select, self._anchor_width(self.preset_select, 280), build)

    def _open_rotate_menu(self):
        current = self.rotate_var.get()

        def pick(value):
            self._close_popover()
            self.rotate_var.set(value)

        def build(card):
            wrap = ctk.CTkFrame(card, fg_color="transparent")
            wrap.pack(fill="both", expand=True, padx=8, pady=8)
            for v in ROTATIONS:
                self._menu_row(wrap, self._rot_label(v), None, v == current, lambda v=v: pick(v))

        self._open_popover(self.rot_select, self._anchor_width(self.rot_select, 220), build)

    def _open_help(self, anchor, title, body, items):
        def build(card):
            wrap = ctk.CTkFrame(card, fg_color="transparent")
            wrap.pack(fill="both", expand=True, padx=16, pady=14)
            ctk.CTkLabel(wrap, text=title, font=self.f_h2, text_color=TEXT, anchor="w").pack(fill="x")
            ctk.CTkLabel(wrap, text=body, font=self.f_small, text_color=MUTED, anchor="w", justify="left",
                         wraplength=284).pack(fill="x", pady=(2, 6))
            for head, desc in items:
                ctk.CTkLabel(wrap, text=head, font=self.f_small_semi, text_color=ACCENT_LIGHT, anchor="w",
                             height=20).pack(fill="x", pady=(6, 0))
                ctk.CTkLabel(wrap, text=desc, font=self.f_small, text_color=TEXT_SOFT, anchor="w",
                             justify="left", wraplength=284).pack(fill="x")
            self._button(wrap, t("help_ok"), self._close_popover, "primary", height=34,
                         font=self.tf_small).pack(anchor="e", pady=(14, 0))

        self._open_popover(anchor, 320, build)

    def _open_metadata_help(self, anchor):
        self._open_help(anchor, t("meta_help_title"), t("meta_help_body"), [
            (t("meta_help_preserve"), t("meta_help_preserve_desc")),
            (t("meta_help_strip"), t("meta_help_strip_desc")),
            (t("meta_help_selective"), t("meta_help_selective_desc")),
        ])

    def _open_fit_help(self, anchor):
        self._open_help(anchor, t("fit_help_title"), t("fit_help_body"), [
            (t("fit_help_inside"), t("fit_help_inside_desc")),
            (t("fit_help_cover"), t("fit_help_cover_desc")),
            (t("fit_help_exact"), t("fit_help_exact_desc")),
        ])

    def _show_errors(self, anchor):
        errors = list(self._errors)

        def build(card):
            wrap = ctk.CTkFrame(card, fg_color="transparent")
            wrap.pack(fill="both", expand=True, padx=16, pady=14)
            ctk.CTkLabel(wrap, text=t("errors_title"), font=self.f_h2, text_color=TEXT, anchor="w").pack(fill="x")
            for name, msg in errors[:8]:
                ctk.CTkLabel(wrap, text=name, font=self.f_small_semi, text_color=DANGER_LIGHT, anchor="w",
                             height=20).pack(fill="x", pady=(8, 0))
                ctk.CTkLabel(wrap, text=str(msg)[:220], font=self.f_caption, text_color=MUTED, anchor="w",
                             justify="left", wraplength=344).pack(fill="x")
            if len(errors) > 8:
                ctk.CTkLabel(wrap, text=t("errors_more", n=len(errors) - 8), font=self.f_caption,
                             text_color=SUBTLE, anchor="w").pack(fill="x", pady=(8, 0))

        self._open_popover(anchor, 380, build)

    # ---------------------------------------------------------------- archivos

    def _row_values(self, path):
        ext = os.path.splitext(path)[1].lstrip(".").upper()
        status = self._row_status.get(path, ("", ()))[0]
        return (" " + os.path.basename(path), ext, _human_size(self._sizes.get(path)), status)

    def _fill_tree(self):
        for path in self.files:
            tags = self._row_status.get(path, ("", ()))[1]
            self.tree.insert("", "end", iid=path, values=self._row_values(path), tags=tags)

    def _add_one(self, path):
        if path in self._file_set:
            return 0
        self.files.append(path)
        self._file_set.add(path)
        try:
            self._sizes[path] = os.path.getsize(path)
        except OSError:
            self._sizes[path] = None
        self.tree.insert("", "end", iid=path, values=self._row_values(path))
        return 1

    def add_paths(self, paths):
        exts = set(self._input_exts)
        added = 0
        for p in paths:
            p = os.path.normpath(str(p))
            if os.path.isdir(p):
                for root_dir, _, names in os.walk(p):
                    for fn in sorted(names):
                        if os.path.splitext(fn)[1].lower() in exts:
                            added += self._add_one(os.path.join(root_dir, fn))
            elif os.path.isfile(p):
                added += self._add_one(p)
        if added:
            self._result = None
            self._progress_value = 0.0
            self._refresh_files_ui()
        return added

    def _add_files(self):
        pattern = " ".join("*" + e for e in self._input_exts) or "*.*"
        files = filedialog.askopenfilenames(
            parent=self.root, title=t("add_files"), initialdir=self._last_dir or None,
            filetypes=[(t("image_files"), pattern), (t("all_files"), "*.*")])
        if files:
            self._last_dir = os.path.dirname(files[0])
            self.add_paths(files)

    def _add_folder(self):
        d = filedialog.askdirectory(parent=self.root, title=t("add_folder"), initialdir=self._last_dir or None)
        if d:
            self._last_dir = d
            self.add_paths([d])

    def _remove_paths(self, paths):
        for path in paths:
            if path in self._file_set:
                self._file_set.discard(path)
                self.files.remove(path)
                self._sizes.pop(path, None)
                self._row_status.pop(path, None)
                self._thumb_cache.pop(path, None)
            if self.tree.exists(path):
                self.tree.delete(path)

    def _remove_selected(self):
        sel = self.tree.selection()
        if not sel or self._running:
            return
        index = self.tree.index(sel[0])
        self._remove_paths(list(sel))
        children = self.tree.get_children()
        if children:
            nxt = children[min(index, len(children) - 1)]
            self.tree.selection_set(nxt)
            self.tree.focus(nxt)
        self._result = None
        self._refresh_files_ui()

    def _clear_files(self):
        if self._running:
            return
        self._remove_paths(list(self.files))
        self._result = None
        self._refresh_files_ui()

    def _select_all(self, _e=None):
        self.tree.selection_set(self.tree.get_children())
        return "break"

    def _open_row(self, event):
        iid = self.tree.identify_row(event.y)
        if iid and os.path.exists(iid):
            try:
                open_path(iid)
            except Exception:
                pass

    def _empty_hover(self, on):
        try:
            self.list_box.configure(border_color=ACCENT if on else BORDER)
            self.empty_title.configure(text_color=ACCENT_LIGHT if on else TEXT)
        except Exception:
            pass

    def _drop_highlight(self, on, event=None):
        self._empty_hover(on)
        return getattr(event, "action", None)

    def _drop_output_highlight(self, on, event=None):
        try:
            self.out_entry.configure(border_color=ACCENT if on else BORDER)
        except Exception:
            pass
        return getattr(event, "action", None)

    def _on_drop_files(self, event):
        self._drop_highlight(False)
        self.add_paths(_normalize_dropped_paths(self.root, event.data))
        return event.action

    def _on_drop_output(self, event):
        self._drop_output_highlight(False)
        for p in _normalize_dropped_paths(self.root, event.data):
            if os.path.isdir(p):
                self.output_var.set(os.path.normpath(p))
                break
            if os.path.isfile(p):
                self.output_var.set(os.path.dirname(os.path.normpath(p)))
                break
        return event.action

    def _pick_output(self):
        current = self.output_var.get().strip()
        d = filedialog.askdirectory(parent=self.root, title=t("pick_output_title"),
                                    initialdir=current if os.path.isdir(current) else None)
        if d:
            self.output_var.set(os.path.normpath(d))

    # ---------------------------------------------------------------- vista previa

    def _make_thumb(self, path):
        bw, bh = self.px(THUMB_W), self.px(THUMB_H)
        try:
            with Image.open(path) as im:
                fmt = (im.format or "").upper()
                w, h = im.size
                try:
                    if im.getexif().get(0x0112, 1) in (5, 6, 7, 8):
                        w, h = h, w
                except Exception:
                    pass
                try:
                    im.draft("RGB", (bw * 2, bh * 2))
                except Exception:
                    pass
                frame = ImageOps.exif_transpose(im) or im
                alpha = frame.mode in ("RGBA", "LA", "PA") or (frame.mode == "P" and "transparency" in frame.info)
                frame = frame.convert("RGBA" if alpha else "RGB")
                frame.thumbnail((bw, bh), Image.LANCZOS)
                if alpha:
                    bg = _checker(frame.width, frame.height, self.px(6))
                    bg.paste(frame, (0, 0), frame)
                    frame = bg
                return ImageTk.PhotoImage(frame, master=self.root), fmt, (w, h)
        except Exception:
            return None, os.path.splitext(path)[1].lstrip(".").upper(), None

    def _update_preview(self):
        if not hasattr(self, "preview"):
            return
        sel = self.tree.selection()
        path = sel[0] if sel else (self.files[0] if self.files else None)
        if path is None or path == self._preview_path:
            self._preview_path = path
            return
        self._preview_path = path
        data = self._thumb_cache.get(path)
        if data is None:
            data = self._make_thumb(path)
            if len(self._thumb_cache) >= 64:
                self._thumb_cache.pop(next(iter(self._thumb_cache)))
            self._thumb_cache[path] = data
        photo, fmt, dims = data
        self._thumb_photo = photo
        if photo is not None:
            self.thumb.configure(image=photo, text="")
        else:
            self.thumb.configure(image="", text=fmt or "?")
        parts = []
        if dims:
            parts.append(t("dims", w=dims[0], h=dims[1]))
        if fmt:
            parts.append(fmt)
        parts.append(_human_size(self._sizes.get(path)))
        self.pv_name.configure(text=os.path.basename(path))
        self.pv_meta.configure(text=" · ".join(parts))
        folder = os.path.dirname(path)
        self.pv_path.configure(text=folder if photo is not None else t("preview_unavailable") + "\n" + folder)

    # ---------------------------------------------------------------- conversión

    def _on_convert_click(self):
        if self._running:
            self._cancel()
        else:
            self._start_convert()

    @staticmethod
    def _parse_px(text):
        text = (text or "").strip()
        if not text:
            return None, True
        if text.isdigit() and int(text) > 0:
            return int(text), True
        return None, False

    def _start_convert(self):
        if self._running or not self.files:
            return
        self._close_popover()
        outdir = self.output_var.get().strip()
        if not outdir:
            d = filedialog.askdirectory(parent=self.root, title=t("pick_output_title"))
            if not d:
                return
            outdir = os.path.normpath(d)
            self.output_var.set(outdir)
        try:
            os.makedirs(outdir, exist_ok=True)
        except OSError as e:
            messagebox.showerror("Open Converter", t("output_error", err=e), parent=self.root)
            return

        w, ok_w = self._parse_px(self.width_var.get())
        h, ok_h = self._parse_px(self.height_var.get())
        if not (ok_w and ok_h):
            messagebox.showwarning("Open Converter", t("invalid_size"), parent=self.root)
            return
        transforms = []
        if w or h:
            transforms.append({"resize": {"width": w, "height": h, "fit": self.fit_var.get() or "inside"}})
        try:
            angle = float(self.rotate_var.get() or 0)
        except ValueError:
            angle = 0.0
        if angle:
            transforms.append({"rotate": {"angle": angle, "expand": True}})
        if self.flip_var.get() in ("horizontal", "vertical"):
            transforms.append({"flip": {"direction": self.flip_var.get()}})
        if self.gray_var.get():
            transforms.append({"grayscale": {}})

        files = list(self.files)
        fmt = self.format_var.get()
        quality = int(self.quality_var.get())
        meta = self.meta_var.get()

        self._errors = []
        for path in files:
            self._row_status.pop(path, None)
            if self.tree.exists(path):
                self.tree.item(path, values=self._row_values(path), tags=())
        self.cancel_flag.clear()
        self._running = True
        self._result = None
        self._progress_value = 0.0
        self._status_text = t("status_working", i=1, n=len(files))
        self._refresh_status()
        self._refresh_buttons()
        self._save_settings()
        self.worker = threading.Thread(
            target=self._convert_worker,
            args=(files, outdir, fmt, quality, meta, transforms or None),
            daemon=True)
        self.worker.start()

    @staticmethod
    def _unique_output(inp, outdir, ext, used):
        base = os.path.splitext(os.path.basename(inp))[0]
        src = os.path.normcase(os.path.abspath(inp))
        n = 0
        while True:
            name = f"{base}.{ext}" if n == 0 else f"{base} ({n}).{ext}"
            cand = os.path.join(outdir, name)
            key = os.path.normcase(os.path.abspath(cand))
            if key not in used and key != src:
                used.add(key)
                return cand
            n += 1

    def _convert_worker(self, files, outdir, fmt, quality, meta, transforms):
        total = len(files)
        ok = 0
        processed = 0
        ext = OUTPUT_EXT.get(fmt, fmt)
        used = set()
        for i, inp in enumerate(files, 1):
            if self.cancel_flag.is_set():
                break
            self._ui(lambda p=inp, i=i: self._row_working(p, i, total))
            outp = self._unique_output(inp, outdir, ext, used)
            try:
                res = self.conv.convert(inp, outp, format=fmt, quality=quality,
                                        transforms=transforms, metadata=meta, preset=None)
                ok += 1
                self._ui(lambda p=inp, r=res: self._row_done(p, r))
            except Exception as e:
                self._ui(lambda p=inp, err=e: self._row_failed(p, err))
            processed = i
            self._ui(lambda v=i: self._set_progress(v, total))
        cancelled = processed < total
        self._ui(lambda: self._finish(ok, total, processed, cancelled))

    def _set_row(self, path, text, tags):
        self._row_status[path] = (text, tags)
        try:
            if self.tree.exists(path):
                self.tree.item(path, values=self._row_values(path), tags=tags)
        except Exception:
            pass

    def _row_working(self, path, i, total):
        self._status_text = t("status_working", i=i, n=total)
        self._set_row(path, t("row_working"), ("working",))
        try:
            if self.tree.exists(path):
                self.tree.see(path)
        except Exception:
            pass
        self._refresh_status()

    def _row_done(self, path, res):
        self._set_row(path, t("row_ok", size=_human_size(res.get("size"))), ("ok",))

    @staticmethod
    def _friendly_error(err):
        msg = str(err)
        low = msg.lower()
        if "cannot identify image file" in low or "cannot detect format" in low:
            return t("err_not_image")
        if isinstance(err, PermissionError) or "permission denied" in low:
            return t("err_permission")
        return re.sub(r"<[^>]+>", "", msg).strip() or type(err).__name__

    def _row_failed(self, path, err):
        self._errors.append((os.path.basename(path), self._friendly_error(err)))
        self._set_row(path, t("row_error"), ("fail",))

    def _set_progress(self, i, total):
        self._progress_value = i / total if total else 0.0
        try:
            self.progress.set(self._progress_value)
        except Exception:
            pass

    def _finish(self, ok, total, processed, cancelled):
        self._running = False
        fail = len(self._errors)
        if cancelled:
            self._result = ("cancelled", t("status_cancelled", ok=ok, total=total))
        elif fail:
            self._result = ("partial", t("status_partial", ok=ok, total=total, fail=fail))
        else:
            self._result = ("done", t("status_done", ok=ok, total=total))
        self._progress_value = processed / total if total else 0.0
        self._refresh_status()
        self._refresh_buttons()

    def _cancel(self):
        self.cancel_flag.set()
        try:
            self.btn_convert.configure(state="disabled")
        except Exception:
            pass

    def _open_output(self):
        d = self.output_var.get().strip()
        if d and os.path.isdir(d):
            open_path(d)

    def _ui(self, fn):
        try:
            self.root.after(0, fn)
        except Exception:
            pass

    # ---------------------------------------------------------------- idioma y cierre

    def _on_lang(self, value):
        lang = value.lower()
        if self._running or lang == get_language():
            self.lang_seg.set(get_language().upper())
            return
        set_language(lang)
        self._save_settings()
        # Reconstruir después de la animación del botón que disparó el cambio.
        self.root.after(160, self._build)

    def _save_settings(self):
        data = {
            "lang": get_language(),
            "output": self.output_var.get().strip(),
            "format": self.format_var.get(),
            "quality": int(self.quality_var.get()),
            "metadata": self.meta_var.get(),
        }
        try:
            path = _settings_path()
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def _on_close(self):
        if self._running and not messagebox.askyesno("Open Converter", t("running_quit"), parent=self.root):
            return
        self.cancel_flag.set()
        self._save_settings()
        self.root.destroy()


def _asset_path(name):
    """Ruta de un archivo de assets/ (en el ejecutable y en el código fuente)."""
    candidates = []
    if getattr(_sys, "frozen", False) and hasattr(_sys, "_MEIPASS"):
        candidates.append(os.path.join(_sys._MEIPASS, "assets", name))
    here = os.path.dirname(os.path.abspath(__file__))
    candidates.append(os.path.join(here, "..", "..", "..", "assets", name))
    candidates.append(os.path.join(os.getcwd(), "assets", name))
    for p in candidates:
        p = os.path.normpath(p)
        if os.path.exists(p):
            return p
    return None


def _icon_path():
    return _asset_path("icon.ico")


def _set_window_icon(root):
    """Ícono de la ventana: .ico en Windows; en Linux y macOS (modo desarrollo) el logo en PNG."""
    if IS_WINDOWS:
        ip = _icon_path()
        if ip:
            try:
                root.iconbitmap(ip)
            except Exception:
                pass
        return
    png = _asset_path("logo.png")
    if png:
        try:
            root._oc_icon = tk.PhotoImage(file=png)  # referencia viva: Tk descarta la imagen si no
            root.iconphoto(True, root._oc_icon)
        except Exception:
            pass


def run_gui():
    # Activar DPI antes de crear la ventana: así Tk y CustomTkinter usan la misma escala.
    try:
        ctk.ScalingTracker.activate_high_dpi_awareness()
    except Exception:
        pass
    try:
        from tkinterdnd2 import TkinterDnD
        root = TkinterDnD.Tk()
    except Exception:
        root = ctk.CTk()
    _set_window_icon(root)
    App(root)
    _set_window_icon(root)
    root.mainloop()
