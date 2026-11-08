"""Subprocess tests for the public governance-cache benchmark CLI.

These tests exercise the command's schema, source identity, argument bounds,
working-directory independence, output protection, and DB sentinel isolation.
They do not qualify performance and make no timing-threshold assertions.
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "benchmark_governance.py"
CORE_DIR = REPO_ROOT / "backend" / "core"

SMOKE_ARGS = [
    "--hits",
    "25",
    "--misses",
    "25",
    "--warmup",
    "3",
    "--repetitions",
    "2",
    "--latency-samples",
    "5",
    "--ttl-seconds",
    "60",
    "--max-size",
    "8",
]


def _run(args, cwd=None, env=None, timeout=120):
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=str(cwd) if cwd is not None else None,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=timeout,
        check=False,
    )


def _run_ok(args, **kwargs):
    completed = _run(args, **kwargs)
    assert completed.returncode == 0, completed.stderr
    return json.loads(completed.stdout)


def _sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


@pytest.fixture
def copied_repo(tmp_path):
    root = tmp_path / "copied-repo"
    core = root / "backend" / "core"
    core.mkdir(parents=True)
    for name in ("governance_cache.py", "asyncio_compat.py"):
        shutil.copyfile(CORE_DIR / name, core / name)
    return root


def test_help_documents_scope_and_command_example():
    completed = _run(["--help"])
    assert completed.returncode == 0
    text = (completed.stdout + completed.stderr).lower()
    assert "warmed synchronous cache hits" in text
    assert "empty-cache synchronous misses" in text
    assert "--repo" in text
    assert "benchmark_governance.py" in text


def test_smoke_scope_schema_counts_and_raw_measurements():
    data = _run_ok(["--repo", str(REPO_ROOT), *SMOKE_ARGS])

    assert data["schema_version"] == "1.0"
    scope = data["scope"]
    assert scope["measured"] == [
        "warmed_synchronous_cache_hits",
        "empty_cache_synchronous_misses",
    ]
    assert scope["warmup_in_timed_samples"] is False
    assert scope["timer_overhead_subtracted"] is False
    assert "cold_process_startup" in scope["excluded"]
    assert "full_permission_checks" in scope["excluded"]

    nonqualification = data["nonqualification"]
    assert nonqualification["db_touched"] is False
    assert nonqualification["current_authority_checked"] is False
    assert nonqualification["budget_enforced"] is False
    assert nonqualification["approvals_checked"] is False
    assert nonqualification["oracle_checked"] is False
    assert nonqualification["http_measured"] is False
    assert nonqualification["full_governance_measured"] is False
    assert nonqualification["universal_throughput_claimed"] is False
    assert nonqualification["performance_gate_applied"] is False
    assert nonqualification["historical_target_gating"] is False
    assert nonqualification["perf01_qualified"] is False
    for phrase in (
        "database latency",
        "current authority decisions",
        "budget enforcement",
        "approval workflow",
        "Oracle integrations",
        "HTTP/API latency",
        "full governance checks",
        "universal throughput",
    ):
        assert phrase in nonqualification["not_qualified_for"]
    assert isinstance(data["limitations"], list) and data["limitations"]

    parameters = data["parameters"]
    assert parameters["hits_per_batch"] == 25
    assert parameters["misses_per_batch"] == 25
    assert parameters["warmup_lookups"] == 3
    assert parameters["repetitions"] == 2
    assert parameters["latency_samples"] == 5
    assert parameters["ttl_seconds"] == 60
    assert parameters["max_size"] == 8

    warm = data["measurements"]["warm_hit"]
    miss = data["measurements"]["empty_miss"]
    for block, batch_ops in ((warm, 25), (miss, 25)):
        assert block["operations_per_batch"] == batch_ops
        assert len(block["batch_duration_ns"]) == 2
        assert len(block["throughput_ops_per_second"]) == 2
        assert all(
            isinstance(value, int) and value >= 0
            for value in block["batch_duration_ns"]
        )
        assert all(
            value is None or (isinstance(value, (int, float)) and value >= 0)
            for value in block["throughput_ops_per_second"]
        )
        assert len(block["stats_delta_hits_per_batch"]) == 2
        assert len(block["stats_delta_misses_per_batch"]) == 2
        latency = block["latency"]
        assert latency["count"] == 5
        assert len(latency["samples_ns"]) == 5
        assert all(
            isinstance(value, int) and value >= 0
            for value in latency["samples_ns"]
        )
        percentiles = latency["percentiles_ns"]
        assert (
            percentiles["p50"]
            <= percentiles["p90"]
            <= percentiles["p95"]
            <= percentiles["p99"]
        )

    assert warm["stats_delta_hits_per_batch"] == [25, 25]
    assert warm["stats_delta_misses_per_batch"] == [0, 0]
    assert miss["stats_delta_hits_per_batch"] == [0, 0]
    assert miss["stats_delta_misses_per_batch"] == [25, 25]

    warm_validation = data["validation"]["warm_hit"]
    expected_warm_hits = (
        parameters["warmup_lookups"]
        + parameters["hits_per_batch"] * parameters["repetitions"]
        + parameters["latency_samples"]
        + 1
    )
    assert warm_validation["expected_hits"] == expected_warm_hits
    assert warm_validation["observed_hits"] == expected_warm_hits
    assert warm_validation["observed_misses"] == 0
    assert warm_validation["cache_size_after"] == 1
    assert warm_validation["returned_fixture_identity"] is True
    assert warm_validation["ttl_expired_during_measurement"] is False

    miss_validation = data["validation"]["empty_miss"]
    expected_misses = (
        parameters["warmup_lookups"]
        + parameters["misses_per_batch"] * parameters["repetitions"]
        + parameters["latency_samples"]
        + 1
    )
    assert miss_validation["expected_misses"] == expected_misses
    assert miss_validation["observed_misses"] == expected_misses
    assert miss_validation["observed_hits"] == 0
    assert miss_validation["cache_size_before"] == 0
    assert miss_validation["cache_size_after"] == 0
    assert miss_validation["returned_none"] is True
    assert miss_validation["empty_cache"] is True

    timer = data["timer"]
    assert timer["clock"] == "time.perf_counter_ns"
    assert timer["overhead_subtracted_from_measurements"] is False
    assert timer["overhead"]["count"] == parameters["timer_overhead_samples"]
    assert (
        timer["resolution_seconds"] is None
        or isinstance(timer["resolution_seconds"], (int, float))
    )

    runtime = data["runtime_metadata"]
    assert runtime["python_implementation"] == platform.python_implementation()
    assert runtime["python_version"] == platform.python_version()
    assert isinstance(runtime["gc_enabled"], bool)
    for key in (
        "platform_system",
        "platform_release",
        "machine",
        "processor",
    ):
        assert isinstance(runtime[key], str) and runtime[key]

    tuning = data["system_tuning"]
    assert tuning["applied"] is False
    assert tuning["marker"] == "no-system-tuning"
    assert tuning["cpu_affinity_changed"] is False
    assert tuning["process_priority_changed"] is False
    assert tuning["gc_policy_changed"] is False

    source = data["source_identity"]
    cache_file = CORE_DIR / "governance_cache.py"
    compat_file = CORE_DIR / "asyncio_compat.py"
    script_file = SCRIPT
    assert source["repo_root"] == str(REPO_ROOT)
    assert source["cache_module_loaded_from"] == str(cache_file.resolve())
    assert source["governance_cache"]["path"] == str(cache_file.resolve())
    assert source["governance_cache"]["sha256"] == _sha256(cache_file)
    assert source["asyncio_compat"]["sha256"] == _sha256(compat_file)
    assert source["script"]["sha256"] == _sha256(script_file)
    assert source["identity_checks"]["cache_module_matches_selected_repo"] is True
    assert source["identity_checks"]["asyncio_compat_matches_selected_repo"] is True
    assert source["identity_checks"]["source_hashes_unchanged_during_run"] is True
    assert source["git"]["revision"] is None or isinstance(
        source["git"]["revision"], str
    )
    assert source["git"]["dirty"] is None or isinstance(
        source["git"]["dirty"], bool
    )


def test_default_repo_is_independent_of_working_directory(tmp_path):
    data = _run_ok(SMOKE_ARGS, cwd=tmp_path)
    source = data["source_identity"]
    assert source["repo_root"] == str(REPO_ROOT)
    assert source["governance_cache"]["path"] == str(
        (CORE_DIR / "governance_cache.py").resolve()
    )
    assert source["governance_cache"]["sha256"] == _sha256(
        CORE_DIR / "governance_cache.py"
    )


def test_explicit_repo_reports_actual_imported_file_hash(copied_repo):
    copied_cache = copied_repo / "backend" / "core" / "governance_cache.py"
    copied_compat = copied_repo / "backend" / "core" / "asyncio_compat.py"
    original_hash = _sha256(CORE_DIR / "governance_cache.py")

    copied_cache.write_bytes(
        copied_cache.read_bytes() + b"\n# local copy marker for identity test\n"
    )
    expected_hash = _sha256(copied_cache)
    assert expected_hash != original_hash

    data = _run_ok(
        ["--repo", str(copied_repo), *SMOKE_ARGS],
        cwd=copied_repo.parent,
    )
    source = data["source_identity"]
    assert source["repo_root"] == str(copied_repo.resolve())
    assert source["cache_module_loaded_from"] == str(copied_cache.resolve())
    assert source["governance_cache"]["path"] == str(copied_cache.resolve())
    assert source["governance_cache"]["sha256"] == expected_hash
    assert source["asyncio_compat"]["sha256"] == _sha256(copied_compat)
    assert source["git"]["available"] is False
    assert source["git"]["revision"] is None
    assert source["git"]["dirty"] is None

    # The in-memory measurement must still complete for the copied source.
    assert data["validation"]["warm_hit"]["observed_misses"] == 0
    assert data["validation"]["empty_miss"]["observed_hits"] == 0


def test_existing_output_is_refused_and_preserved(tmp_path):
    output = tmp_path / "retained-evidence.json"
    original = "retained evidence must not be overwritten\n"
    output.write_text(original, encoding="utf-8")

    completed = _run(
        ["--repo", str(REPO_ROOT), *SMOKE_ARGS, "--output", str(output)]
    )
    assert completed.returncode != 0
    assert completed.stdout == ""
    assert "refus" in completed.stderr.lower()
    assert output.read_text(encoding="utf-8") == original


def test_output_is_written_when_absent(tmp_path):
    output = tmp_path / "new-evidence.json"
    completed = _run(
        ["--repo", str(REPO_ROOT), *SMOKE_ARGS, "--output", str(output)]
    )
    assert completed.returncode == 0, completed.stderr
    assert output.is_file()
    assert json.loads(output.read_text(encoding="utf-8")) == json.loads(
        completed.stdout
    )


def test_missing_repo_source_fails_cleanly(tmp_path):
    empty_root = tmp_path / "not-a-repo"
    empty_root.mkdir()
    completed = _run(["--repo", str(empty_root), *SMOKE_ARGS])
    assert completed.returncode != 0
    assert completed.stdout == ""
    assert "required source" in completed.stderr.lower()


@pytest.mark.parametrize(
    "invalid",
    [
        ["--hits", "0"],
        ["--hits", "-1"],
        ["--hits", "not-an-int"],
        ["--hits", "2000001"],
        ["--misses", "0"],
        ["--misses", "-1"],
        ["--misses", "1.5"],
        ["--misses", "2000001"],
        ["--warmup", "0"],
        ["--warmup", "-1"],
        ["--warmup", "2000001"],
        ["--repetitions", "0"],
        ["--repetitions", "-1"],
        ["--repetitions", ""],
        ["--repetitions", "31"],
        ["--latency-samples", "0"],
        ["--latency-samples", "-1"],
        ["--latency-samples", "20001"],
        ["--ttl-seconds", "0"],
        ["--ttl-seconds", "-1"],
        ["--ttl-seconds", "86401"],
        ["--max-size", "0"],
        ["--max-size", "-1"],
        ["--max-size", "1000001"],
        ["--repo", ""],
    ],
)
def test_invalid_arguments_fail(invalid):
    completed = _run(["--repo", str(REPO_ROOT), *invalid])
    assert completed.returncode != 0
    assert completed.stdout == ""
    assert completed.stderr.strip()


def test_inherited_database_url_sentinel_is_not_read_or_written(tmp_path):
    sentinel_db = tmp_path / "database-must-not-be-touched.db"
    sentinel_value = "DO-NOT-COLLECT-OR-LEAK"
    env = os.environ.copy()
    env["DATABASE_URL"] = f"sqlite:///{sentinel_db}"
    env["BENCHMARK_ENV_SENTINEL"] = sentinel_value
    database_url_before = os.environ.get("DATABASE_URL")

    completed = _run(
        ["--repo", str(REPO_ROOT), *SMOKE_ARGS],
        cwd=tmp_path,
        env=env,
    )
    assert completed.returncode == 0, completed.stderr
    combined = completed.stdout + completed.stderr
    assert sentinel_value not in combined
    assert "DATABASE_URL" not in combined
    assert str(sentinel_db) not in combined
    assert not sentinel_db.exists()
    assert os.environ.get("DATABASE_URL") == database_url_before
    assert json.loads(completed.stdout)["schema_version"] == "1.0"
