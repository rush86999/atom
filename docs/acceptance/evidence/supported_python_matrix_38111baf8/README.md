# Supported-Python quickstart matrix

Frozen source: `38111baf83c30d46fa9c8a3d0ed82cc3965f33a4`.

The documented Python 3.11–3.13 range previously had a real hosted 3.11 quickstart but only fake-interpreter guard controls for 3.12 and 3.13. This change preserves the original real setup/artifact/boot sequence in fresh 3.11, 3.12 and 3.13 runner jobs. The required `quickstart` name is an always-run aggregate over the complete matrix. Failure, cancellation, skip or missing result refuses; no continue-on-error and no supported version excluded.

Local controls: 42 pass on Python 3.11 and 3.14. They compare original steps exactly (normalizing only the selected Python version), execute the real aggregate shell over every result state, preserve backend lane coverage, and run the pre-existing interpreter guard twins. They do not install Python 3.12/3.13 or qualify the application on Python 3.14. Test command: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest --noconftest backend/tests/test_ci_backend_lane_contract.py backend/tests/test_quickstart_matrix_contract.py backend/tests/test_quickstart_python_guard.py -q`. Candidate bytes were hashed before commit and equal the frozen source.

Actual supported-version installation results remain pending hosted execution. Fresh runner checks, dependency installation, generated env artifacts and backend `/alive` are the intended qualification. They will not prove desktop/macOS/Windows/Linux distro breadth, UI first-use, live model/provider operation, PostgreSQL, soak or whole-app completion. No application dependency, authority, role, provider, secret or deployment policy is changed.

Research: [GitHub Actions matrix](https://docs.github.com/en/actions/how-tos/write-workflows/choose-what-workflows-do/run-job-variations), [job conditions](https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/control-jobs-with-conditions). The aggregate explicitly checks dependency success because skipped jobs do not certify execution.
