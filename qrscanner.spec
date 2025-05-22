# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['qr_main.py'],
    pathex=['C:\\Users\\samue\\Documents\\Projects\\QR_SCREEN_CAPTURE'],
    binaries=[
        ('C:\\Users\\samue\\Documents\\Projects\\QR_SCREEN_CAPTURE\\libiconv.dll', '.'),
        ('C:\\Users\\samue\\Documents\\Projects\\QR_SCREEN_CAPTURE\\libzbar-64.dll', '.')
    ],
    datas=[
        ('C:\\Users\\samue\\Documents\\Projects\\QR_SCREEN_CAPTURE\\frames', 'frames')
    ],
    hiddenimports=[],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher
)

pyz = PYZ(
    a.pure,
    a.zipped_data,
    cipher=block_cipher
)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,  # exclude binaries, add with COLLECT normally
    name='QR Barcode Scanner',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    icon='C:\\Users\\samue\\Documents\\Projects\\QR_SCREEN_CAPTURE\\frames\\favicon.ico',
    manifest='C:\\Users\\samue\\Documents\\Projects\\QR_SCREEN_CAPTURE\\app.manifest'
)

# For single file build, use MERGE of binaries and exe with EXE(..., onefile=True)

app = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    name='scanner',
    debug=False,
    strip=False,
    version='version.txt',
    upx=True,
    console=False,
    bootloader_ignore_signals=False,
    icon='C:\\Users\\samue\\Documents\\Projects\\QR_SCREEN_CAPTURE\\frames\\favicon.ico',
    manifest='C:\\Users\\samue\\Documents\\Projects\\QR_SCREEN_CAPTURE\\app.manifest',
    onefile=True,
)
