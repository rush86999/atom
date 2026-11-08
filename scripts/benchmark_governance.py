#!/usr/bin/env python3
"""Bounded governance-cache microbenchmark (PERF-02 method reproducer).

Scope
-----
This command measures only:

* warmed synchronous ``GovernanceCache.get(...)`` cache hits, and
* synchronous ``GovernanceCache.get(...)`` misses against an empty cache.

It does NOT measure cold process startup, full permission/governance checks,
database latency, current-authority decisions, budgets, approvals, Oracle,
HTTP/API latency, or universal throughput. It applies no performance gate and
does not rescore any historical claim.

The actual ``backend/core/governance_cache.py`` selected by ``--repo`` (or by
the repository containing this script) is imported directly by file path. The
module's loaded file identity and SHA-256 are checked and reported, as are the
hashes of ``core/asyncio_compat.py`` and this script. No application DB,
model, provider, or service startup is performed.

Command example
---------------
    python scripts/benchmark_governance.py --repo /path/to/repo \\
        --hits 100000 --misses 100000 --warmup 5000 --repetitions 5 \\
        --latency-samples 2000 --output governance_cache_benchmark.json

Use ``python scripts/benchmark_governance.py --help`` for bounds.
"""

from __future__ import annotations

import argparse
import gc
import hashlib
import importlib.util
import json
import math
import os
import platform
import statistics
import subprocess
import sys
import time
import types
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence


SCHEMA_VERSION = "1.0"

HITS_DEFAULT = 100_000
HITS_MIN = 1
HITS_MAX = 2_000_000

MISSES_DEFAULT = 100_000
MISSES_MIN = 1
MISSES_MAX = 2_000_000

WARMUP_DEFAULT = 5_000
WARMUP_MIN = 1
WARMUP_MAX = 2_000_000

REPETITIONS_DEFAULT = 5
REPETITIONS_MIN = 1
REPETITIONS_MAX = 30

LATENCY_SAMPLES_DEFAULT = 2_000
LATENCY_SAMPLES_MIN = 1
LATENCY_SAMPLES_MAX = 20_000

TTL_SECONDS_DEFAULT = 600
TTL_SECONDS_MIN = 1
TTL_SECONDS_MAX = 86_400

MAX_SIZE_DEFAULT = 1_024
MAX_SIZE_MIN = 1
MAX_SIZE_MAX = 1_000_000

TIMER_OVERHEAD_SAMPLES = 2_000

WARM_AGENT = "benchmark-agent"
WARM_ACTION = "benchmark_warm_action"
MISS_ACTION = "benchmark_uncached_action"

PERCENTILES = (50, 90, 95, 99)


class BenchmarkError(RuntimeError):
    """Raised when the benchmark cannot produce trustworthy evidence."""


def _make_fixture() -> Dict[str, Any]:
    """Return the seeded in-memory value used to validate warm hits."""
    return {
        "allowed": True,
        "action": "benchmark_fixture",
        "data": {"benchmark": "cache-only", "real_governance_decision": False},
    }


def _int_range(name: str, minimum: int, maximum: int):
    """Build an argparse converter that requires a bounded integer."""

    def convert(raw: str) -> int:
        try:
            value = int(raw, 10)
        except (TypeError, ValueError) as exc:
            raise argparse.ArgumentTypeError(
                f"{name} must be an integer (got {raw!r})"
            ) from exc
        if value < minimum or value > maximum:
            raise argparse.ArgumentTypeError(
                f"{name} must be between {minimum} and {maximum} (got {value})"
            )
        return value

    return convert


def _build_parser() -> argparse.ArgumentParser:
    epilog = (
        "Scope: warmed synchronous cache hits and empty-cache synchronous "
        "misses only. This is not cold process startup, database, "
        "current-authority, budget, approval, Oracle, HTTP, or full-governance "
        "latency qualification. No performance gate is applied.\n\n"
        "Example:\n"
        "  python scripts/benchmark_governance.py --repo /path/to/repo "
        "--hits 100000 --misses 100000 --warmup 5000 --repetitions 5 "
        "--latency-samples 2000 --output evidence.json"
    )
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=epilog,
    )
    parser.add_argument(
        "--repo",
        default=None,
        help=(
            "repository root containing backend/core/governance_cache.py; "
            "defaults to the repository containing this script"
        ),
    )
    parser.add_argument(
        "--hits",
        type=_int_range("--hits", HITS_MIN, HITS_MAX),
        default=HITS_DEFAULT,
        help="warm-hit lookups per timed batch (default: %(default)s)",
    )
    parser.add_argument(
        "--misses",
        type=_int_range("--misses", MISSES_MIN, MISSES_MAX),
        default=MISSES_DEFAULT,
        help="empty-cache miss lookups per timed batch (default: %(default)s)",
    )
    parser.add_argument(
        "--warmup",
        type=_int_range("--warmup", WARMUP_MIN, WARMUP_MAX),
        default=WARMUP_DEFAULT,
        help="untimed warmup lookups per scope (default: %(default)s)",
    )
    parser.add_argument(
        "--repetitions",
        type=_int_range("--repetitions", REPETITIONS_MIN, REPETITIONS_MAX),
        default=REPETITIONS_DEFAULT,
        help="timed batches per scope (default: %(default)s)",
    )
    parser.add_argument(
        "--latency-samples",
        type=_int_range(
            "--latency-samples", LATENCY_SAMPLES_MIN, LATENCY_SAMPLES_MAX
        ),
        default=LATENCY_SAMPLES_DEFAULT,
        help="bounded per-lookup latency samples per scope (default: %(default)s)",
    )
    parser.add_argument(
        "--ttl-seconds",
        type=_int_range("--ttl-seconds", TTL_SECONDS_MIN, TTL_SECONDS_MAX),
        default=TTL_SECONDS_DEFAULT,
        help="cache TTL passed to GovernanceCache (default: %(default)s)",
    )
    parser.add_argument(
        "--max-size",
        type=_int_range("--max-size", MAX_SIZE_MIN, MAX_SIZE_MAX),
        default=MAX_SIZE_DEFAULT,
        help="cache max_size passed to GovernanceCache (default: %(default)s)",
    )
    parser.add_argument(
        "--output",
        default=None,
        help=(
            "optional JSON evidence path; the command refuses to overwrite an "
            "existing file"
        ),
    )
    return parser


def _resolve_repo(repo_arg: Optional[str]) -> Path:
    if repo_arg is None:
        # scripts/benchmark_governance.py -> repository root, independent of cwd.
        root = Path(__file__).resolve().parents[1]
    else:
        if not repo_arg.strip():
            raise BenchmarkError("--repo must not be empty")
        root = Path(repo_arg).expanduser()
    try:
        root = root.resolve()
    except (OSError, RuntimeError) as exc:
        raise BenchmarkError(f"cannot resolve repository path: {exc}") from exc
    if not root.is_dir():
        raise BenchmarkError(f"repository path is not a directory: {root}")

    core_dir = root / "backend" / "core"
    required = (
        core_dir / "governance_cache.py",
        core_dir / "asyncio_compat.py",
    )
    for path in required:
        try:
            resolved = path.resolve()
        except (OSError, RuntimeError) as exc:
            raise BenchmarkError(f"cannot resolve required source {path}: {exc}") from exc
        try:
            resolved.relative_to(root)
        except ValueError as exc:
            raise BenchmarkError(
                f"required source escapes selected repository: {path}"
            ) from exc
        if not resolved.is_file():
            raise BenchmarkError(f"required source not found: {path}")
    return root


def _prepare_output(output_arg: Optional[str]) -> Optional[Path]:
    if output_arg is None:
        return None
    path = Path(output_arg).expanduser()
    if os.path.lexists(str(path)):
        raise BenchmarkError(
            f"refusing to overwrite existing --output file: {path}"
        )
    parent = path.parent if str(path.parent) else Path(".")
    if not parent.exists():
        raise BenchmarkError(f"--output directory does not exist: {parent}")
    if not parent.is_dir():
        raise BenchmarkError(f"--output parent is not a directory: {parent}")
    return path


def _write_exclusive(path: Path, text: str) -> None:
    """Create *path* with O_EXCL so an existing file is never replaced."""
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    try:
        fd = os.open(str(path), flags, 0o644)
    except FileExistsError as exc:
        raise BenchmarkError(
            f"refusing to overwrite existing --output file: {path}"
        ) from exc
    except OSError as exc:
        raise BenchmarkError(f"cannot create --output file {path}: {exc}") from exc

    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
    except Exception:
        try:
            os.unlink(str(path))
        except OSError:
            pass
        raise


def _load_module_from_path(module_name: str, path: Path):
    spec = importlib.util.spec_from_file_location(module_name, str(path))
    if spec is None or spec.loader is None:
        raise BenchmarkError(f"cannot create import spec for {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        # Execute the exact bytes we attest. SourceFileLoader may otherwise
        # accept timestamp/size-valid stale .pyc after a rapid source edit.
        source_bytes = path.read_bytes()
        code = compile(source_bytes, str(path), "exec", dont_inherit=True)
        exec(code, module.__dict__)
        module.__benchmark_loaded_source_sha256__ = hashlib.sha256(source_bytes).hexdigest()
    except Exception as exc:
        sys.modules.pop(module_name, None)
        raise BenchmarkError(
            f"failed to import {path}: {type(exc).__name__}: {exc}"
        ) from exc

    loaded = getattr(module, "__file__", None)
    if loaded is None or Path(loaded).resolve() != path.resolve():
        raise BenchmarkError(
            f"imported module {module_name} came from {loaded!r}, "
            f"not the selected source {path}"
        )
    return module


def _load_repo_modules(repo_root: Path):
    """Load the selected cache module and its only application dependency.

    ``core`` is installed as a synthetic package in ``sys.modules`` so that
    ``governance_cache.py`` can resolve ``core.asyncio_compat`` without
    executing an application package initializer, importing DB/models, or
    depending on the process working directory.
    """
    core_dir = repo_root / "backend" / "core"
    cache_path = (core_dir / "governance_cache.py").resolve()
    compat_path = (core_dir / "asyncio_compat.py").resolve()

    package = types.ModuleType("core")
    package.__path__ = [str(core_dir)]
    package.__package__ = "core"
    sys.modules["core"] = package

    compat_module = _load_module_from_path("core.asyncio_compat", compat_path)
    package.asyncio_compat = compat_module

    cache_module = _load_module_from_path("core.governance_cache", cache_path)
    package.governance_cache = cache_module

    if not isinstance(getattr(cache_module, "GovernanceCache", None), type):
        raise BenchmarkError(
            f"selected cache module does not expose GovernanceCache: {cache_path}"
        )
    return cache_module, cache_path, compat_path


def _file_identity(path: Path) -> Dict[str, Any]:
    try:
        data = path.read_bytes()
    except OSError as exc:
        raise BenchmarkError(f"cannot read source file {path}: {exc}") from exc
    return {
        "path": str(path.resolve()),
        "sha256": hashlib.sha256(data).hexdigest(),
        "size_bytes": len(data),
    }


def _git_output(repo_root: Path, args: Sequence[str]) -> Optional[str]:
    try:
        completed = subprocess.run(
            ["git", "-C", str(repo_root), *args],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            errors="replace",
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if completed.returncode != 0:
        return None
    return completed.stdout.strip()


def _git_metadata(repo_root: Path) -> Dict[str, Any]:
    if not (repo_root / ".git").exists():
        return {
            "available": False,
            "revision": None,
            "dirty": None,
            "reason": "no .git metadata in selected repository",
        }

    revision = _git_output(repo_root, ("rev-parse", "HEAD"))
    status = _git_output(repo_root, ("status", "--porcelain"))
    if revision is None:
        return {
            "available": False,
            "revision": None,
            "dirty": None,
            "reason": "git revision unavailable",
        }
    return {
        "available": True,
        "revision": revision,
        "dirty": None if status is None else bool(status),
        "reason": None if status is not None else "git status unavailable",
    }


def _percentile_nearest_rank(sorted_values: Sequence[int], percentile: int) -> int:
    if not sorted_values:
        raise ValueError("percentile requires at least one sample")
    rank = max(1, math.ceil(percentile / 100.0 * len(sorted_values)))
    return int(sorted_values[min(rank, len(sorted_values)) - 1])


def _summarize_latency(samples: Sequence[int]) -> Dict[str, Any]:
    if not samples:
        return {
            "count": 0,
            "samples_ns": [],
            "min_ns": None,
            "median_ns": None,
            "mean_ns": None,
            "percentiles_ns": {f"p{p}": None for p in PERCENTILES},
            "max_ns": None,
        }
    ordered = sorted(int(value) for value in samples)
    return {
        "count": len(ordered),
        "samples_ns": [int(value) for value in samples],
        "min_ns": ordered[0],
        "median_ns": statistics.median(ordered),
        "mean_ns": statistics.fmean(ordered),
        "percentiles_ns": {
            f"p{p}": _percentile_nearest_rank(ordered, p) for p in PERCENTILES
        },
        "max_ns": ordered[-1],
    }


def _summarize_values(values: Sequence[Optional[float]]) -> Dict[str, Any]:
    valid = [float(value) for value in values if value is not None]
    if not valid:
        return {
            "count": 0,
            "min": None,
            "median": None,
            "mean": None,
            "max": None,
        }
    return {
        "count": len(valid),
        "min": min(valid),
        "median": statistics.median(valid),
        "mean": statistics.fmean(valid),
        "max": max(valid),
    }


def _throughput(operations: int, duration_ns: int) -> Optional[float]:
    if duration_ns <= 0:
        return None
    return operations / (duration_ns / 1_000_000_000.0)


def _timer_overhead_samples(count: int) -> List[int]:
    samples: List[int] = []
    for _ in range(count):
        started = time.perf_counter_ns()
        stopped = time.perf_counter_ns()
        samples.append(stopped - started)
    return samples


def _timer_metadata() -> Dict[str, Any]:
    try:
        clock_info = time.get_clock_info("perf_counter")
        resolution_seconds: Optional[float] = float(clock_info.resolution)
    except (OSError, ValueError):
        resolution_seconds = None

    resolution_ns: Optional[float]
    if resolution_seconds is None:
        resolution_ns = None
    else:
        resolution_ns = resolution_seconds * 1_000_000_000.0

    return {
        "clock": "time.perf_counter_ns",
        "clock_info_name": "perf_counter",
        "resolution_seconds": resolution_seconds,
        "resolution_ns": resolution_ns,
        "overhead": _summarize_latency(_timer_overhead_samples(TIMER_OVERHEAD_SAMPLES)),
        "overhead_method": (
            "two consecutive time.perf_counter_ns() calls; loop overhead is "
            "included"
        ),
        "overhead_subtracted_from_measurements": False,
    }


def _runtime_metadata() -> Dict[str, Any]:
    return {
        "python_implementation": platform.python_implementation(),
        "python_version": platform.python_version(),
        "python_version_info": list(sys.version_info[:3]),
        "platform_system": platform.system() or "unknown",
        "platform_release": platform.release() or "unknown",
        "machine": platform.machine() or "unknown",
        "processor": platform.processor() or "unknown",
        "gc_enabled": gc.isenabled(),
    }


def _run_warm_hit_scope(cache_cls, params: argparse.Namespace):
    cache = cache_cls(
        max_size=params.max_size,
        ttl_seconds=params.ttl_seconds,
    )
    fixture = _make_fixture()
    if cache.set(WARM_AGENT, WARM_ACTION, fixture) is not True:
        raise BenchmarkError("GovernanceCache.set() did not cache the warm fixture")

    measurement_started = time.perf_counter_ns()

    for _ in range(params.warmup):
        if cache.get(WARM_AGENT, WARM_ACTION) is not fixture:
            raise BenchmarkError("warmup hit did not return the seeded fixture")

    baseline = cache.get_stats()
    if baseline["hits"] != params.warmup or baseline["misses"] != 0:
        raise BenchmarkError(
            "warmup cache statistics are inconsistent "
            f"(hits={baseline['hits']}, misses={baseline['misses']})"
        )

    durations: List[int] = []
    throughputs: List[Optional[float]] = []
    stats_delta_hits: List[int] = []
    stats_delta_misses: List[int] = []

    for _ in range(params.repetitions):
        before = cache.get_stats()
        started = time.perf_counter_ns()
        last = None
        for _ in range(params.hits):
            last = cache.get(WARM_AGENT, WARM_ACTION)
        elapsed = time.perf_counter_ns() - started
        after = cache.get_stats()

        if last is not fixture:
            raise BenchmarkError(
                "timed warm-hit batch did not return the seeded fixture"
            )

        hits_delta = after["hits"] - before["hits"]
        misses_delta = after["misses"] - before["misses"]
        if hits_delta != params.hits or misses_delta != 0:
            raise BenchmarkError(
                "warm-hit cache statistics mismatch "
                f"(hits delta={hits_delta}, misses delta={misses_delta})"
            )

        durations.append(elapsed)
        throughputs.append(_throughput(params.hits, elapsed))
        stats_delta_hits.append(hits_delta)
        stats_delta_misses.append(misses_delta)

    latency_samples: List[int] = []
    for _ in range(params.latency_samples):
        started = time.perf_counter_ns()
        returned = cache.get(WARM_AGENT, WARM_ACTION)
        elapsed = time.perf_counter_ns() - started
        if returned is not fixture:
            raise BenchmarkError(
                "warm-hit latency sample did not return the seeded fixture"
            )
        latency_samples.append(elapsed)

    if cache.get(WARM_AGENT, WARM_ACTION) is not fixture:
        raise BenchmarkError("post-measurement warm-hit canary failed")

    final = cache.get_stats()
    expected_hits = (
        params.warmup
        + params.hits * params.repetitions
        + params.latency_samples
        + 1
    )
    expected_misses = 0
    if final["hits"] != expected_hits or final["misses"] != expected_misses:
        raise BenchmarkError(
            "warm-hit final cache statistics mismatch "
            f"(observed hits={final['hits']}, misses={final['misses']}; "
            f"expected hits={expected_hits}, misses={expected_misses})"
        )
    if final["size"] != 1:
        raise BenchmarkError(
            f"warm-hit cache size changed unexpectedly: {final['size']}"
        )

    measurement_elapsed = time.perf_counter_ns() - measurement_started
    ttl_ns = params.ttl_seconds * 1_000_000_000
    if measurement_elapsed >= ttl_ns:
        raise BenchmarkError(
            "warm-hit measurement reached or exceeded the cache TTL; "
            "results would risk including an expiry path"
        )

    measurements = {
        "scope": "warmed synchronous cache hits",
        "operations_per_batch": params.hits,
        "batch_duration_ns": durations,
        "throughput_ops_per_second": throughputs,
        "batch_duration_summary_ns": _summarize_values(durations),
        "throughput_summary_ops_per_second": _summarize_values(throughputs),
        "stats_delta_hits_per_batch": stats_delta_hits,
        "stats_delta_misses_per_batch": stats_delta_misses,
        "latency": _summarize_latency(latency_samples),
    }
    validation = {
        "ok": True,
        "warmup_lookups": params.warmup,
        "timed_batch_lookups": params.hits * params.repetitions,
        "latency_sample_lookups": params.latency_samples,
        "post_canary_lookups": 1,
        "expected_hits": expected_hits,
        "expected_misses": expected_misses,
        "observed_hits": final["hits"],
        "observed_misses": final["misses"],
        "cache_size_after": final["size"],
        "returned_fixture_identity": True,
        "ttl_seconds": params.ttl_seconds,
        "ttl_expired_during_measurement": False,
        "measurement_elapsed_ns": measurement_elapsed,
    }
    return measurements, validation


def _run_empty_miss_scope(cache_cls, params: argparse.Namespace):
    cache = cache_cls(
        max_size=params.max_size,
        ttl_seconds=params.ttl_seconds,
    )
    initial = cache.get_stats()
    if initial["size"] != 0:
        raise BenchmarkError(
            f"empty-miss cache is not empty at start (size={initial['size']})"
        )

    for _ in range(params.warmup):
        if cache.get(WARM_AGENT, MISS_ACTION) is not None:
            raise BenchmarkError("warmup miss returned a cached value")

    baseline = cache.get_stats()
    if baseline["hits"] != 0 or baseline["misses"] != params.warmup:
        raise BenchmarkError(
            "miss warmup cache statistics are inconsistent "
            f"(hits={baseline['hits']}, misses={baseline['misses']})"
        )

    durations: List[int] = []
    throughputs: List[Optional[float]] = []
    stats_delta_hits: List[int] = []
    stats_delta_misses: List[int] = []

    for _ in range(params.repetitions):
        before = cache.get_stats()
        started = time.perf_counter_ns()
        last = None
        for _ in range(params.misses):
            last = cache.get(WARM_AGENT, MISS_ACTION)
        elapsed = time.perf_counter_ns() - started
        after = cache.get_stats()

        if last is not None:
            raise BenchmarkError("timed empty-cache batch returned a cached value")

        hits_delta = after["hits"] - before["hits"]
        misses_delta = after["misses"] - before["misses"]
        if hits_delta != 0 or misses_delta != params.misses:
            raise BenchmarkError(
                "empty-cache miss statistics mismatch "
                f"(hits delta={hits_delta}, misses delta={misses_delta})"
            )
        if after["size"] != 0:
            raise BenchmarkError(
                f"empty-cache batch populated the cache (size={after['size']})"
            )

        durations.append(elapsed)
        throughputs.append(_throughput(params.misses, elapsed))
        stats_delta_hits.append(hits_delta)
        stats_delta_misses.append(misses_delta)

    latency_samples: List[int] = []
    for _ in range(params.latency_samples):
        started = time.perf_counter_ns()
        returned = cache.get(WARM_AGENT, MISS_ACTION)
        elapsed = time.perf_counter_ns() - started
        if returned is not None:
            raise BenchmarkError("empty-cache latency sample returned a cached value")
        latency_samples.append(elapsed)

    if cache.get(WARM_AGENT, MISS_ACTION) is not None:
        raise BenchmarkError("post-measurement empty-cache canary returned a value")

    final = cache.get_stats()
    expected_misses = (
        params.warmup
        + params.misses * params.repetitions
        + params.latency_samples
        + 1
    )
    expected_hits = 0
    if final["misses"] != expected_misses or final["hits"] != expected_hits:
        raise BenchmarkError(
            "empty-cache final statistics mismatch "
            f"(observed hits={final['hits']}, misses={final['misses']}; "
            f"expected hits={expected_hits}, misses={expected_misses})"
        )
    if final["size"] != 0:
        raise BenchmarkError(
            f"empty-cache final size changed unexpectedly: {final['size']}"
        )

    measurements = {
        "scope": "empty-cache synchronous misses",
        "operations_per_batch": params.misses,
        "batch_duration_ns": durations,
        "throughput_ops_per_second": throughputs,
        "batch_duration_summary_ns": _summarize_values(durations),
        "throughput_summary_ops_per_second": _summarize_values(throughputs),
        "stats_delta_hits_per_batch": stats_delta_hits,
        "stats_delta_misses_per_batch": stats_delta_misses,
        "latency": _summarize_latency(latency_samples),
    }
    validation = {
        "ok": True,
        "warmup_lookups": params.warmup,
        "timed_batch_lookups": params.misses * params.repetitions,
        "latency_sample_lookups": params.latency_samples,
        "post_canary_lookups": 1,
        "expected_hits": expected_hits,
        "expected_misses": expected_misses,
        "observed_hits": final["hits"],
        "observed_misses": final["misses"],
        "cache_size_before": initial["size"],
        "cache_size_after": final["size"],
        "returned_none": True,
        "empty_cache": True,
    }
    return measurements, validation


def _run_benchmark(
    cache_module,
    repo_root: Path,
    cache_path: Path,
    compat_path: Path,
    script_path: Path,
    params: argparse.Namespace,
) -> Dict[str, Any]:
    cache_cls = getattr(cache_module, "GovernanceCache")

    actual_cache_path = Path(cache_module.__file__).resolve()
    compat_module = sys.modules.get("core.asyncio_compat")
    if compat_module is None or getattr(compat_module, "__file__", None) is None:
        raise BenchmarkError("core.asyncio_compat was not loaded from the selected repo")
    actual_compat_path = Path(compat_module.__file__).resolve()

    if actual_cache_path != cache_path.resolve():
        raise BenchmarkError(
            f"imported cache module path mismatch: {actual_cache_path} != {cache_path}"
        )
    if actual_compat_path != compat_path.resolve():
        raise BenchmarkError(
            "imported asyncio_compat path mismatch: "
            f"{actual_compat_path} != {compat_path}"
        )

    cache_identity_before = _file_identity(actual_cache_path)
    compat_identity_before = _file_identity(actual_compat_path)
    script_identity_before = _file_identity(script_path)
    for loaded_module, identity in (
        (cache_module, cache_identity_before),
        (compat_module, compat_identity_before),
    ):
        loaded_hash = getattr(loaded_module, "__benchmark_loaded_source_sha256__", None)
        if loaded_hash != identity["sha256"]:
            raise BenchmarkError("selected source changed while loading: " + identity["path"])

    timer_metadata = _timer_metadata()
    warm_hit_measurements, warm_hit_validation = _run_warm_hit_scope(
        cache_cls, params
    )
    empty_miss_measurements, empty_miss_validation = _run_empty_miss_scope(
        cache_cls, params
    )

    cache_identity_after = _file_identity(actual_cache_path)
    compat_identity_after = _file_identity(actual_compat_path)
    script_identity_after = _file_identity(script_path)
    if cache_identity_before["sha256"] != cache_identity_after["sha256"]:
        raise BenchmarkError("governance_cache.py changed during the benchmark")
    if compat_identity_before["sha256"] != compat_identity_after["sha256"]:
        raise BenchmarkError("asyncio_compat.py changed during the benchmark")
    if script_identity_before["sha256"] != script_identity_after["sha256"]:
        raise BenchmarkError("benchmark script changed during the benchmark")

    return {
        "schema_version": SCHEMA_VERSION,
        "benchmark": "governance_cache_microbenchmark",
        "scope": {
            "measured": [
                "warmed_synchronous_cache_hits",
                "empty_cache_synchronous_misses",
            ],
            "excluded": [
                "cold_process_startup",
                "full_permission_checks",
                "database_latency",
                "current_authority",
                "budget_enforcement",
                "approval_workflow",
                "oracle",
                "http_api",
                "full_governance",
            ],
            "timed_operation": (
                "synchronous GovernanceCache.get(agent_id, action_type)"
            ),
            "timed_operation_notes": (
                "Returned values and cache statistics are validated outside "
                "each timed read; per-lookup latency samples validate the "
                "returned value after the stop timestamp."
            ),
            "warmup_in_timed_samples": False,
            "timer_overhead_subtracted": False,
            "cache_instances": (
                "one fresh in-process GovernanceCache per measured scope"
            ),
            "seeded_values": (
                "in-memory benchmark fixtures, not real governance decisions"
            ),
        },
        "nonqualification": {
            "statement": (
                "This bounded cache microbenchmark does not qualify database, "
                "current-authority, budget, approval, Oracle, HTTP/API, "
                "cold-start, or full-governance latency."
            ),
            "not_qualified_for": [
                "database latency",
                "current authority decisions",
                "budget enforcement",
                "approval workflow",
                "Oracle integrations",
                "HTTP/API latency",
                "cold process startup",
                "full governance checks",
                "universal throughput",
            ],
            "db_touched": False,
            "current_authority_checked": False,
            "budget_enforced": False,
            "approvals_checked": False,
            "oracle_checked": False,
            "http_measured": False,
            "full_governance_measured": False,
            "universal_throughput_claimed": False,
            "performance_gate_applied": False,
            "historical_target_gating": False,
            "perf01_qualified": False,
            "scope_note": "bounded PERF-02 cache-method evidence only",
        },
        "limitations": [
            (
                "Single-process, in-memory cache lookups only; no DB, network, "
                "or full governance path is exercised."
            ),
            (
                "No CPU isolation, affinity, priority, frequency, or GC policy "
                "changes were applied."
            ),
            (
                "Only governance_cache.py and core.asyncio_compat.py are "
                "loaded directly; no backend/core/__init__.py or app startup "
                "is executed."
            ),
            (
                "No pyperf dependency; time.perf_counter_ns with manual "
                "repetitions is used."
            ),
            (
                "Timer resolution and two-call timer overhead are reported "
                "separately and are not subtracted."
            ),
            (
                "Other host processes may add noise; no soak or CPU-isolation "
                "claim is made."
            ),
            (
                "Seeded policy-shaped fixtures are not real governance "
                "decisions."
            ),
            (
                "TTL uses the cache's wall-clock implementation; a run that "
                "reaches the TTL fails instead of reporting."
            ),
            (
                "Results are machine/run specific and do not grant universal "
                "throughput or PERF-01 qualification."
            ),
        ],
        "parameters": {
            "repo": str(repo_root),
            "hits_per_batch": params.hits,
            "misses_per_batch": params.misses,
            "warmup_lookups": params.warmup,
            "repetitions": params.repetitions,
            "latency_samples": params.latency_samples,
            "ttl_seconds": params.ttl_seconds,
            "max_size": params.max_size,
            "timer_overhead_samples": TIMER_OVERHEAD_SAMPLES,
        },
        "runtime_metadata": _runtime_metadata(),
        "system_tuning": {
            "applied": False,
            "marker": "no-system-tuning",
            "cpu_affinity_changed": False,
            "process_priority_changed": False,
            "gc_policy_changed": False,
            "cpu_frequency_changed": False,
        },
        "source_identity": {
            "repo_root": str(repo_root),
            "cache_module_loaded_from": str(actual_cache_path),
            "asyncio_compat_loaded_from": str(actual_compat_path),
            "governance_cache": {**cache_identity_after,
                                 "loaded_sha256": cache_module.__benchmark_loaded_source_sha256__},
            "asyncio_compat": {**compat_identity_after,
                               "loaded_sha256": compat_module.__benchmark_loaded_source_sha256__},
            "script": script_identity_after,
            "identity_checks": {
                "cache_module_name": cache_module.__name__,
                "cache_module_matches_selected_repo": True,
                "asyncio_compat_matches_selected_repo": True,
                "source_hashes_unchanged_during_run": True,
            },
            "git": _git_metadata(repo_root),
        },
        "timer": timer_metadata,
        "measurements": {
            "warm_hit": warm_hit_measurements,
            "empty_miss": empty_miss_measurements,
        },
        "validation": {
            "warm_hit": warm_hit_validation,
            "empty_miss": empty_miss_validation,
        },
    }


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    try:
        # Do not create __pycache__ files in the selected read-only source tree.
        sys.dont_write_bytecode = True
        repo_root = _resolve_repo(args.repo)
        output_path = _prepare_output(args.output)
        cache_module, cache_path, compat_path = _load_repo_modules(repo_root)
        payload = _run_benchmark(
            cache_module=cache_module,
            repo_root=repo_root,
            cache_path=cache_path,
            compat_path=compat_path,
            script_path=Path(__file__).resolve(),
            params=args,
        )
        text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
        if output_path is not None:
            _write_exclusive(output_path, text)
    except BenchmarkError as exc:
        print(f"benchmark error: {exc}", file=sys.stderr)
        return 2

    sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
