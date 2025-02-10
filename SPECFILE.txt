# -*- mode: python ; coding: utf-8 -*-


block_cipher = None

# Import collect_submodules and collect_data_files for numpy
from PyInstaller.utils.hooks import collect_submodules, collect_data_files

# Include numpy dependencies
hiddenimports = collect_submodules('numpy')
datas = collect_data_files('numpy')

a = Analysis(
    ['MT5Futures.py'],
    pathex=[],
    binaries=[],
    datas=datas,  # Add the numpy data files
    hiddenimports=hiddenimports,  # Add the numpy hidden imports
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
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
    name='Test3',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
