# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['agenda.py'],
    pathex=[],
    binaries=[],
    datas=[('static/*', 'static'), ('templates/*', 'templates'),('templates/users.json', 'templates')],
    hiddenimports=[],
    hookspath=[],
    runtime_hooks=[],
    excludes=[]
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='agenda',
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
