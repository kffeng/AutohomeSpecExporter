# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

root = Path(SPECPATH).resolve().parent
icon = str(root / "assets" / "icon.ico")
version_file = str(root / "packaging" / "version_info.txt")

datas = [
    (str(root / "web"), "web"),
    (str(root / "assets" / "icon.png"), "assets"),
]
datas += collect_data_files("openpyxl")
datas += collect_data_files("certifi")
hiddenimports = collect_submodules("openpyxl") + collect_submodules("truststore") + [
    "certifi",
    "truststore",
    "flask",
    "flask.json",
    "werkzeug.serving",
]

a = Analysis(
    [str(root / "main.py")],
    pathex=[str(root)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "pytest"],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="AutohomeSpecExporter",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=icon,
    version=version_file,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="AutohomeSpecExporter",
)
