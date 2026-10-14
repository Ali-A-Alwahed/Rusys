# -*- mode: python ; coding: utf-8 -*-
# Rusys 26.10.14 — portable onefile build.
# Licensed under GPL-3.0-or-later.
# Requires: pyinstaller>=6.22.3, PySide6>=6.12,<6.13, requests>=2.34.2
# No collect_all: PyInstaller hooks pull only used Qt modules (keeps size down).
# Heavy unused Qt modules are excluded explicitly.
#
# NOTE: resources/ contains GPL-3.0 third-party sources (Rufus, Ventoy,
# grub2-themes). Those files retain their own upstream licenses; see
# THIRD_PARTY_NOTICES.md. This project as a whole is GPL-3.0-or-later.

a = Analysis(
    ['rusys_launcher.py'],
    pathex=[],
    binaries=[],
    datas=[('resources', 'resources')],
    hiddenimports=['rusys', 'rusys.core', 'rusys.ui', 'rusys.data'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'PySide6.QtWebEngine', 'PySide6.QtWebEngineCore', 'PySide6.QtWebEngineWidgets',
        'PySide6.QtWebEngineQuick', 'PySide6.QtWebChannel', 'PySide6.QtWebSockets',
        'PySide6.QtWebView', 'PySide6.QtQml', 'PySide6.QtQuick', 'PySide6.QtQuickWidgets',
        'PySide6.QtQuickControls2', 'PySide6.QtQuick3D', 'PySide6.Qt3DCore',
        'PySide6.Qt3DRender', 'PySide6.Qt3DAnimation', 'PySide6.Qt3DExtras',
        'PySide6.Qt3DInput', 'PySide6.Qt3DLogic', 'PySide6.QtCharts',
        'PySide6.QtDataVisualization', 'PySide6.QtGraphs', 'PySide6.QtGraphsWidgets',
        'PySide6.QtMultimedia', 'PySide6.QtMultimediaWidgets', 'PySide6.QtBluetooth',
        'PySide6.QtNfc', 'PySide6.QtSensors', 'PySide6.QtSerialBus', 'PySide6.QtSerialPort',
        'PySide6.QtPositioning', 'PySide6.QtLocation', 'PySide6.QtTextToSpeech',
        'PySide6.QtPdf', 'PySide6.QtPdfWidgets', 'PySide6.QtHelp',
        'PySide6.QtDesigner', 'PySide6.QtUiTools', 'PySide6.QtTest',
        'PySide6.QtStateMachine', 'PySide6.QtScxml', 'PySide6.QtRemoteObjects',
        'PySide6.QtNetworkAuth', 'PySide6.QtSql', 'PySide6.QtPrintSupport',
        'PySide6.QtOpenGLWidgets', 'PySide6.QtSpatialAudio',
        'PySide6.scripts', 'PySide6.support',
        'tkinter', 'unittest', 'pydoc', 'doctest',
    ],
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
    name='Rusys',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    icon='resources/icons/rusys.ico',
    version='version_info.txt',
    manifest='Rusys.exe.manifest',
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
