# -*- mode: python ; coding: utf-8 -*-

a = Analysis(
    ['workbench-launcher.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('teacher-workbench.html', '.'),
        ('manifest.json', '.'),
        ('sw.js', '.'),
        ('libs', 'libs'),
        ('icons', 'icons'),
    ],
    hiddenimports=[
        # pywebview
        'webview', 'webview.platforms.winforms',
        'clr_loader', 'pythonnet',
        # Flask core
        'flask', 'flask.json', 'flask.wrappers', 'flask.helpers',
        'flask_cors',
        # Flask-SocketIO + engineio
        'flask_socketio',
        'socketio', 'socketio.async_drivers.threading',
        'engineio', 'engineio.async_drivers', 'engineio.async_drivers.threading',
        'engineio.async_threading', 'engineio.payload',
        # simple-websocket
        'simple_websocket',
        # Werkzeug
        'werkzeug', 'werkzeug.serving', 'werkzeug.debug',
        'werkzeug.middleware', 'werkzeug.middleware.proxy_fix',
        # Jinja2
        'jinja2', 'jinja2.ext',
        # Other Flask deps
        'markupsafe', 'itsdangerous', 'click', 'blinker', 'bidict',
        # Stdlib that PyInstaller may miss
        'json', 'threading', 'datetime', 'urllib',
        'http', 'http.server', 'socketserver',
        'wsproto', 'h11',
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
    name='班主任工作台',
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
    icon=None,
)
