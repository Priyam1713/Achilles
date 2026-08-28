from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "benchmark_runtimes", ROOT / "scripts/benchmark_runtimes.py"
)
assert SPEC and SPEC.loader
benchmark_runtimes = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(benchmark_runtimes)


DEFAULTS = {
    "n_prompt": 512,
    "n_gen": 128,
    "repetitions": 3,
    "batch_size": 2048,
    "ubatch_size": 512,
    "threads": 10,
    "cache_type_k": "q8_0",
    "cache_type_v": "q8_0",
    "flash_attention": True,
}


def test_runtime_tournament_translates_flash_attention_per_dialect() -> None:
    upstream = benchmark_runtimes.build_argv(
        Path("llama-bench"), "upstream", Path("model.gguf"), 37, DEFAULTS
    )
    ik = benchmark_runtimes.build_argv(
        Path("llama-bench"), "ik", Path("model.gguf"), 37, DEFAULTS
    )
    assert upstream[upstream.index("-fa") + 1] == "on"
    assert ik[ik.index("-fa") + 1] == "1"
    assert upstream[upstream.index("-ngl") + 1] == "37"
    assert ik[ik.index("-ngl") + 1] == "37"


def test_runtime_tournament_rejects_unknown_cli_dialect() -> None:
    try:
        benchmark_runtimes.build_argv(
            Path("llama-bench"), "mystery", Path("model.gguf"), 1, DEFAULTS
        )
    except ValueError as exc:
        assert "Unsupported runtime dialect" in str(exc)
    else:
        raise AssertionError("unknown runtime dialect was accepted")


def test_runtime_tournament_normalises_upstream_and_ik_json_rows() -> None:
    parsed = benchmark_runtimes.parse_measurements(
        [
            {
                "model_type": "qwen35 27B IQ4_XS",
                "model_size": 15,
                "model_n_params": 27,
                "n_gpu_layers": 37,
                "n_threads": 10,
                "type_k": "q8_0",
                "type_v": "q8_0",
                "flash_attn": 1,
                "n_prompt": 512,
                "n_gen": 0,
                "avg_ts": 456.107285,
                "stddev_ts": 19.270356,
                "samples_ts": [434.065, 469.765, 464.492],
            },
            {
                "n_prompt": 0,
                "n_gen": 128,
                "avg_ts": 6.392007,
                "stddev_ts": 0.11353,
                "samples_ts": [6.26161, 6.46888, 6.44553],
            },
        ]
    )
    assert parsed["identity"]["n_gpu_layers"] == 37
    assert parsed["measurements"]["pp512"]["tokens_per_second"] == 456.1073
    assert parsed["measurements"]["pp512"]["median_tokens_per_second"] == 464.492
    assert parsed["measurements"]["pp512"]["min_tokens_per_second"] == 434.065
    assert parsed["measurements"]["pp512"]["max_tokens_per_second"] == 469.765
    assert parsed["measurements"]["tg128"]["tokens_per_second"] == 6.392
