"""The local OPUS-MT provider, with CTranslate2 replaced by fakes.

No test here loads, converts or downloads a model: `_generate` (the one call
into CTranslate2 and sentencepiece) is monkeypatched, and the backend is handed
a loader that returns a stand-in for the loaded model.
"""

from __future__ import annotations

import pytest

from app.paths import app_dir
from app.translators import TranslatorService
from app.translators import opusmt_provider as opus


class _Loaded:
    """Stands in for `_LoadedModel`: only `_generate` ever looks inside."""

    def __init__(self, source: str, target: str) -> None:
        self.pair = f"{source}->{target}"


def _fake_backend(loaded: list[str]) -> opus.OpusMtBackend:
    def loader(source: str, target: str) -> _Loaded:
        loaded.append(f"{source}->{target}")
        return _Loaded(source, target)

    return opus.OpusMtBackend(loader=loader)


# ── translating ──────────────────────────────────────────────────────────────


def test_each_direction_uses_its_own_model(monkeypatch):
    loaded: list[str] = []
    backend = _fake_backend(loaded)
    monkeypatch.setattr(opus, "_generate", lambda model, text: f"{model.pair}:{text}")

    incoming = backend.translate("thanks for the run", target_lang="HU", source_lang="EN")
    reply = backend.translate("köszi a segítséget", target_lang="EN", source_lang="HU")

    assert incoming.success and incoming.translated == "EN->HU:thanks for the run"
    assert reply.success and reply.translated == "HU->EN:köszi a segítséget"
    assert incoming.backend == opus.PROVIDER_ID == "opusmt"
    assert loaded == ["EN->HU", "HU->EN"]


def test_a_model_is_loaded_once_and_reused(monkeypatch):
    loaded: list[str] = []
    backend = _fake_backend(loaded)
    monkeypatch.setattr(opus, "_generate", lambda model, text: "x")

    for _ in range(3):
        backend.translate("hello there", target_lang="HU", source_lang="EN")

    assert loaded == ["EN->HU"]


def test_lowercase_language_codes_are_accepted(monkeypatch):
    backend = _fake_backend([])
    monkeypatch.setattr(opus, "_generate", lambda model, text: "szia")

    result = backend.translate("hi", target_lang="hu", source_lang="en")

    assert result.success and result.source_lang == "EN"


def test_the_output_is_trimmed(monkeypatch):
    backend = _fake_backend([])
    monkeypatch.setattr(opus, "_generate", lambda model, text: "  szia  ")

    assert backend.translate("hi", target_lang="HU", source_lang="EN").translated == "szia"


def test_a_pair_without_a_model_fails_without_loading_anything():
    loaded: list[str] = []
    result = _fake_backend(loaded).translate("hello", target_lang="DE", source_lang="EN")

    assert not result.success
    assert result.error == opus.UNSUPPORTED_PAIR
    assert result.translated == "hello"
    assert loaded == []


def test_no_source_language_is_an_unsupported_pair():
    result = _fake_backend([]).translate("hello", target_lang="HU")

    assert not result.success and result.error == opus.UNSUPPORTED_PAIR


def test_a_model_error_is_a_failure_not_a_crash(monkeypatch):
    def broken(_model, _text):
        raise RuntimeError("out of memory")

    monkeypatch.setattr(opus, "_generate", broken)
    result = _fake_backend([]).translate("hello", target_lang="HU", source_lang="EN")

    assert not result.success and result.error == opus.MODEL_ERROR
    assert result.translated == "hello"


def test_a_loader_error_is_a_failure_not_a_crash():
    def loader(_source, _target):
        raise FileNotFoundError("no converted model")

    result = opus.OpusMtBackend(loader=loader).translate("hello", target_lang="HU", source_lang="EN")

    assert not result.success and result.error == opus.MODEL_ERROR


def test_an_empty_output_is_a_failure(monkeypatch):
    monkeypatch.setattr(opus, "_generate", lambda model, text: "   ")
    result = _fake_backend([]).translate("hello", target_lang="HU", source_lang="EN")

    assert not result.success and result.error == opus.MODEL_ERROR


def test_warm_up_loads_the_model_and_swallows_errors():
    loaded: list[str] = []
    _fake_backend(loaded).warm_up("en", "hu")
    assert loaded == ["EN->HU"]

    def loader(_source, _target):
        raise RuntimeError("broken")

    opus.OpusMtBackend(loader=loader).warm_up()  # must not raise


# ── where the models live ────────────────────────────────────────────────────


def test_models_dir_honours_the_override(monkeypatch, tmp_path):
    monkeypatch.setenv(opus.MODELS_DIR_ENV, str(tmp_path))

    assert opus.models_dir() == tmp_path
    assert opus.model_path("EN", "HU") == tmp_path / "opus-mt-en-hu-ct2"


def test_models_dir_defaults_to_the_app_folder(monkeypatch, tmp_path):
    monkeypatch.delenv(opus.MODELS_DIR_ENV, raising=False)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))

    assert opus.models_dir() == app_dir() / "models"


def test_downloads_stay_in_the_models_folder(monkeypatch, tmp_path):
    monkeypatch.setenv(opus.MODELS_DIR_ENV, str(tmp_path))

    assert opus.hf_cache_dir().parent == tmp_path


def test_a_model_folder_counts_only_when_complete(tmp_path):
    folder = tmp_path / "opus-mt-en-hu-ct2"
    folder.mkdir()
    assert not opus.is_converted(folder)

    for name in ("model.bin", "source.spm"):
        (folder / name).write_bytes(b"x")
    assert not opus.is_converted(folder), "a folder without target.spm is not a model"

    (folder / "target.spm").write_bytes(b"x")
    assert opus.is_converted(folder)


def test_models_ready_needs_both_directions(monkeypatch, tmp_path):
    monkeypatch.setenv(opus.MODELS_DIR_ENV, str(tmp_path))
    for source, target in opus.MODELS:
        assert not opus.models_ready()
        folder = opus.model_path(source, target)
        folder.mkdir(parents=True)
        for name in ("model.bin", "source.spm", "target.spm"):
            (folder / name).write_bytes(b"x")

    assert opus.models_ready()


def test_without_converted_models_and_no_converter_the_loader_says_so(monkeypatch, tmp_path):
    monkeypatch.setenv(opus.MODELS_DIR_ENV, str(tmp_path))
    monkeypatch.setattr(opus, "can_convert", lambda: False)

    with pytest.raises(FileNotFoundError, match="prepare_opusmt"):
        opus.OpusMtBackend()._load_or_convert("EN", "HU")


# ── building it ──────────────────────────────────────────────────────────────


def test_build_refuses_when_the_runtime_is_missing(monkeypatch):
    monkeypatch.setattr(opus, "runtime_missing", lambda: "ctranslate2")

    with pytest.raises(RuntimeError, match="ctranslate2"):
        opus._build()


def test_build_refuses_when_there_are_no_models_and_none_can_be_made(monkeypatch, tmp_path):
    monkeypatch.setattr(opus, "runtime_missing", lambda: "")
    monkeypatch.setenv(opus.MODELS_DIR_ENV, str(tmp_path))
    monkeypatch.setattr(opus, "can_convert", lambda: False)

    with pytest.raises(RuntimeError, match="prepare_opusmt"):
        opus._build()


def test_the_disable_switch_reads_as_a_missing_runtime(monkeypatch):
    monkeypatch.setenv(opus.DISABLE_ENV, "1")

    assert opus.runtime_missing()


def test_with_the_disable_switch_the_service_has_no_backend(monkeypatch):
    monkeypatch.setenv(opus.DISABLE_ENV, "1")

    service = TranslatorService()

    assert service.has_backend is False
    assert "opusmt" not in service.active_ids


def test_a_failed_load_is_not_retried_on_every_line():
    calls = []

    def loader(source, target):
        calls.append((source, target))
        raise RuntimeError("conversion broke")

    backend = opus.OpusMtBackend(loader=loader)
    for _ in range(3):
        result = backend.translate("hello", target_lang="HU", source_lang="EN")
        assert not result.success
    assert calls == [("EN", "HU")]
