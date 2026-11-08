# Reproducible governance cache measurement

Executed source: `95abe265d5efee562ce363407bb2f69034cb397c`.

The historical measurement named a command absent from accepted main d9a45f559. The retained baseline demonstrates that absence. This successor adds a source-bound reproducer; it does not rewrite historical measurements.

Run from the repository root:

```sh
python scripts/benchmark_governance.py --hits 100000 --misses 100000 --warmup 5000 --repetitions 5 --latency-samples 2000 --output cache-measurement.json
```

An existing output file is refused. Use `--repo` to select an explicit repository from another working directory. JSON includes actual source hashes, runtime and timer metadata, raw batch and latency samples, and correctness counts. No system tuning or threshold gating is applied.

Both Python 3.11 and 3.14 returned exit 0 for the measurements and 33 subprocess tests each. Test invocation: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest --noconftest backend/tests/test_governance_cache_benchmark_cli.py -q`. Plugin autoload is disabled to isolate this stdlib command; the normal application test suite is not claimed. Python 3.14 results do not change the application's supported installation versions.

These are warm in-memory cache hits and empty-cache misses on one host. They do not measure process startup, HTTP, database, current authority, budget, approval, Oracle or the full governance path. Timer overhead is retained separately, not subtracted. Full PERF-01 and broader performance qualification remain open.

Method references: [Python timeit](https://docs.python.org/3.11/library/timeit.html), [pyperf system noise guidance](https://pyperf.readthedocs.io/en/latest/system.html). Native CLI authored the two files from public source only; root independently inspected and executed them. No model inference or live business effect was performed by the benchmark.
