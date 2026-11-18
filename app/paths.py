"""Where BabelChat keeps its files: in its own folder, and nowhere else.

Everything the app writes (settings, translation cache, logs, the lock file,
the translation models) lives in one folder:

- the built app: the folder that holds BabelChat.exe
- from source: the project folder (the one that holds `app/`)

So the whole install is that one folder, and deleting it removes everything.
The only files outside it are the addon copied into WoW's Interface\\AddOns.
"""

from __future__ import annotations

import sys
from pathlib import Path


def app_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def data_file(name: str) -> Path:
    """A file in the app's folder."""
    return app_dir() / name
