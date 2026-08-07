"""
Regression tests for the dead Debug System Aggregator startup hook.

main_api_app.py's lifespan imported core.debug_log_aggregator
(start_aggregator/stop_aggregator) — a module that never existed in this repo
(git history has no commit ever adding or deleting it). Every boot logged
"Failed to start Debug System Aggregator: No module named
'core.debug_log_aggregator'". The dead hook must be removed from both the
startup and shutdown paths.
"""

import inspect

import main_api_app as main_mod


class TestDebugAggregatorStartupHook:
    def test_lifespan_has_no_dead_debug_aggregator_import(self):
        """Startup/shutdown must not reference the missing module."""
        src = inspect.getsource(main_mod.lifespan)
        assert "debug_log_aggregator" not in src, (
            "Startup must not import the missing core.debug_log_aggregator "
            "module — every boot logs 'Failed to start Debug System Aggregator'"
        )
