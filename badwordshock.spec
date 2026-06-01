# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_dynamic_libs, collect_data_files

datas = collect_dynamic_libs('ctranslate2')
datas += collect_data_files('faster_whisper')


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[('C:/Users/Max/AppData/Roaming/Python/Python311/site-packages/torch/lib/cublas64_12.dll', '.')],
    datas=datas,
    hiddenimports=['faster_whisper', 'numpy', 'sounddevice'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['torch', 'transformers', 'accelerate'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='badwordshock',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    # 过滤 collect_data_files('faster_whisper') 拖入的冗余 torch/lib DLL
    [(src, dst) for src, dst in a.datas if not dst.replace('\\', '/').startswith('torch/lib/')],
    strip=False,
    upx=True,
    upx_exclude=[],
    name='badwordshock',
)
