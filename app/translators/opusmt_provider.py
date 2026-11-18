"""OPUS-MT: Helsinki-NLP's small Marian models, run locally with CTranslate2.

The app's only translator. Two models cover its one language pair:

    Helsinki-NLP/opus-mt-en-hu   incoming chat, English -> Hungarian
    Helsinki-NLP/opus-mt-hu-en   the reply box, Hungarian -> English

They run through CTranslate2 as int8 — measured on the comparison corpus
(tools/compare_translators.py) about five times faster than the same models in
PyTorch, at the same quality — and need only `ctranslate2` and
`sentencepiece` at runtime. Nothing leaves the machine and there is no quota.

The models are converted from the official Helsinki-NLP releases, once, into
the `models` folder beside the app (see `models_dir`). That step needs `transformers` and
`torch`; `tools/prepare_opusmt.py` does it, and so does this provider on
first use when those packages happen to be installed.
"""

from __future__ import annotations

import logging
import os
import shutil
import threading
from pathlib import Path
from typing import Any

from app.paths import app_dir
from app.translators.base import (
    ProviderSpec,
    TranslationResult,
    failed,
    register,
)

logger = logging.getLogger(__name__)

PROVIDER_ID = "opusmt"

#: (source, target) -> Hugging Face model id of the official release.
MODELS: dict[tuple[str, str], str] = {
    ("EN", "HU"): "Helsinki-NLP/opus-mt-en-hu",
    ("HU", "EN"): "Helsinki-NLP/opus-mt-hu-en",
}

UNSUPPORTED_PAIR = "unsupported_language_pair"
MODEL_ERROR = "opusmt_model_error"

#: Set to any value to keep OPUS-MT from being built — the test suite does,
#: so that no test run ever loads, converts or downloads a model.
DISABLE_ENV = "BABELCHAT_DISABLE_OPUSMT"
#: Where the converted models live, if not the default.
MODELS_DIR_ENV = "BABELCHAT_MODELS_DIR"

#: Files a converted model folder needs, beside CTranslate2's own.
_SPM_FILES = ("source.spm", "target.spm")

#: One conversion at a time across the whole process. The app builds more than
#: one translator (chat and the reply box), and two conversions running at
#: once break inside transformers ("aten::equal ... Meta tensors").
_CONVERT_LOCK = threading.Lock()


def models_dir() -> Path:
    """`models` in the app's own folder (see app/paths.py)."""
    override = os.environ.get(MODELS_DIR_ENV)
    if override:
        return Path(override)
    return app_dir() / "models"


def hf_cache_dir() -> Path:
    """Where a conversion keeps what it downloads — inside the app's folder
    too, instead of Hugging Face's default in the user's home folder."""
    return models_dir() / ".download-cache"


def model_path(source: str, target: str) -> Path:
    return models_dir() / f"opus-mt-{source.lower()}-{target.lower()}-ct2"


def is_converted(path: Path) -> bool:
    return (path / "model.bin").is_file() and all((path / f).is_file() for f in _SPM_FILES)


def runtime_missing() -> str:
    """Missing runtime packages, or "" when CTranslate2 can run."""
    if os.environ.get(DISABLE_ENV):
        return f"nothing ({DISABLE_ENV} is set)"
    missing = []
    for module in ("ctranslate2", "sentencepiece"):
        try:
            __import__(module)
        except ImportError:
            missing.append(module)
    return ", ".join(missing)


def can_convert() -> bool:
    try:
        import huggingface_hub  # noqa: F401
        import torch  # noqa: F401
        import transformers  # noqa: F401
    except ImportError:
        return False
    return True


def convert(source: str, target: str, quantization: str = "int8") -> Path:
    """Convert the official model for a pair into the models folder.

    Needs `transformers` and `torch`; the result needs neither. The tokenizer
    files are copied alongside, so the folder is all the runtime reads.
    """
    # Before transformers or huggingface_hub read it, so the download lands
    # in the app's folder and not in ~/.cache/huggingface.
    os.environ["HF_HOME"] = str(hf_cache_dir())
    import ctranslate2
    from huggingface_hub import hf_hub_download

    model_id = MODELS[(source.upper(), target.upper())]
    out = model_path(source, target)
    out.parent.mkdir(parents=True, exist_ok=True)
    partial = out.with_name(out.name + ".partial")
    if partial.exists():
        shutil.rmtree(partial)
    logger.info("Converting %s to CTranslate2 (%s) in %s", model_id, quantization, out)
    ctranslate2.converters.TransformersConverter(model_id).convert(str(partial), quantization=quantization)
    for name in _SPM_FILES:
        shutil.copy(hf_hub_download(model_id, name), partial / name)
    # Only a complete folder takes the real name, so an interrupted conversion
    # is never mistaken for a model.
    if out.exists():
        shutil.rmtree(out)
    partial.rename(out)
    return out


class _LoadedModel:
    def __init__(self, translator: Any, source_sp: Any, target_sp: Any) -> None:
        self.translator = translator
        self.source_sp = source_sp
        self.target_sp = target_sp


def _load(path: Path) -> _LoadedModel:
    import ctranslate2
    import sentencepiece

    # Two threads per model: enough for a chat line in well under a tenth of a
    # second, and it leaves the rest of the CPU to the game.
    translator = ctranslate2.Translator(str(path), device="cpu", compute_type="int8", intra_threads=2)
    source_sp = sentencepiece.SentencePieceProcessor(model_file=str(path / "source.spm"))
    target_sp = sentencepiece.SentencePieceProcessor(model_file=str(path / "target.spm"))
    return _LoadedModel(translator, source_sp, target_sp)


def _generate(loaded: _LoadedModel, text: str) -> str:
    # Marian's input is the sentencepiece pieces plus the end-of-sentence
    # marker; its output is pieces again, joined back by the target model.
    tokens = loaded.source_sp.encode(text, out_type=str) + ["</s>"]
    result = loaded.translator.translate_batch([tokens], beam_size=4, max_decoding_length=256)
    pieces = [piece for piece in result[0].hypotheses[0] if piece != "</s>"]
    return loaded.target_sp.decode(pieces)


class OpusMtBackend:
    """Translates with whichever OPUS-MT model covers the requested pair."""

    def __init__(self, loader=None, auto_convert: bool = True) -> None:
        self._loader = loader or self._load_or_convert
        self._auto_convert = auto_convert
        self._models: dict[tuple[str, str], _LoadedModel] = {}
        # A pair that failed to load stays failed until the app restarts, so a
        # missing model costs one attempt (and one download try), not one per line.
        self._failed: dict[tuple[str, str], str] = {}
        self._lock = threading.Lock()

    def _load_or_convert(self, source: str, target: str) -> _LoadedModel:
        path = model_path(source, target)
        if not is_converted(path):
            if not (self._auto_convert and can_convert()):
                raise FileNotFoundError(f"no converted model at {path}; run tools/prepare_opusmt.py")
            with _CONVERT_LOCK:
                # Another translator may have converted it while this one waited.
                if not is_converted(path):
                    convert(source, target)
        return _load(path)

    def _model_for(self, source: str, target: str) -> _LoadedModel:
        key = (source, target)
        loaded = self._models.get(key)
        if loaded is not None:
            return loaded
        with self._lock:
            loaded = self._models.get(key)
            if loaded is None:
                if key in self._failed:
                    raise RuntimeError(self._failed[key])
                logger.info("Loading OPUS-MT %s->%s", source, target)
                try:
                    loaded = self._loader(source, target)
                except Exception as e:
                    self._failed[key] = f"{type(e).__name__}: {e} (restart the app to try again)"
                    raise
                self._models[key] = loaded
        return loaded

    def warm_up(self, source_lang: str = "EN", target_lang: str = "HU") -> None:
        """Load a model ahead of the first message, so that one is not slow."""
        try:
            self._model_for(source_lang.upper(), target_lang.upper())
        except Exception as e:  # reported again, as a failure, on first real use
            logger.warning("OPUS-MT warm-up failed for %s->%s: %s", source_lang, target_lang, e)

    def translate(self, text: str, target_lang: str, source_lang: str | None = None) -> TranslationResult:
        source = (source_lang or "").upper()
        target = target_lang.upper()
        if (source, target) not in MODELS:
            return failed(text, target_lang, source_lang, UNSUPPORTED_PAIR, PROVIDER_ID)

        try:
            # CTranslate2's Translator is safe to call from several threads.
            translated = _generate(self._model_for(source, target), text)
        except Exception as e:
            logger.warning("OPUS-MT failed on %s->%s: %s", source, target, e)
            return failed(text, target_lang, source_lang, MODEL_ERROR, PROVIDER_ID)

        if not translated.strip():
            return failed(text, target_lang, source_lang, MODEL_ERROR, PROVIDER_ID)
        return TranslationResult(
            original=text,
            translated=translated.strip(),
            source_lang=source,
            target_lang=target_lang,
            success=True,
            backend=PROVIDER_ID,
        )


def models_ready() -> bool:
    """Both directions are converted and on disk."""
    return all(is_converted(model_path(s, t)) for s, t in MODELS)


def _models_obtainable() -> bool:
    return models_ready() or can_convert()


def _build() -> OpusMtBackend:
    missing = runtime_missing()
    if missing:
        raise RuntimeError(f"OPUS-MT needs {missing} (pip install -r requirements.txt)")
    if not _models_obtainable():
        raise RuntimeError(f"OPUS-MT has no models in {models_dir()}; run tools/prepare_opusmt.py")
    backend = OpusMtBackend()

    # Both directions in the background: incoming chat first, then the reply
    # box, so neither the first line nor the first reply waits on a load.
    def warm_both() -> None:
        backend.warm_up("EN", "HU")
        backend.warm_up("HU", "EN")

    threading.Thread(target=warm_both, name="opusmt-warmup", daemon=True).start()
    return backend


SPEC = register(ProviderSpec(id=PROVIDER_ID, display_name="OPUS-MT", build=_build))
