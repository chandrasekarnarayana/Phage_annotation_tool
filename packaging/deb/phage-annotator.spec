# PyInstaller spec for Phage Annotator (onedir bundle).
#
# Scientific-stack packages (scikit-learn, scikit-image, scipy, pandas,
# matplotlib) and the icon-font packages (qtawesome, simpleicons) are
# notorious for PyInstaller missing dynamically-loaded submodules or data
# files, so we collect them broadly rather than relying on PyInstaller's
# default import analysis alone.

from PyInstaller.utils.hooks import collect_all

datas = []
binaries = []
hiddenimports = []

for pkg in (
    "sklearn",
    "skimage",
    "scipy",
    "pandas",
    "matplotlib",
    "qtawesome",
    "simpleicons",
    "lmfit",
    "asteval",
    "uncertainties",
    "tifffile",
    "PyQt5",
):
    pkg_datas, pkg_binaries, pkg_hiddenimports = collect_all(pkg)
    datas += pkg_datas
    binaries += pkg_binaries
    hiddenimports += pkg_hiddenimports

hiddenimports += [
    "phage_annotator",
]

a = Analysis(
    ["entrypoint.py"],
    pathex=["src"],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "PySide2", "PySide6", "PyQt6"],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="phage-annotator",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="phage-annotator",
)
