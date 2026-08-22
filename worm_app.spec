# -*- mode: python ; coding: utf-8 -*-
import streamlit
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

streamlit_data = collect_data_files("streamlit")
streamlit_hidden = collect_submodules("streamlit")

a = Analysis(
    ["launcher.py"],
    pathex=[],
    binaries=[],
    datas=streamlit_data + [("app.py", "."), ("measure_worms.py", ".")],
    hiddenimports=streamlit_hidden + ["skimage.morphology", "networkx"],
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
    a.binaries,
    a.datas,
    [],
    name="MedicionGusanos",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    icon=None,
)
