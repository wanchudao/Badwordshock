# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_dynamic_libs, collect_data_files

datas = collect_dynamic_libs('ctranslate2')
datas += collect_data_files('faster_whisper')


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[
        ('C:/Users/Max/AppData/Roaming/Python/Python311/site-packages/torch/lib/cublas64_12.dll', '.'),
        ('C:/Users/Max/AppData/Roaming/Python/Python311/site-packages/torch/lib/cudart64_12.dll', '.'),
    ],
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
    # 过滤 collect_data_files('faster_whisper') 拖入的冗余 torch/lib DLL
    [(n, p, t) for n, p, t in a.binaries if not n.replace('\\', '/').startswith('torch/lib/')],
    [(n, p, t) for n, p, t in a.datas    if not n.replace('\\', '/').startswith('torch/lib/')],
    strip=False,
    upx=True,
    upx_exclude=[],
    name='badwordshock',
)
