# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec — 말랑몰랑 (MallangMollang)
# 빌드: pyinstaller mallangmollang.spec

import sys
from pathlib import Path

block_cipher = None

a = Analysis(
    ['mallangmollang/__main__.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[
        # PyQt6 플러그인
        'PyQt6.QtWidgets',
        'PyQt6.QtCore',
        'PyQt6.QtGui',
        # pynput 백엔드 (Windows)
        'pynput.keyboard._win32',
        'pynput.mouse._win32',
        # 암호화
        'cryptography.fernet',
        # win32 API
        'win32gui',
        'win32con',
        'win32process',
        'win32api',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # 불필요한 대형 모듈 제외
        'tkinter',
        'matplotlib',
        'numpy.testing',
        'scipy',
        'pandas',
    ],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='MallangMollang',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,          # GUI 앱이므로 콘솔 창 숨김
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='MallangMollang',
)
