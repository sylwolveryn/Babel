"""Measure what the local OPUS-MT translator costs: memory, CPU, time.

    .venv/Scripts/python tools/measure_opusmt.py

Runs in its own process with only what the app loads (ctranslate2 and
sentencepiece — never torch), loads both directions the way the app does at
start-up, then translates the comparison corpus and reports:

- resident memory (RSS) before loading, after each model, and at the end
- wall time and CPU time to load each model
- per-line latency (median, 95th percentile, max) and CPU time per line
- how many CPU cores a translation keeps busy while it runs

Needs psutil (requirements-compare.txt).
"""

from __future__ import annotations

import io
import statistics
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))


def main() -> int:
    if isinstance(sys.stdout, io.TextIOWrapper):
        sys.stdout.reconfigure(encoding="utf-8")
    import psutil
    from translator_corpus import EN_HU, HU_EN

    from app.translators import opusmt_provider as opus

    proc = psutil.Process()

    def rss_mb() -> float:
        return proc.memory_info().rss / 1e6

    def cpu_s() -> float:
        t = proc.cpu_times()
        return t.user + t.system

    print(f"Python + app imports: {rss_mb():.0f} MB RSS")
    backend = opus.OpusMtBackend(auto_convert=False)
    for source, target in (("EN", "HU"), ("HU", "EN")):
        before_rss, before_cpu, started = rss_mb(), cpu_s(), time.perf_counter()
        backend._model_for(source, target)
        print(
            f"Load {source}->{target}: {time.perf_counter() - started:.2f}s wall, "
            f"{cpu_s() - before_cpu:.2f}s CPU, +{rss_mb() - before_rss:.0f} MB (now {rss_mb():.0f} MB)"
        )
    print(f"torch loaded: {'torch' in sys.modules}")

    for source, target, corpus in (("EN", "HU", EN_HU), ("HU", "EN", HU_EN)):
        latencies, cpus = [], []
        for line, _reference in corpus:
            c0, t0 = cpu_s(), time.perf_counter()
            result = backend.translate(line, target_lang=target, source_lang=source)
            latencies.append(time.perf_counter() - t0)
            cpus.append(cpu_s() - c0)
            assert result.success, result.error
        lat = sorted(latencies)
        p95 = lat[max(0, int(len(lat) * 0.95) - 1)]
        busy = sum(cpus) / sum(latencies)
        print(
            f"{source}->{target} x{len(corpus)}: median {statistics.median(lat) * 1000:.0f} ms, "
            f"p95 {p95 * 1000:.0f} ms, max {lat[-1] * 1000:.0f} ms; "
            f"{statistics.mean(cpus) * 1000:.0f} ms CPU/line, ~{busy:.1f} cores busy while translating"
        )
    print(f"Peak at end: {rss_mb():.0f} MB RSS")
    sample = backend.translate("need a tank for ICC 10, 5k gs minimum", target_lang="HU", source_lang="EN")
    print(f"Sample: {sample.translated}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
