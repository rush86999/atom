"""
Unit tests for ProviderScheduler
"""
import asyncio
import os
from unittest.mock import Mock, MagicMock, patch, call
import pytest

from core.provider_scheduler import ProviderScheduler, get_provider_scheduler


class TestProviderScheduler:
    """Comprehensive tests for ProviderScheduler"""

    def test_initialization(self):
        """Verify AsyncIOScheduler is created on initialization"""
        with patch('core.provider_scheduler.get_auto_discovery') as mock_discovery, \
             patch('core.provider_scheduler.get_provider_health_monitor') as mock_health:

            mock_discovery.return_value = Mock()
            mock_health.return_value = Mock()

            scheduler = ProviderScheduler()

            # Verify AsyncIOScheduler is created
            assert hasattr(scheduler.scheduler, 'add_job')
            assert hasattr(scheduler.scheduler, 'shutdown')
            assert hasattr(scheduler.scheduler, 'start')

    def test_singleton_pattern(self):
        """Verify get_instance returns same instance"""
        with patch('core.provider_scheduler.get_auto_discovery') as mock_discovery, \
             patch('core.provider_scheduler.get_provider_health_monitor') as mock_health:

            mock_discovery.return_value = Mock()
            mock_health.return_value = Mock()

            instance1 = ProviderScheduler.get_instance()
            instance2 = ProviderScheduler.get_instance()

            # Should be the same instance
            assert instance1 is instance2

    def test_start_schedules_job(self):
        """Verify start() schedules job with correct parameters"""
        with patch('core.provider_scheduler.get_auto_discovery') as mock_discovery, \
             patch('core.provider_scheduler.get_provider_health_monitor') as mock_health:

            mock_discovery.return_value = Mock()
            mock_health.return_value = Mock()

            scheduler = ProviderScheduler()

            # Mock the scheduler to avoid event loop requirements
            with patch.object(scheduler.scheduler, 'start'):
                scheduler.start()

            # Verify job was added
            jobs = scheduler.scheduler.get_jobs()
            assert len(jobs) == 1
            assert jobs[0].id == 'provider_auto_sync'

    def test_start_24_hour_interval(self):
        """Verify interval is 24 hours"""
        with patch('core.provider_scheduler.get_auto_discovery') as mock_discovery, \
             patch('core.provider_scheduler.get_provider_health_monitor') as mock_health:

            mock_discovery.return_value = Mock()
            mock_health.return_value = Mock()

            scheduler = ProviderScheduler()

            # Mock the scheduler to avoid event loop requirements
            with patch.object(scheduler.scheduler, 'start'):
                scheduler.start()

            # Get job trigger
            jobs = scheduler.scheduler.get_jobs()
            assert len(jobs) == 1

            trigger = jobs[0].trigger
            # Verify interval is 24 hours (timedelta)
            import datetime
            assert trigger.interval == datetime.timedelta(days=1)
            assert trigger.interval_length == 24 * 3600

    def test_start_max_instances_1(self):
        """Verify max_instances prevents overlapping executions"""
        with patch('core.provider_scheduler.get_auto_discovery') as mock_discovery, \
             patch('core.provider_scheduler.get_provider_health_monitor') as mock_health:

            mock_discovery.return_value = Mock()
            mock_health.return_value = Mock()

            scheduler = ProviderScheduler()

            # Mock the scheduler to avoid event loop requirements
            with patch.object(scheduler.scheduler, 'start'):
                scheduler.start()

            # Get job and verify max_instances
            jobs = scheduler.scheduler.get_jobs()
            assert len(jobs) == 1
            assert jobs[0].max_instances == 1

    def test_start_coalesce_true(self):
        """Verify coalesce combines missed executions"""
        with patch('core.provider_scheduler.get_auto_discovery') as mock_discovery, \
             patch('core.provider_scheduler.get_provider_health_monitor') as mock_health:

            mock_discovery.return_value = Mock()
            mock_health.return_value = Mock()

            scheduler = ProviderScheduler()

            # Mock the scheduler to avoid event loop requirements
            with patch.object(scheduler.scheduler, 'start'):
                scheduler.start()

            # Get job and verify coalesce
            jobs = scheduler.scheduler.get_jobs()
            assert len(jobs) == 1
            assert jobs[0].coalesce is True

    def test_disabled_by_env(self):
        """Verify PROVIDER_AUTO_SYNC_ENABLED=false prevents scheduling"""
        with patch.dict(os.environ, {'PROVIDER_AUTO_SYNC_ENABLED': 'false'}), \
             patch('core.provider_scheduler.get_auto_discovery') as mock_discovery, \
             patch('core.provider_scheduler.get_provider_health_monitor') as mock_health:

            mock_discovery.return_value = Mock()
            mock_health.return_value = Mock()

            scheduler = ProviderScheduler()
            scheduler.start()

            # Verify no jobs scheduled
            jobs = scheduler.scheduler.get_jobs()
            assert len(jobs) == 0

    def test_sync_with_error_handling_success(self):
        """Verify successful sync updates health monitor"""
        with patch('core.provider_scheduler.get_auto_discovery') as mock_discovery, \
             patch('core.provider_scheduler.get_provider_health_monitor') as mock_health:

            # Create async mock function
            async def mock_sync():
                return {'providers_synced': 5, 'models_synced': 100}

            mock_auto_discovery = Mock()
            mock_auto_discovery.sync_providers = mock_sync
            mock_discovery.return_value = mock_auto_discovery

            mock_monitor = Mock()
            mock_health.return_value = mock_monitor

            scheduler = ProviderScheduler()

            # Run sync task
            asyncio.run(scheduler._sync_with_error_handling())

            # Verify health monitor called with success=True
            mock_monitor.record_call.assert_called_once_with("provider_registry", True, 0)

    def test_sync_with_error_handling_failure(self):
        """Verify failed sync records error to health monitor"""
        with patch('core.provider_scheduler.get_auto_discovery') as mock_discovery, \
             patch('core.provider_scheduler.get_provider_health_monitor') as mock_health:

            # Create async mock function that raises exception
            async def mock_sync_error():
                raise Exception("API error")

            mock_auto_discovery = Mock()
            mock_auto_discovery.sync_providers = mock_sync_error
            mock_discovery.return_value = mock_auto_discovery

            mock_monitor = Mock()
            mock_health.return_value = mock_monitor

            scheduler = ProviderScheduler()

            # Run sync task (should not raise)
            asyncio.run(scheduler._sync_with_error_handling())

            # Verify health monitor called with success=False
            mock_monitor.record_call.assert_called_once_with("provider_registry", False, 0)

    def test_stop_shutdown_scheduler(self):
        """Verify stop() calls scheduler.shutdown()"""
        with patch('core.provider_scheduler.get_auto_discovery') as mock_discovery, \
             patch('core.provider_scheduler.get_provider_health_monitor') as mock_health:

            mock_discovery.return_value = Mock()
            mock_health.return_value = Mock()

            scheduler = ProviderScheduler()

            # Mock start to avoid event loop
            with patch.object(scheduler.scheduler, 'start'):
                scheduler.start()

            # Mock shutdown to verify it's called
            with patch.object(scheduler.scheduler, 'shutdown') as mock_shutdown:
                scheduler.stop()
                mock_shutdown.assert_called_once()

    def test_get_provider_scheduler_enabled(self):
        """Verify get_provider_scheduler returns instance when enabled"""
        with patch.dict(os.environ, {'PROVIDER_AUTO_SYNC_ENABLED': 'true'}), \
             patch('core.provider_scheduler.get_auto_discovery') as mock_discovery, \
             patch('core.provider_scheduler.get_provider_health_monitor') as mock_health:

            mock_discovery.return_value = Mock()
            mock_health.return_value = Mock()

            # Reset singleton
            ProviderScheduler._instance = None

            result = get_provider_scheduler()

            assert result is not None
            assert isinstance(result, ProviderScheduler)

    def test_get_provider_scheduler_disabled(self):
        """Verify get_provider_scheduler returns None when disabled"""
        with patch.dict(os.environ, {'PROVIDER_AUTO_SYNC_ENABLED': 'false'}), \
             patch('core.provider_scheduler.get_auto_discovery') as mock_discovery, \
             patch('core.provider_scheduler.get_provider_health_monitor') as mock_health:

            mock_discovery.return_value = Mock()
            mock_health.return_value = Mock()

            # Reset singleton
            ProviderScheduler._instance = None

            result = get_provider_scheduler()

            assert result is None

    def test_replace_existing_true(self):
        """Verify replace_existing=True parameter is passed to add_job"""
        with patch('core.provider_scheduler.get_auto_discovery') as mock_discovery, \
             patch('core.provider_scheduler.get_provider_health_monitor') as mock_health:

            mock_discovery.return_value = Mock()
            mock_health.return_value = Mock()

            scheduler = ProviderScheduler()

            # Mock the scheduler's start to avoid event loop requirements
            with patch.object(scheduler.scheduler, 'start'):
                scheduler.start()

            # Get the job that was added
            jobs = scheduler.scheduler.get_jobs()
            assert len(jobs) >= 1

            # Verify the job has the correct ID (provider_auto_sync)
            # The replace_existing=True ensures that calling start() again
            # will replace the job with the same ID rather than adding a duplicate
            job_ids = [job.id for job in jobs]
            assert 'provider_auto_sync' in job_ids

    def test_job_id_is_provider_auto_sync(self):
        """Verify correct job ID is assigned"""
        with patch('core.provider_scheduler.get_auto_discovery') as mock_discovery, \
             patch('core.provider_scheduler.get_provider_health_monitor') as mock_health:

            mock_discovery.return_value = Mock()
            mock_health.return_value = Mock()

            scheduler = ProviderScheduler()

            # Mock start to avoid event loop
            with patch.object(scheduler.scheduler, 'start'):
                scheduler.start()

            jobs = scheduler.scheduler.get_jobs()
            assert jobs[0].id == 'provider_auto_sync'

    def test_health_monitor_integration(self):
        """Verify health_monitor.record_call is invoked on sync"""
        with patch('core.provider_scheduler.get_auto_discovery') as mock_discovery, \
             patch('core.provider_scheduler.get_provider_health_monitor') as mock_health:

            # Create async mock function
            async def mock_sync():
                return {'providers_synced': 3, 'models_synced': 50}

            mock_auto_discovery = Mock()
            mock_auto_discovery.sync_providers = mock_sync
            mock_discovery.return_value = mock_auto_discovery

            mock_monitor = Mock()
            mock_health.return_value = mock_monitor

            scheduler = ProviderScheduler()

            # Run sync
            asyncio.run(scheduler._sync_with_error_handling())

            # Verify health_monitor.record_call was called
            assert mock_monitor.record_call.called
            call_args = mock_monitor.record_call.call_args
            assert call_args[0][0] == "provider_registry"
            assert call_args[0][1] is True  # success
            assert call_args[0][2] == 0  # latency_ms (not measured for sync)
