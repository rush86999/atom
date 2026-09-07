"""Phase 0: HybridDataIngestionService state persists across restarts.

Sync configs and usage stats previously lived in in-memory dicts and were
lost on restart. They now write through to ingestion_settings (behind
ATOM_INGESTION_PERSIST_STATE, disabled globally for tests via conftest —
these tests opt back in against a temp SQLite DB).
"""
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import asyncio

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.models import Base, IngestionSettings


@pytest.fixture()
def temp_db(monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine, tables=[IngestionSettings.__table__])
    Session = sessionmaker(bind=engine)
    session = Session()
    # Route the service's SessionLocal to the temp DB.
    import core.hybrid_data_ingestion as hdi
    monkeypatch.setattr(hdi, "SessionLocal", Session)
    monkeypatch.setenv("ATOM_INGESTION_PERSIST_STATE", "true")
    yield session
    session.close()


def make_service(**kwargs):
    graphrag = MagicMock()
    graphrag.ingest_document = AsyncMock(return_value={"entities": 1, "relationships": 1})
    with patch("core.lancedb_handler.get_lancedb_handler", return_value=MagicMock()), \
         patch("core.graphrag_engine.GraphRAGEngine", return_value=graphrag), \
         patch("core.llm_service.get_llm_service", return_value=MagicMock()):
        from core.hybrid_data_ingestion import HybridDataIngestionService
        return HybridDataIngestionService(
            workspace_id=kwargs.pop("workspace_id", "default"),
            tenant_id=kwargs.pop("tenant_id", "default"),
            **kwargs,
        )


class TestWriteThrough:
    def test_enable_auto_sync_persists_row(self, temp_db):
        svc = make_service()
        svc.enable_auto_sync("slack")
        row = temp_db.query(IngestionSettings).filter_by(integration_id="slack").one()
        assert row.enabled is True
        assert row.entity_types == ["messages", "channels"]  # from DEFAULT_SYNC_CONFIGS
        assert row.sync_last_n_days == 7

    def test_usage_counters_persisted(self, temp_db):
        svc = make_service()
        svc.record_integration_usage("hubspot", "HubSpot", success=True)
        svc.record_integration_usage("hubspot", "HubSpot", success=False)
        row = temp_db.query(IngestionSettings).filter_by(integration_id="hubspot").one()
        assert row.usage_stats_json["total_calls"] == 2
        assert row.usage_stats_json["successful_calls"] == 1
        assert row.usage_stats_json["integration_name"] == "HubSpot"

    def test_disable_persists(self, temp_db):
        svc = make_service()
        svc.enable_auto_sync("slack")
        svc.disable_auto_sync("slack")
        row = temp_db.query(IngestionSettings).filter_by(integration_id="slack").one()
        assert row.enabled is False

    async def test_sync_completion_persists_last_synced(self, temp_db):
        svc = make_service()
        svc.enable_auto_sync("slack")
        stats = svc.usage_stats["slack"]
        async def fake_fetch(integration_id, config, discovery_mode=False, role=None):
            return [{"id": "1", "type": "message", "text": "hello world"}]
        with patch.object(svc, "_fetch_integration_data", new=fake_fetch):
            await svc.sync_integration_data("slack", force=True)
        row = temp_db.query(IngestionSettings).filter_by(integration_id="slack").one()
        assert row.last_sync is not None
        assert row.usage_stats_json["last_synced"] is not None


class TestRestartRoundTrip:
    def test_state_restored_on_new_instance(self, temp_db):
        svc = make_service()
        svc.record_integration_usage("hubspot", "HubSpot")
        svc.enable_auto_sync("slack")

        # Simulate a restart: fresh service instance, same persisted DB.
        svc2 = make_service()
        assert "hubspot" in svc2.usage_stats
        assert svc2.usage_stats["hubspot"].total_calls == 1
        assert svc2.usage_stats["hubspot"].integration_name == "HubSpot"
        assert "slack" in svc2.sync_configs
        assert svc2.usage_stats["slack"].auto_sync_enabled is True
        assert svc2.sync_configs["slack"].entity_types == ["messages", "channels"]

    def test_document_only_rows_ignored_on_load(self, temp_db):
        temp_db.add(IngestionSettings(
            workspace_id="default", integration_id="gdrive-docs",
            enabled=True, file_types=["pdf"],  # no entity_types / usage_stats_json
        ))
        temp_db.commit()
        svc = make_service()
        assert "gdrive-docs" not in svc.usage_stats
        assert "gdrive-docs" not in svc.sync_configs


class TestDegradesGracefully:
    def test_persistence_disabled_keeps_in_memory_only(self, temp_db, monkeypatch):
        monkeypatch.setenv("ATOM_INGESTION_PERSIST_STATE", "false")
        svc = make_service()
        svc.enable_auto_sync("slack")
        assert temp_db.query(IngestionSettings).count() == 0
        assert "slack" in svc.sync_configs

    def test_load_survives_db_error(self, monkeypatch):
        monkeypatch.setenv("ATOM_INGESTION_PERSIST_STATE", "true")
        import core.hybrid_data_ingestion as hdi

        class Boom:
            def __call__(self):
                raise RuntimeError("db down")

            def query(self, *a, **k):
                raise RuntimeError("db down")

        monkeypatch.setattr(hdi, "SessionLocal", Boom)
        svc = make_service()  # _load_state fails → in-memory behaviour
        assert svc.usage_stats == {}

    def test_persist_failure_non_fatal(self, temp_db, monkeypatch):
        import core.hybrid_data_ingestion as hdi

        real_session = hdi.SessionLocal

        def flaky():
            raise RuntimeError("write failed")

        monkeypatch.setattr(hdi, "SessionLocal", flaky)
        svc = make_service()
        svc._persist_integration("slack")  # must not raise
        monkeypatch.setattr(hdi, "SessionLocal", real_session)


class TestSyncDurationMeasurement:
    """Measured wall-clock sync durations ground the "first ingestion takes
    ~X" guidance — a real average on this workspace beats the static
    per-integration estimate."""

    def test_incremental_mean_over_samples(self):
        from core.hybrid_data_ingestion import IntegrationUsageStats

        stats = IntegrationUsageStats(
            integration_id="zoho", integration_name="Zoho"
        )
        assert stats.avg_sync_duration_seconds is None
        stats.record_sync_duration(10.0)
        assert stats.avg_sync_duration_seconds == 10.0
        stats.record_sync_duration(30.0)
        assert stats.avg_sync_duration_seconds == 20.0
        assert stats.sync_duration_samples == 2
        assert stats.last_sync_duration_seconds == 30.0

    async def test_sync_duration_measured_and_persisted(self, temp_db):
        svc = make_service()
        svc.enable_auto_sync("slack")

        async def fake_fetch(integration_id, config, discovery_mode=False, role=None):
            await asyncio.sleep(0.01)
            return [{"id": "1", "type": "message", "text": "hello world"}]

        with patch.object(svc, "_fetch_integration_data", new=fake_fetch):
            await svc.sync_integration_data("slack", force=True)

        stats = svc.usage_stats["slack"]
        assert stats.last_sync_duration_seconds is not None
        assert stats.last_sync_duration_seconds >= 0.01
        assert stats.sync_duration_samples == 1
        row = temp_db.query(IngestionSettings).filter_by(integration_id="slack").one()
        assert row.usage_stats_json["sync_duration_samples"] == 1
        assert (
            row.usage_stats_json["last_sync_duration_seconds"]
            == stats.last_sync_duration_seconds
        )

    def test_duration_survives_restart(self, temp_db):
        svc = make_service()
        svc.record_integration_usage("hubspot", "HubSpot")
        svc.usage_stats["hubspot"].record_sync_duration(240.0)
        svc._persist_integration("hubspot")

        svc2 = make_service()
        restored = svc2.usage_stats["hubspot"]
        assert restored.avg_sync_duration_seconds == 240.0
        assert restored.sync_duration_samples == 1
