"""Ventana sin la barra de título de Windows, conservando sus funciones nativas.

Cómo funciona:
1. Tk crea la ventana sin marco (overrideredirect), así su contenido ocupa toda la ventana.
2. Se le devuelven los estilos nativos (redimensionar, minimizar, maximizar, Aero Snap)
   y su botón en la barra de tareas.
3. Se intercepta el procedimiento de ventana (WNDPROC) para que Windows no dibuje su
   barra (WM_NCCALCSIZE) y para que al maximizar ocupe justo el área de trabajo
   (WM_GETMINMAXINFO, WM_NCCALCSIZE y WM_WINDOWPOSCHANGED).
4. Arrastrar y redimensionar se inician desde eventos de Tk: como cada widget de Tk es
   una sub-ventana, Windows no puede detectar solo la barra ni los bordes. Se le pide el
   movimiento nativo con PostMessage (asíncrono, fuera del callback de Tk).

Importante: _wndproc corre dentro del bucle de mensajes de Windows; ahí NO se puede
llamar a tkinter (Tcl no lo admite). Solo usa la API de Windows.
"""

import ctypes
import sys
from ctypes import wintypes

GWL_STYLE = -16
GWL_EXSTYLE = -20
GWLP_WNDPROC = -4
WS_POPUP = 0x80000000
WS_OVERLAPPEDWINDOW = 0x00CF0000
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_APPWINDOW = 0x00040000
WM_GETMINMAXINFO = 0x0024
WM_WINDOWPOSCHANGED = 0x0047
WM_NCCALCSIZE = 0x0083
WM_NCACTIVATE = 0x0086
WM_NCLBUTTONDOWN = 0x00A1
WM_SYSCOMMAND = 0x0112
SC_MINIMIZE = 0xF020
SC_MAXIMIZE = 0xF030
SC_RESTORE = 0xF120
SWP_NOSIZE = 0x0001
HTCAPTION = 2
HTLEFT, HTRIGHT, HTTOP, HTTOPLEFT, HTTOPRIGHT = 10, 11, 12, 13, 14
HTBOTTOM, HTBOTTOMLEFT, HTBOTTOMRIGHT = 15, 16, 17
SWP_FRAME_FLAGS = 0x0001 | 0x0002 | 0x0004 | 0x0010 | 0x0020  # NOSIZE|NOMOVE|NOZORDER|NOACTIVATE|FRAMECHANGED
MONITOR_DEFAULTTONEAREST = 2
DWMWA_USE_IMMERSIVE_DARK_MODE = 20
DWMWA_WINDOW_CORNER_PREFERENCE = 33
DWMWA_BORDER_COLOR = 34
DWMWA_CAPTION_COLOR = 35
DWMWCP_ROUND = 2

# Cursor de Tk para cada borde
EDGE_CURSORS = {
    HTLEFT: "size_we", HTRIGHT: "size_we", HTTOP: "size_ns", HTBOTTOM: "size_ns",
    HTTOPLEFT: "size_nw_se", HTBOTTOMRIGHT: "size_nw_se",
    HTTOPRIGHT: "size_ne_sw", HTBOTTOMLEFT: "size_ne_sw",
}

LRESULT = ctypes.c_ssize_t
# WINFUNCTYPE solo existe en Windows; en macOS y Linux este módulo se importa pero no se usa.
WNDPROC = (ctypes.WINFUNCTYPE(LRESULT, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)
           if sys.platform.startswith("win") else None)


class MINMAXINFO(ctypes.Structure):
    _fields_ = [("ptReserved", wintypes.POINT), ("ptMaxSize", wintypes.POINT),
                ("ptMaxPosition", wintypes.POINT), ("ptMinTrackSize", wintypes.POINT),
                ("ptMaxTrackSize", wintypes.POINT)]


class MONITORINFO(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", wintypes.RECT),
                ("rcWork", wintypes.RECT), ("dwFlags", wintypes.DWORD)]


class WINDOWPOS(ctypes.Structure):
    _fields_ = [("hwnd", wintypes.HWND), ("hwndInsertAfter", wintypes.HWND),
                ("x", ctypes.c_int), ("y", ctypes.c_int), ("cx", ctypes.c_int),
                ("cy", ctypes.c_int), ("flags", wintypes.UINT)]


class NCCALCSIZE_PARAMS(ctypes.Structure):
    _fields_ = [("rgrc", wintypes.RECT * 3), ("lppos", ctypes.POINTER(WINDOWPOS))]


def _colorref(hex_color):
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return r | (g << 8) | (b << 16)


def _api():
    user32 = ctypes.windll.user32
    user32.GetWindowLongPtrW.restype = ctypes.c_ssize_t
    user32.GetWindowLongPtrW.argtypes = (wintypes.HWND, ctypes.c_int)
    user32.SetWindowLongPtrW.restype = ctypes.c_ssize_t
    user32.SetWindowLongPtrW.argtypes = (wintypes.HWND, ctypes.c_int, ctypes.c_ssize_t)
    user32.CallWindowProcW.restype = LRESULT
    user32.CallWindowProcW.argtypes = (ctypes.c_ssize_t, wintypes.HWND, wintypes.UINT,
                                       wintypes.WPARAM, wintypes.LPARAM)
    user32.PostMessageW.argtypes = (wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)
    user32.MonitorFromRect.restype = wintypes.HMONITOR
    user32.MonitorFromRect.argtypes = (ctypes.POINTER(wintypes.RECT), wintypes.DWORD)
    user32.MonitorFromWindow.restype = wintypes.HMONITOR
    user32.MonitorFromWindow.argtypes = (wintypes.HWND, wintypes.DWORD)
    user32.GetMonitorInfoW.argtypes = (wintypes.HMONITOR, ctypes.POINTER(MONITORINFO))
    user32.GetWindowRect.argtypes = (wintypes.HWND, ctypes.POINTER(wintypes.RECT))
    user32.IsZoomed.argtypes = (wintypes.HWND,)
    user32.SetWindowPos.argtypes = (wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int,
                                    ctypes.c_int, ctypes.c_int, wintypes.UINT)
    return user32


def set_dwm_colors(hwnd, border=None, caption=None):
    """Modo oscuro, esquinas redondeadas y colores del marco (Windows 11; en 10 se ignora)."""
    try:
        dwm = ctypes.windll.dwmapi
        one = ctypes.c_int(1)
        dwm.DwmSetWindowAttribute(hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE, ctypes.byref(one), 4)
        corner = ctypes.c_int(DWMWCP_ROUND)
        dwm.DwmSetWindowAttribute(hwnd, DWMWA_WINDOW_CORNER_PREFERENCE, ctypes.byref(corner), 4)
        if border:
            c = ctypes.c_int(_colorref(border))
            dwm.DwmSetWindowAttribute(hwnd, DWMWA_BORDER_COLOR, ctypes.byref(c), 4)
        if caption:
            c = ctypes.c_int(_colorref(caption))
            dwm.DwmSetWindowAttribute(hwnd, DWMWA_CAPTION_COLOR, ctypes.byref(c), 4)
    except Exception:
        pass


class FramelessWindow:
    """Quita la barra de Windows a una ventana Tk creada con overrideredirect(True)."""

    def __init__(self, root, border_px=6):
        self.root = root
        self.border = border_px
        self.hwnd = None
        self._old_proc = None
        self._proc_ref = None
        self._user32 = None

    @staticmethod
    def supported():
        return sys.platform.startswith("win")

    def install(self, border_color=None):
        """Aplica el marco propio. Devuelve False si algo falla (se usa la barra nativa)."""
        if not self.supported():
            return False
        try:
            user32 = self._user32 = _api()
            self.root.update_idletasks()
            hwnd = int(self.root.wm_frame(), 16)
            self.hwnd = hwnd
            style = user32.GetWindowLongPtrW(hwnd, GWL_STYLE)
            user32.SetWindowLongPtrW(hwnd, GWL_STYLE, (style & ~WS_POPUP) | WS_OVERLAPPEDWINDOW)
            ex = user32.GetWindowLongPtrW(hwnd, GWL_EXSTYLE)
            user32.SetWindowLongPtrW(hwnd, GWL_EXSTYLE, (ex & ~WS_EX_TOOLWINDOW) | WS_EX_APPWINDOW)
            self._proc_ref = WNDPROC(self._wndproc)
            self._old_proc = user32.SetWindowLongPtrW(
                hwnd, GWLP_WNDPROC, ctypes.cast(self._proc_ref, ctypes.c_void_p).value)
            if not self._old_proc:
                return False
            set_dwm_colors(hwnd, border=border_color)
            user32.SetWindowPos(hwnd, None, 0, 0, 0, 0, SWP_FRAME_FLAGS)
            return True
        except Exception:
            return False

    # ---------------------------------------------------------------- acciones
    # Todo con PostMessage: Windows ejecuta la acción en su bucle, fuera del callback de Tk.

    def minimize(self):
        if self.hwnd:
            self._user32.PostMessageW(self.hwnd, WM_SYSCOMMAND, SC_MINIMIZE, 0)

    def toggle_maximize(self):
        if self.hwnd:
            cmd = SC_RESTORE if self.is_maximized() else SC_MAXIMIZE
            self._user32.PostMessageW(self.hwnd, WM_SYSCOMMAND, cmd, 0)

    def is_maximized(self):
        return bool(self.hwnd and self._user32.IsZoomed(self.hwnd))

    def begin_move(self, x_root, y_root):
        """Arrastre nativo de la ventana (con Aero Snap) desde la barra de título propia."""
        self._begin(HTCAPTION, x_root, y_root)

    def begin_resize(self, edge, x_root, y_root):
        self._begin(edge, x_root, y_root)

    def _begin(self, hit, x, y):
        if not self.hwnd:
            return
        self._user32.ReleaseCapture()
        lparam = (x & 0xFFFF) | ((y & 0xFFFF) << 16)
        self._user32.PostMessageW(self.hwnd, WM_NCLBUTTONDOWN, hit, lparam)

    def edge_at(self, x_root, y_root):
        """Código del borde bajo el puntero (0 si no está en un borde o si está maximizada)."""
        if not self.hwnd or self.is_maximized():
            return 0
        rect = wintypes.RECT()
        self._user32.GetWindowRect(self.hwnd, ctypes.byref(rect))
        b = self.border
        left, right = x_root - rect.left < b, rect.right - x_root <= b
        top, bottom = y_root - rect.top < b, rect.bottom - y_root <= b
        if top and left:
            return HTTOPLEFT
        if top and right:
            return HTTOPRIGHT
        if bottom and left:
            return HTBOTTOMLEFT
        if bottom and right:
            return HTBOTTOMRIGHT
        if left:
            return HTLEFT
        if right:
            return HTRIGHT
        if top:
            return HTTOP
        if bottom:
            return HTBOTTOM
        return 0

    # ---------------------------------------------------------------- procedimiento de ventana

    def _wndproc(self, hwnd, msg, wparam, lparam):
        try:
            if msg == WM_NCCALCSIZE and wparam:
                if self._user32.IsZoomed(hwnd):
                    # Maximizada: Windows deja los bordes 8 px fuera de pantalla; el área
                    # visible del programa es solo el área de trabajo del monitor.
                    params = NCCALCSIZE_PARAMS.from_address(lparam)
                    area = self._work_area(rect=params.rgrc[0])
                    if area:
                        params.rgrc[0] = area[0]
                return 0  # sin barra ni bordes de Windows: todo es área del programa
            if msg == WM_NCACTIVATE:
                # lParam = -1 evita que Windows repinte su barra al activar/desactivar
                return self._user32.CallWindowProcW(self._old_proc, hwnd, msg, wparam, -1)
            if msg == WM_GETMINMAXINFO:
                result = self._user32.CallWindowProcW(self._old_proc, hwnd, msg, wparam, lparam)
                self._fit_minmax(hwnd, lparam)
                return result
            if msg == WM_WINDOWPOSCHANGED and self._user32.IsZoomed(hwnd):
                self._report_client_to_tk(hwnd, lparam)
        except Exception:
            pass
        return self._user32.CallWindowProcW(self._old_proc, hwnd, msg, wparam, lparam)

    def _work_area(self, hwnd=None, rect=None):
        """Área de trabajo del monitor. Con `rect` se usa el destino (no la posición actual,
        que al restaurar desde minimizado está fuera de pantalla y apunta a otro monitor)."""
        if rect is not None:
            r = wintypes.RECT(rect.left, rect.top, rect.right, rect.bottom)
            monitor = self._user32.MonitorFromRect(ctypes.byref(r), MONITOR_DEFAULTTONEAREST)
        else:
            monitor = self._user32.MonitorFromWindow(hwnd, MONITOR_DEFAULTTONEAREST)
        info = MONITORINFO()
        info.cbSize = ctypes.sizeof(MONITORINFO)
        if not self._user32.GetMonitorInfoW(monitor, ctypes.byref(info)):
            return None
        return info.rcWork, info.rcMonitor

    def _fit_minmax(self, hwnd, lparam):
        area = self._work_area(hwnd)
        if not area:
            return
        work, mon = area
        mmi = MINMAXINFO.from_address(lparam)
        mmi.ptMaxPosition.x = work.left - mon.left
        mmi.ptMaxPosition.y = work.top - mon.top
        mmi.ptMaxSize.x = work.right - work.left
        mmi.ptMaxSize.y = work.bottom - work.top
        mmi.ptMaxTrackSize.x = max(mmi.ptMaxTrackSize.x, mmi.ptMaxSize.x)
        mmi.ptMaxTrackSize.y = max(mmi.ptMaxTrackSize.y, mmi.ptMaxSize.y)

    def _report_client_to_tk(self, hwnd, lparam):
        """Tk calcula el tamaño de su contenido con el de la ventana. Maximizada, la ventana
        es 16 px más grande que lo visible, así que se le informa el área de trabajo."""
        pos = WINDOWPOS.from_address(lparam)
        if pos.flags & SWP_NOSIZE:
            return
        target = wintypes.RECT(pos.x, pos.y, pos.x + pos.cx, pos.y + pos.cy)
        area = self._work_area(rect=target)
        if not area:
            return
        work = area[0]
        pos.x, pos.y = work.left, work.top
        pos.cx, pos.cy = work.right - work.left, work.bottom - work.top


def apply_native_dark_caption(root, caption_color, border_color=None):
    """Plan B: barra nativa de Windows pintada con los colores del programa."""
    if not sys.platform.startswith("win"):
        return
    try:
        root.update_idletasks()
        hwnd = int(root.wm_frame(), 16)
        set_dwm_colors(hwnd, border=border_color, caption=caption_color)
    except Exception:
        pass
