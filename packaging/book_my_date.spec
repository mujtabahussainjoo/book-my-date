# -*- mode: python ; coding: utf-8 -*-
import re
import sys
from pathlib import Path

ROOT = Path(SPECPATH).parent
CONFIG = (ROOT / "book_my_date" / "config.py").read_text(encoding="utf-8")
VERSION = re.search(r'VERSION\s*=\s*"([^"]+)"', CONFIG).group(1)
ASSETS = ROOT / "book_my_date" / "assets"
ICON_PNG = ASSETS / "app_icon.png"
ICON_ICO = ASSETS / "app.ico"
ICON_ICNS = ASSETS / "app.icns"

a = Analysis(
    [str(ROOT / "packaging" / "entrypoint.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=[(str(ASSETS), "book_my_date/assets")],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="BookMyDate",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    icon=str(ICON_ICO if sys.platform == "win32" else ICON_PNG),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="BookMyDate",
)

if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name="Book My Date.app",
        icon=str(ICON_ICNS),
        bundle_identifier="io.bookmydate.app",
        info_plist={
            "CFBundleName": "Book My Date",
            "CFBundleDisplayName": "Book My Date",
            "CFBundleShortVersionString": VERSION,
            "CFBundleVersion": VERSION,
            "NSHighResolutionCapable": True,
            "LSMinimumSystemVersion": "10.15",
            "LSApplicationCategoryType": "public.app-category.productivity",
        },
    )
