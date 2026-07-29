# -*- mode: python ; coding: utf-8 -*-
"""
OIHK Basic Backend — PyInstaller spec for sidecar compilation.

Build the backend into a single executable that can be bundled with Tauri.

Usage:
    pyinstaller oihk-basic-backend.spec

Output: dist/oihk-basic-backend/
"""

import os

block_cipher = None

a = Analysis(
    ['backend/run.py'],
    pathex=['backend'],
    binaries=[],
    datas=[],
    hiddenimports=[
        'app',
        'app.core',
        'app.middleware',
        'app.routers',
        'app.services',
        'app.forensic',
        'app.forensic.extraction',
        'app.forensic.hashing',
        'app.forensic.ioc',
        'app.forensic.metadata',
        'app.forensic.mime',
        'app.forensic.timeline',
        'app.forensic.web',
        'app.forensic.yara',
        'app.investigation',
        'app.investigation.modules',
        'app.transforms',
        'app.schemas',
        'app.models',
        'app.database',
        'app.database_migrations',
        'app.core.update_service',
        'app.middleware.update_gate',
        'app.routers.updates',
        'sqlalchemy',
        'aiosqlite',
        'uvicorn',
        'httpx',
        'cryptography',
        'orjson',
        'pydantic',
        'pydantic_settings',
        'multipart',
        'PIL',
        'yaml',
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
    a.binaries,
    a.datas,
    [],
    name='oihk-basic-backend',
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
    icon='src-tauri/icons/icon.ico' if os.path.exists('src-tauri/icons/icon.ico') else None,
)
