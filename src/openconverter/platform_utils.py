"""Diferencias entre Windows, macOS y Linux en un solo lugar.

Todo lo que depende del sistema operativo (carpeta de ajustes, abrir archivos,
tipografías, atajos de teclado) vive aquí, para que el resto del código sea igual
en los tres sistemas.
"""

import os
import subprocess
import sys

APP_DIR_NAME = "Open Converter"

IS_WINDOWS = sys.platform.startswith("win")
IS_MAC = sys.platform == "darwin"
IS_LINUX = sys.platform.startswith("linux")


def config_dir() -> str:
    """Carpeta donde se guardan los ajustes, según las costumbres de cada sistema."""
    home = os.path.expanduser("~")
    if IS_WINDOWS:
        base = os.environ.get("APPDATA") or home
        return os.path.join(base, APP_DIR_NAME)
    if IS_MAC:
        return os.path.join(home, "Library", "Application Support", APP_DIR_NAME)
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.join(home, ".config")
    return os.path.join(base, "open-converter")


def open_path(path: str) -> bool:
    """Abre un archivo o carpeta con el programa predeterminado del sistema."""
    try:
        if IS_WINDOWS:
            os.startfile(path)  # type: ignore[attr-defined]
        elif IS_MAC:
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except Exception:
        return False


def font_candidates() -> tuple:
    """(normales, seminegrita): tipografías en orden de preferencia para cada sistema."""
    if IS_WINDOWS:
        return ("Segoe UI",), ("Segoe UI Semibold", "Segoe UI")
    if IS_MAC:
        return ("Helvetica Neue", "Helvetica", "Arial"), ("Helvetica Neue", "Helvetica", "Arial")
    return (
        ("Ubuntu", "Noto Sans", "Cantarell", "DejaVu Sans", "Liberation Sans", "Arial"),
        ("Ubuntu", "Noto Sans", "Cantarell", "DejaVu Sans", "Liberation Sans", "Arial"),
    )


def command_modifier() -> str:
    """Tecla de los atajos: Command en macOS, Control en Windows y Linux (nombre de evento Tk)."""
    return "Command" if IS_MAC else "Control"
