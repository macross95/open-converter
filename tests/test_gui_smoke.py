"""Prueba de humo: la ventana se construye y se cierra sin errores en cada sistema."""

import os
import sys

import pytest

tk = pytest.importorskip("tkinter")
pytest.importorskip("customtkinter")

HAS_DISPLAY = sys.platform.startswith("win") or sys.platform == "darwin" or bool(os.environ.get("DISPLAY"))


@pytest.mark.skipif(not HAS_DISPLAY, reason="no hay pantalla disponible")
def test_window_builds_and_closes():
    from openconverter.gui.tk_app import App

    try:
        from tkinterdnd2 import TkinterDnD
        root = TkinterDnD.Tk()
    except Exception:
        import customtkinter as ctk
        root = ctk.CTk()
    try:
        app = App(root)
        root.update_idletasks()
        root.update()
        assert app.files == []
    finally:
        root.destroy()


def test_platform_helpers():
    from openconverter import platform_utils as pu

    assert os.path.isabs(pu.config_dir())
    normal, semi = pu.font_candidates()
    assert normal and semi
    assert pu.command_modifier() in ("Control", "Command")


def test_vector_icons_cover_all_names():
    from openconverter.gui.tk_app import ICON_GLYPHS
    from openconverter.gui.vector_icons import draw_icon

    for name in ICON_GLYPHS:
        img = draw_icon(name, "#ffffff", 16)
        assert img is not None and img.size == (16, 16)
