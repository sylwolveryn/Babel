"""Convert the OPUS-MT models the app uses into CTranslate2 format, once.

    .venv/Scripts/python -m pip install -r requirements-opusmt-convert.txt
    .venv/Scripts/python tools/prepare_opusmt.py

Downloads the official Helsinki-NLP/opus-mt-en-hu and opus-mt-hu-en models
(~300 MB each) and writes int8 CTranslate2 copies (~80 MB each) to `models/` in
the project folder, or BABELCHAT_MODELS_DIR. The download cache stays in
`models/.download-cache`, inside the project too. After that
the app needs only ctranslate2 and sentencepiece; torch and transformers can be
uninstalled.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.translators import opusmt_provider as opus  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--force", action="store_true", help="convert again even if a model is already there")
    args = parser.parse_args(argv)

    if not opus.can_convert():
        print("Converting needs transformers and torch: pip install -r requirements-opusmt-convert.txt")
        return 1
    for source, target in opus.MODELS:
        path = opus.model_path(source, target)
        if opus.is_converted(path) and not args.force:
            print(f"{source}->{target}: already at {path}")
            continue
        print(f"{source}->{target}: converting {opus.MODELS[(source, target)]} ...", flush=True)
        print(f"   -> {opus.convert(source, target)}")
    print(f"Models folder: {opus.models_dir()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
