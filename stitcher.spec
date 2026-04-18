# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec для Stitcher CLI.
Точка входа: main.py
Режим: --onedir (папка с EXE и зависимостями)
"""

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=['.'],
    binaries=[],
    datas=[
        ('profiles', 'profiles'),
    ],
    hiddenimports=[
        'app.config',
        'app.config.config_loader',
        'app.config.settings',
        'app.models',
        'app.models.domain',
        'app.runtime',
        'app.runtime.paths',
        'app.runtime.logging_config',
        'app.runtime.env_loader',
        'app.runtime.cleanup',
        'app.runtime.ytdlp_updater',
        'app.google',
        'app.google.auth',
        'app.google.sheets_client',
        'app.ingest',
        'app.ingest.language_detector',
        'app.ingest.link_normalizer',
        'app.ingest.youtube_metadata',
        'app.input',
        'app.input.row_enricher',
        'app.input.sheet_parser',
        'app.input.sheet_reader',
        'app.download',
        'app.download.video_downloader',
        'app.download.thumbnail_fetcher',
        'app.transcode',
        'app.transcode.video_normalizer',
        'app.transcode.thumbnail_clip',
        'app.transcode.fade_clip',
        'app.ffmpeg',
        'app.ffmpeg.command_builder',
        'app.ffmpeg.codec_fallback',
        'app.concat',
        'app.concat.manifest_builder',
        'app.concat.final_concat',
        'app.worker',
        'app.worker.pipeline',
        'app.worker.progress',
        'dotenv',
        'google.auth',
        'google.oauth2',
        'google.oauth2.credentials',
        'google_auth_oauthlib',
        'googleapiclient',
        'googleapiclient.discovery',
        'langdetect',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'aiogram',
        'app.bot',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='stitcher',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
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
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='stitcher',
)
