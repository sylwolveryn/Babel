"""Compare translation engines on WoW chat, English <-> Hungarian.

Runs every engine over tools/translator_corpus.py and reports, per engine and
direction: how long the model took to load, the average time per line, and a
chrF score against the reference translations (0-100, higher is closer). The
side-by-side outputs go into a Markdown report, because a score is only a hint
and reading the lines is what decides.

    .venv/Scripts/python tools/compare_translators.py
    .venv/Scripts/python tools/compare_translators.py --engines opus-mt,argos
    .venv/Scripts/python tools/compare_translators.py --with-mymemory

Engines whose packages are missing are reported as skipped, with the reason.
Models download on first use: OPUS-MT ~300 MB per direction, OPUS-MT tc-big
~470 MB per direction, Argos ~100 MB per direction. CTranslate2 converts the
already-downloaded OPUS-MT models into tools/.models (int8), once.

Optional packages: see requirements-compare.txt.
"""

from __future__ import annotations

import argparse
import io
import os
import sys
import time
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE))

from translator_corpus import EN_HU, HU_EN  # noqa: E402

MODELS_DIR = HERE / ".models"

# Every download stays inside the project: Hugging Face and Argos would
# otherwise cache in the user's home folder. Set before either is imported.
os.environ.setdefault("HF_HOME", str(MODELS_DIR / "huggingface"))
for _xdg in ("XDG_DATA_HOME", "XDG_CACHE_HOME", "XDG_CONFIG_HOME"):
    os.environ.setdefault(_xdg, str(MODELS_DIR / "argos"))

OPUS_BASE = {("en", "hu"): "Helsinki-NLP/opus-mt-en-hu", ("hu", "en"): "Helsinki-NLP/opus-mt-hu-en"}
OPUS_BIG = {("en", "hu"): "Helsinki-NLP/opus-mt-tc-big-en-hu", ("hu", "en"): "Helsinki-NLP/opus-mt-tc-big-hu-en"}


# ── scoring ──────────────────────────────────────────────────────────────────


def _char_ngrams(text: str, n: int) -> Counter:
    text = " ".join(text.split())
    return Counter(text[i : i + n] for i in range(len(text) - n + 1))


def chrf(hypothesis: str, reference: str, max_n: int = 6, beta: float = 2.0) -> float:
    """Character n-gram F-score (Popović 2015), 0-100. Case-insensitive.

    The usual automatic measure for short, morphologically rich output like
    Hungarian, where word-level overlap punishes every different suffix.
    """
    hyp, ref = hypothesis.lower(), reference.lower()
    precisions, recalls = [], []
    for n in range(1, max_n + 1):
        h, r = _char_ngrams(hyp, n), _char_ngrams(ref, n)
        if not h or not r:
            continue
        overlap = sum((h & r).values())
        precisions.append(overlap / sum(h.values()))
        recalls.append(overlap / sum(r.values()))
    if not precisions:
        return 0.0
    p = sum(precisions) / len(precisions)
    r = sum(recalls) / len(recalls)
    if p + r == 0:
        return 0.0
    return 100 * (1 + beta**2) * p * r / (beta**2 * p + r)


# ── engines ──────────────────────────────────────────────────────────────────

#: An engine factory takes (source, target) and returns a translate function.
Factory = Callable[[str, str], Callable[[str], str]]


def _transformers_factory(models: dict[tuple[str, str], str]) -> Factory:
    def factory(source: str, target: str) -> Callable[[str], str]:
        import torch
        from transformers import MarianMTModel, MarianTokenizer

        model_id = models[(source, target)]
        tokenizer = MarianTokenizer.from_pretrained(model_id)
        model = MarianMTModel.from_pretrained(model_id).eval()

        def translate(text: str) -> str:
            batch = tokenizer([text], return_tensors="pt", truncation=True)
            with torch.inference_mode():
                out = model.generate(**batch, num_beams=4)
            return tokenizer.decode(out[0], skip_special_tokens=True)

        return translate

    return factory


def _ctranslate2_factory(models: dict[tuple[str, str], str], tag: str) -> Factory:
    def factory(source: str, target: str) -> Callable[[str], str]:
        import ctranslate2
        from transformers import MarianTokenizer

        model_id = models[(source, target)]
        out_dir = MODELS_DIR / f"ct2-{tag}-{source}-{target}"
        if not (out_dir / "model.bin").exists():
            MODELS_DIR.mkdir(exist_ok=True)
            print(f"    converting {model_id} to CTranslate2 (int8) -> {out_dir}", flush=True)
            ctranslate2.converters.TransformersConverter(model_id).convert(
                str(out_dir), quantization="int8", force=True
            )
        tokenizer = MarianTokenizer.from_pretrained(model_id)
        translator = ctranslate2.Translator(str(out_dir), device="cpu", compute_type="int8")

        def translate(text: str) -> str:
            tokens = tokenizer.convert_ids_to_tokens(tokenizer.encode(text))
            result = translator.translate_batch([tokens], beam_size=4)
            ids = tokenizer.convert_tokens_to_ids(result[0].hypotheses[0])
            return tokenizer.decode(ids, skip_special_tokens=True)

        return translate

    return factory


def _argos_factory(source: str, target: str) -> Callable[[str], str]:
    import argostranslate.package
    import argostranslate.translate

    installed = {(p.from_code, p.to_code) for p in argostranslate.package.get_installed_packages()}
    if (source, target) not in installed:
        print(f"    downloading Argos {source}->{target} package", flush=True)
        argostranslate.package.update_package_index()
        available = argostranslate.package.get_available_packages()
        package = next(p for p in available if p.from_code == source and p.to_code == target)
        argostranslate.package.install_from_path(package.download())

    def translate(text: str) -> str:
        return argostranslate.translate.translate(text, source, target)

    translate(".")  # load the model now, so load time is not billed to line one
    return translate


MYMEMORY_ENDPOINT = "https://api.mymemory.translated.net/get"


def _mymemory_factory(source: str, target: str) -> Callable[[str], str]:
    """MyMemory's free HTTP API, for comparison only — the app does not use it."""
    import requests

    session = requests.Session()

    def translate(text: str) -> str:
        try:
            response = session.get(
                MYMEMORY_ENDPOINT,
                params={"q": text, "langpair": f"{source}|{target}"},
                timeout=15,
            )
            payload = response.json()
        except (requests.RequestException, ValueError) as e:
            return f"[failed: {type(e).__name__}]"
        data = payload.get("responseData") if isinstance(payload, dict) else None
        translated = data.get("translatedText") if isinstance(data, dict) else None
        if response.status_code != 200 or payload.get("responseStatus") not in (200, "200") or not translated:
            return f"[failed: {payload.get('responseStatus', response.status_code)}]"
        return translated

    return translate


ENGINES: dict[str, Factory] = {
    "opus-mt": _transformers_factory(OPUS_BASE),
    "opus-mt-tc-big": _transformers_factory(OPUS_BIG),
    "ct2-opus-mt": _ctranslate2_factory(OPUS_BASE, "base"),
    "ct2-opus-mt-tc-big": _ctranslate2_factory(OPUS_BIG, "big"),
    "argos": _argos_factory,
    "mymemory": _mymemory_factory,
}

DEFAULT_ENGINES = ("opus-mt", "opus-mt-tc-big", "ct2-opus-mt", "ct2-opus-mt-tc-big", "argos")


# ── running ──────────────────────────────────────────────────────────────────


@dataclass
class DirectionResult:
    engine: str
    source: str
    target: str
    load_s: float = 0.0
    per_line_s: float = 0.0
    chrf: float = 0.0
    outputs: list[str] = field(default_factory=list)
    error: str = ""


def run_direction(name: str, factory: Factory, source: str, target: str, corpus) -> DirectionResult:
    result = DirectionResult(name, source, target)
    try:
        started = time.perf_counter()
        translate = factory(source, target)
        result.load_s = time.perf_counter() - started
    except ImportError as e:
        result.error = f"skipped: {e.name or e} not installed"
        return result
    except Exception as e:
        result.error = f"failed to load: {type(e).__name__}: {e}"
        return result

    scores, elapsed = [], 0.0
    for line, reference in corpus:
        started = time.perf_counter()
        try:
            output = translate(line)
        except Exception as e:
            output = f"[error: {type(e).__name__}: {e}]"
        elapsed += time.perf_counter() - started
        result.outputs.append(output)
        scores.append(chrf(output, reference))
    result.per_line_s = elapsed / len(corpus)
    result.chrf = sum(scores) / len(scores)
    return result


def render_report(results: list[DirectionResult]) -> str:
    lines = ["# Translator comparison: WoW chat, English ↔ Hungarian", ""]
    lines += [
        "chrF is a character n-gram overlap with the reference translation "
        "(0–100, higher is closer). It ranks engines against each other; read "
        "the lines below before trusting it.",
        "",
        "| Engine | Direction | chrF | ms / line | Load (s) | Note |",
        "| --- | --- | ---: | ---: | ---: | --- |",
    ]
    for r in results:
        direction = f"{r.source}→{r.target}"
        if r.error:
            lines.append(f"| {r.engine} | {direction} | – | – | – | {r.error} |")
        else:
            lines.append(
                f"| {r.engine} | {direction} | {r.chrf:.1f} | {r.per_line_s * 1000:.0f} | {r.load_s:.1f} | |"
            )
    for source, target, corpus in (("en", "hu", EN_HU), ("hu", "en", HU_EN)):
        ran = [r for r in results if (r.source, r.target) == (source, target) and not r.error]
        if not ran:
            continue
        lines += ["", f"## {source.upper()} → {target.upper()}", ""]
        for i, (line, reference) in enumerate(corpus):
            lines.append(f"**{line}**  ")
            lines.append(f"- *reference*: {reference}  ")
            for r in ran:
                lines.append(f"- {r.engine}: {r.outputs[i]}  ")
            lines.append("")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    if isinstance(sys.stdout, io.TextIOWrapper):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--engines", default=",".join(DEFAULT_ENGINES), help="comma-separated: " + ", ".join(ENGINES))
    parser.add_argument("--with-mymemory", action="store_true", help="also query MyMemory (network, uses its quota)")
    parser.add_argument("--report", default=str(HERE / "reports" / "translator-comparison.md"))
    args = parser.parse_args(argv)

    names = [n.strip() for n in args.engines.split(",") if n.strip()]
    if args.with_mymemory and "mymemory" not in names:
        names.append("mymemory")
    unknown = [n for n in names if n not in ENGINES]
    if unknown:
        parser.error(f"unknown engine(s): {', '.join(unknown)}")

    results: list[DirectionResult] = []
    for name in names:
        for source, target, corpus in (("en", "hu", EN_HU), ("hu", "en", HU_EN)):
            print(f"== {name} {source}->{target}", flush=True)
            result = run_direction(name, ENGINES[name], source, target, corpus)
            if result.error:
                print(f"   {result.error}")
            else:
                print(f"   chrF {result.chrf:.1f}  {result.per_line_s * 1000:.0f} ms/line  load {result.load_s:.1f}s")
            results.append(result)

    report = Path(args.report)
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(render_report(results), encoding="utf-8")
    print(f"\nReport: {report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
