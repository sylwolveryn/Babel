# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for BabelChat: BabelChat.exe with its files beside it.

A folder build, not a single file: a one-file .exe unpacks itself into the
system temp folder on every start, and the app keeps everything it writes in
its own folder (app/paths.py). Run tools/build_exe.py rather than this spec
directly: it also copies the translation models in and puts the result in dist/.
"""

a = Analysis(
    ["app/main.py"],
    pathex=["."],
    binaries=[('app/babelchat_scanner_win.dll', '.')],
    datas=[
        ("assets/icon.ico", "assets"),
        ("assets/icon.png", "assets"),
        ("addon/BabelChat", "addon/BabelChat"),
    ],
    hiddenimports=[
        "watchdog",
        "watchdog.observers",
        "watchdog.events",
        "PyQt6",
        "PyQt6.QtCore",
        "PyQt6.QtGui",
        "PyQt6.QtWidgets",
        "dotenv",
        "app.watcher",
        "app.parser",
        "app.detector",
        "app.translator",
        "app.cache",
        "app.pipeline",
        "app.overlay",
        "app.tray",
        "app.config",
        "app.settings_dialog",
        "app.setup_wizard",
        "app.branding",
        "app.hotkeys",
        "app.hotkeys_windows",
        "app.text_utils",
        "app.memory_reader",
        "app.memory_reader_windows",
        "pymem",
        "pymem.process",
        "pymem.exception",
        "app.i18n",
        "app.phrasebook",
        "app.slang",
        # The translator. The models are not inside the bundle: they sit in
        # `models` beside BabelChat.exe, where tools/build_exe.py copies them.
        "app.translators",
        "app.translators.opusmt_provider",
        "app.postedit",
        "app.paths",
        "ctranslate2",
        "sentencepiece",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "tkinter",
        "matplotlib",
        "scipy",
        "PIL",
        # Only converting a model needs these; the app never imports them, and
        # torch alone would add over a gigabyte.
        "torch",
        "transformers",
        "huggingface_hub",
        "sacremoses",
        "argostranslate",
        "stanza",
        "psutil",
        "requests",
        # Pulled in by package hooks, never imported by the app (checked by
        # importing everything it runs and listing sys.modules).
        "numpy",
        "google",
        "yaml",
        "regex",
        "charset_normalizer",
        "urllib3",
        "pytest",
        "lupa",
    ],
    noarchive=False,
)

# Qt pieces a widgets-only app never loads: the software OpenGL renderer
# (21 MB), networking, SVG, Qt's own translations, and image plugins other than
# the .ico reader the window icon needs.
_QT_DROP = (
    "opengl32sw.dll",
    "qt6network.dll",
    "qt6svg.dll",
    "/translations/",
    "/iconengines/",
    "/generic/",
)


def _keep(entry):
    path = entry[0].replace("\\", "/").lower()
    if any(part in path for part in _QT_DROP):
        return False
    if "/imageformats/" in path and not path.endswith("qico.dll"):
        return False
    return True


a.binaries = [b for b in a.binaries if _keep(b)]
a.datas = [d for d in a.datas if _keep(d)]

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="BabelChat",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    icon="assets/icon.ico",
    # Reading another process owned by the same user needs PROCESS_VM_READ and
    # PROCESS_QUERY_INFORMATION, which Windows grants from the target's own
    # DACL. The scanner asks for exactly those. Elevation was only ever needed
    # by the pymem fallback's PROCESS_ALL_ACCESS open, which no longer happens —
    # and standing administrator rights turned an ordinary DLL-planting bug into
    # a privilege escalation.
    uac_admin=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="BabelChat",
)
