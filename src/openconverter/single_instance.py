"""Evita abrir dos ventanas de Open Converter a la vez.

En Windows usa un mutex y trae al frente la ventana abierta; en Linux y macOS, un archivo
bloqueado en la carpeta de ajustes.

Si ya hay una ventana abierta, la trae al frente en lugar de abrir otra.
La línea de comandos no pasa por aquí, así que se puede convertir por consola
aunque la ventana esté abierta.
"""

import os
import sys

_MUTEX_NAME = "OpenConverter_SingleInstance_Mutex"
_WINDOW_PREFIX = "Open Converter"
_mutex = None  # se mantiene vivo mientras corre el programa


def _focus_existing_window():
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    own_pid = os.getpid()
    found = []

    @ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
    def callback(hwnd, _lparam):
        length = user32.GetWindowTextLengthW(hwnd)
        if length and user32.IsWindowVisible(hwnd):
            buf = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buf, length + 1)
            pid = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            if buf.value.startswith(_WINDOW_PREFIX) and pid.value != own_pid:
                found.append(hwnd)
                return False
        return True

    user32.EnumWindows(callback, 0)
    if not found:
        return False
    hwnd = found[0]
    if user32.IsIconic(hwnd):
        user32.ShowWindow(hwnd, 9)  # SW_RESTORE
    user32.SetForegroundWindow(hwnd)
    return True


def ensure_single_instance() -> bool:
    """True si esta es la única ventana; False si ya había otra (y se trajo al frente)."""
    global _mutex
    if not sys.platform.startswith("win"):
        return _ensure_single_instance_posix()
    import ctypes

    kernel32 = ctypes.windll.kernel32
    _mutex = kernel32.CreateMutexW(None, False, _MUTEX_NAME)
    if kernel32.GetLastError() != 183:  # ERROR_ALREADY_EXISTS
        return True
    try:
        if _focus_existing_window():
            return False
    except Exception:
        pass
    try:
        ctypes.windll.user32.MessageBoxW(None, "Open Converter ya está abierto.", "Open Converter", 0x40)
    except Exception:
        pass
    return False


_lock_file = None  # se mantiene abierto mientras corre el programa


def _ensure_single_instance_posix() -> bool:
    global _lock_file
    try:
        import fcntl

        from .platform_utils import config_dir

        os.makedirs(config_dir(), exist_ok=True)
        _lock_file = open(os.path.join(config_dir(), "app.lock"), "w")
        fcntl.flock(_lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return True
    except BlockingIOError:
        print("Open Converter ya está abierto.", file=sys.stderr)
        return False
    except Exception:
        return True  # si no se puede bloquear, mejor abrir que no abrir
