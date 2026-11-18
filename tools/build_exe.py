"""Build BabelChat.exe into dist/, with everything it needs beside it.

    .venv/Scripts/python -m pip install pyinstaller
    .venv/Scripts/python tools/build_exe.py

Result:

    dist/
      BabelChat.exe     the app
      _internal/        Python, Qt and the app's code (do not separate from the exe)
      models/           the two translation models, copied from models/

The folder is the whole install and is portable: settings, cache and logs are
written there too (app/paths.py), and nothing in it names a path, so it runs
from wherever it is copied. PyInstaller's own
intermediate files go to build/, inside the project.

Needs the models converted first (tools/prepare_opusmt.py) unless
--no-models is given.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.translators import opusmt_provider as opus  # noqa: E402

DIST = ROOT / "dist"
BUILD = ROOT / "build"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--no-models", action="store_true", help="build without copying the models in")
    args = parser.parse_args(argv)

    models = [opus.model_path(s, t) for s, t in opus.MODELS]
    if not args.no_models:
        missing = [m for m in models if not opus.is_converted(m)]
        if missing:
            print("Models missing — run tools/prepare_opusmt.py first:")
            for m in missing:
                print(f"   {m}")
            return 1

    if not (ROOT / "app" / "babelchat_scanner_win.dll").is_file():
        print("app/babelchat_scanner_win.dll is missing — build babelchat_scanner_win first.")
        return 1

    exe = DIST / "BabelChat.exe"
    if exe.exists():
        try:
            with open(exe, "r+b"):
                pass
        except PermissionError:
            print("dist/BabelChat.exe is running — close BabelChat first.")
            return 1

    staging = BUILD / "pyinstaller-dist"
    subprocess.run(
        [
            sys.executable,
            "-m",
            "PyInstaller",
            "build.spec",
            "--noconfirm",
            "--clean",
            "--distpath",
            str(staging),
            "--workpath",
            str(BUILD / "pyinstaller-work"),
        ],
        cwd=ROOT,
        check=True,
    )

    # dist/ is rebuilt from scratch: nothing from an earlier run (settings,
    # cache, logs) is carried into a fresh build.
    if DIST.exists():
        shutil.rmtree(DIST)
    DIST.mkdir(exist_ok=True)
    for item in (staging / "BabelChat").iterdir():
        shutil.move(str(item), DIST / item.name)

    if not args.no_models:
        for m in models:
            shutil.copytree(m, DIST / "models" / m.name)

    size = sum(f.stat().st_size for f in DIST.rglob("*") if f.is_file()) / 1e6
    print(f"\nBuilt {DIST / 'BabelChat.exe'}  ({size:.0f} MB in dist/)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
