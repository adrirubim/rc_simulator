# -*- mode: python ; coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path

from PyInstaller.building.build_main import Analysis, EXE, PYZ
from PyInstaller.building.datastruct import Tree

block_cipher = None


# PyInstaller typically defines SPECPATH (directory containing this .spec).
# Some environments may execute the spec without defining __file__.
ROOT = Path(globals().get("SPECPATH", Path.cwd())).resolve()
ENTRYPOINT = ROOT / "src" / "rc_simulator" / "ui_qt" / "app.py"

# Bundle all runtime assets so importlib.resources can resolve them inside the executable.
# This lands under: <bundle>/rc_simulator/resources/...
RESOURCES_DIR = ROOT / "src" / "rc_simulator" / "resources"
if RESOURCES_DIR.exists():
    _tree = Tree(str(RESOURCES_DIR), prefix="rc_simulator/resources")
    # PyInstaller's Tree may yield 2-tuples or 3-tuples like (dest, src, typecode).
    # Analysis(datas=...) expects (src, dest) pairs.
    DATAS = []
    for item in _tree:
        try:
            dest, src, _typecode = item
        except ValueError:
            dest, src = item
        DATAS.append((src, dest))
else:
    DATAS = []

# Optional Windows .ico for the produced EXE. (If missing, we skip setting an icon.)
ICON_ICO = ROOT / "src" / "rc_simulator" / "resources" / "icons" / "rc-simulator.ico"
ICON = str(ICON_ICO) if ICON_ICO.exists() else None


# Toggle between one-file and one-dir builds:
# - ONEFILE = True  => easier distribution, slower startup
# - ONEFILE = False => faster startup, folder-based distribution
ONEFILE = True


a = Analysis(
    [str(ENTRYPOINT)],
    pathex=[str(ROOT / "src")],
    binaries=[],
    datas=DATAS,
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="rc-simulator",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # --noconsole / windowed
    icon=ICON,
)

if ONEFILE:
    exe = exe
else:
    # One-dir build is produced by default when using a COLLECT step.
    # We keep this spec single-purpose (onefile) unless you flip ONEFILE=False.
    from PyInstaller.building.build_main import COLLECT

    coll = COLLECT(
        exe,
        a.binaries,
        a.zipfiles,
        a.datas,
        strip=False,
        upx=True,
        upx_exclude=[],
        name="rc-simulator",
    )

