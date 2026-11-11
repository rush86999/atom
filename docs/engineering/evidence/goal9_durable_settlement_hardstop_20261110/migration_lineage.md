# Migration lineage / existing startup upgrade path

Date: 2026-11-10. Scope: the durable `TokenUsage` change from
`codex/goal9-durable-settlement-20261110` (draft PR #832). This file
records the actual migration landscape; it is evidence, not a live apply.

## Findings

- `backend/alembic/versions` contains **42 revisions** and **42 heads**.
- **No Alembic revision mentions `token_usage`.**
  - `token_usage` is created on a fresh DB by `Base.metadata.create_all`.
  - `create_all` does not alter an existing table, so a real pre-upgrade
    install would keep the old NOT NULL columns and fail non-agent/unknown
    settlement. That is the gap this follow-through closes.
- The app has an existing SQLite schema-drift hook:
  `core.sqlite_schema_repair.repair_known_drift()`, called at
  `backend/main_api_app.py:478` **before** `Base.metadata.create_all`.
  - This change adds `ensure_token_usage_upgrade()` to that same hook.
  - It is the app's already-used bounded startup repair pattern, not a
    parallel migration engine.
  - PostgreSQL is left to the owner/Alembic path; `migration.sql` holds
    the reversible DDL and was not applied.

## Why no new Alembic revision / merge head

With 42 divergent heads there is no single safe `down_revision`.
Adding a 43rd head would be misleading and would not be applied by the
existing SQLite install path. Official Alembic guidance is to `merge`
branch heads into a single lineage (and to use batch mode/table rebuild
for SQLite ALTER limitations); see:

- https://alembic.sqlalchemy.org/en/latest/branches.html
- https://alembic.sqlalchemy.org/en/latest/batch.html
- https://alembic.sqlalchemy.org/en/latest/tutorial.html

The owner may restore a canonical Alembic lineage and apply the equivalent
DDL through it; until then the supported SQLite startup repair is the
upgrade path exercised here.

## Exact heads (revision -> file)

- `091_decimal_precision` -> `091_decimal_precision_migration.py`
- `1a2b3c4d5e6f` -> `1a2b3c4d5e6f_add_chatsession_model.py`
- `20260204_messaging_perf` -> `20260204_messaging_performance_indexes.py`
- `20260205_add_job_id` -> `20260205_add_social_post_job_id.py`
- `20260205_menubar_integration` -> `20260205_menubar_integration.py`
- `20260205_mobile_biometric` -> `20260205_mobile_biometric_support.py`
- `20260205_offline_sync_enhancements` -> `20260205_offline_sync_enhancements.py`
- `20260206_add_debug_system` -> `20260206_add_debug_system.py`
- `20260207_complete_learning_analysis` -> `20260207_complete_learning_and_analysis_implementations.py`
- `20260207_multi_level_supervision` -> `20260207_multi_level_supervision_system.py`
- `20260207_supervision_learning` -> `20260207_supervision_learning_integration.py`
- `20260208_two_way_learning` -> `20260208_two_way_learning.py`
- `20260220_smoke_test` -> `20260220_create_smoke_test_user.py`
- `20260225_chrono_constraints` -> `20260225_chronological_integrity_constraints.py`
- `20260425_add_template_component_tables` -> `20260425_add_template_and_component_tables.py`
- `20260505_add_discovered_entities` -> `20260505_add_discovered_entities.py`
- `20260518_fix_acu_fk` -> `20260518_fix_acu_usage_fk_to_tenants.py`
- `20260902_installation_adaptation` -> `20260902_installation_adaptation.py`
- `20260902_wikiskill_adaptation` -> `20260902_wikiskill_adaptation.py`
- `20260908_playbook_dense_recall` -> `20260908_playbook_dense_recall.py`
- `20260909_goal_runs` -> `20260909_goal_runs.py`
- `20260912_agent_verified_record` -> `20260912_agent_marketplace_verified_record.py`
- `20261102_goal_run_material_revision` -> `20261102_goal_run_material_revision.py`
- `20261107_task_operation_result` -> `20261107_task_operation_result_json.py`
- `226103220000` -> `226103220000_add_provider_registry.py`
- `226403220000` -> `226403220000_add_capabilities_and_exclusion.py`
- `3a1b2c3d4e5f` -> `3a1b2c3d4e5f_add_governance_and_workflow_parity.py`
- `a2f0c1d4e5b6` -> `20261105_auth_2fa_durable_state.py`
- `a7b8c9d0e1f2` -> `a7b8c9d0e1f2_add_missing_agent_executions_columns.py`
- `add_audit_immutable_trigger` -> `20260225_audit_immutable_trigger.py`
- `add_notification_prefs` -> `add_notification_preferences.py`
- `b1c2d3e4f5a6` -> `add_canvas_type_to_canvas_audit.py`
- `b5370fc53623` -> `b5370fc53623_add_status_to_agent_episodes.py`
- `bcf9c8a7a85c` -> `bcf9c8a7a85c_add_notion_oauth_token_model.py`
- `c1d2e3f4g5h6` -> `add_unified_oauth_storage.py`
- `d1e2f3g4h5i6` -> `merge_oauth_heads.py`
- `d4e5f6g7h8i9` -> `d4e5f6g7h8i9_add_governance_tracking.py`
- `e186393951b0` -> `e186393951b0_add_nullable_columns_for_agent_registry_and_hitlaction.py`
- `e1f2g3h4i5j6` -> `e1f2g3h4i5j6_remove_workspace_multi_tenancy.py`
- `f1a2b3c4d5e6` -> `f1a2b3c4d5e6_add_browser_automation_models.py`
- `ffc5eb832d0d` -> `ffc5eb832d0d_add_smart_home_credentials.py`
- `g1h2i3j4k5l6` -> `g1h2i3j4k5l6_add_device_capability_models.py`

## Revisions mentioning token_usage

- None.
