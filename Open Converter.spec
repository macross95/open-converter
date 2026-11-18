# -*- mode: python ; coding: utf-8 -*-
# Spec de PyInstaller para Windows, macOS y Linux (se elige el sistema al compilar).
import sys

from PyInstaller.utils.hooks import collect_all

IS_WIN = sys.platform.startswith("win")
IS_MAC = sys.platform == "darwin"

# Versión única: la de src/openconverter/__init__.py
sys.path.insert(0, "src")
from openconverter import __version__  # noqa: E402

datas = [('assets', 'assets')]
binaries = []
hiddenimports = ['PIL', 'PIL._imaging', 'openconverter', 'openconverter.gui.tk_app']
tmp_ret = collect_all('customtkinter')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('tkinterdnd2')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]

# Windows y macOS: "Open Converter". Linux: sin espacios, más cómodo en la terminal.
APP_NAME = 'open-converter' if sys.platform.startswith("linux") else 'Open Converter'
ICON = 'assets/icon.ico' if IS_WIN else ('assets/icon.icns' if IS_MAC else None)

a = Analysis(
    ['launcher.py'],
    pathex=['src'],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=APP_NAME,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=IS_WIN,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=[ICON] if ICON else None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=IS_WIN,
    upx_exclude=[],
    name=APP_NAME,
)

if IS_MAC:
    app = BUNDLE(
        coll,
        name='Open Converter.app',
        icon='assets/icon.icns',
        bundle_identifier='com.macross95.openconverter',
        version=__version__,
        info_plist={
            'CFBundleDisplayName': 'Open Converter',
            'CFBundleShortVersionString': __version__,
            'NSHighResolutionCapable': True,
            'LSMinimumSystemVersion': '11.0',
            # Que Finder ofrezca "Abrir con Open Converter" para las imágenes
            'CFBundleDocumentTypes': [{
                'CFBundleTypeName': 'Imagen',
                'CFBundleTypeRole': 'Viewer',
                'LSHandlerRank': 'Alternate',
                'LSItemContentTypes': ['public.image'],
            }],
        },
    )
