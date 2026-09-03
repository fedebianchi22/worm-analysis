# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all

datas = [
    ("app.py", "."),
    ("measure_worms.py", "."),
    ("reporte_excel.py", "."),
    ("pen_editor.py", "."),
    ("pen_editor/index.html", "pen_editor"),
    (".streamlit/config.toml", ".streamlit"),
]
binaries = []
hiddenimports = []

for pkg in ["streamlit", "altair", "pyarrow", "pandas", "numpy", "scipy", "skimage", "networkx", "cv2"]:
    d, b, h = collect_all(pkg)
    datas += d
    binaries += b
    hiddenimports += h

a = Analysis(
    ["launcher.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports + [
        "numpy.core._exceptions",
        "numpy._core._exceptions",
        "numpy.core.multiarray",
        "numpy._core.multiarray",
        "scipy._cyutility",
        "scipy.special._cdflib",
    ],
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
    name="CElegansLab",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    icon=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    name="CElegansLab",
)
