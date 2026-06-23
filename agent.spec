# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_submodules
from PyInstaller.utils.hooks import copy_metadata

datas = []
hiddenimports = ['pydantic_settings']
datas += copy_metadata('pydantic')
datas += copy_metadata('pydantic_settings')
hiddenimports += collect_submodules('agent')
hiddenimports += collect_submodules('httpx')
hiddenimports += collect_submodules('pydantic')
hiddenimports += collect_submodules('pydantic_settings')


a = Analysis(
    ['src/agent/cli.py'],
    pathex=['src'],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['pandas', 'numpy', 'sklearn', 'scipy', 'fastapi', 'uvicorn', 'starlette', 'matplotlib', 'joblib', 'PyQt5', 'PyQt6', 'PySide2', 'PySide6', 'wx', 'gtk', 'IPython', 'jupyter', 'notebook', 'pytest'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='agent',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
