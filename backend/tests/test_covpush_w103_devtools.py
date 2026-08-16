# -*- coding: utf-8 -*-
"""Coverage wave 103 — dev-tool modules (all currently 0%).

Targets:
1.  integrations/whatsapp_database_setup.py     — DB schema setup script (mocked psycopg2)
2.  core/llm/registry/test_cache.py             — module with importable async test functions
3.  integrations/whatsapp_production_test.py    — manual smoke-tester (mocked requests)

No network, no real database — psycopg2 / requests / cache are mocked everywhere.
Plain pytest + unittest.mock.
"""
import asyncio
import os
import sys
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


# =========================================================================== #
# integrations/whatsapp_database_setup.py
# =========================================================================== #
def _psycopg2_mock(connect_side_effect=None):
    """Build a mocked psycopg2 module member suitable for patching."""
    psycopg2 = MagicMock()
    connection = MagicMock()
    cursor = MagicMock()
    connection.cursor.return_value.__enter__.return_value = cursor
    connection.cursor.return_value.__exit__.return_value = False
    psycopg2.connect = MagicMock(
        side_effect=connect_side_effect, return_value=connection
    ) if connect_side_effect is None else MagicMock(side_effect=connect_side_effect)
    psycopg2.connect.return_value = connection
    psycopg2.extras.DictCursor = MagicMock()
    return psycopg2, connection, cursor


class TestWhatsAppDatabaseSetup:
    def _manager(self):
        import integrations.whatsapp_database_setup as mod
        return mod.WhatsAppDatabaseManager()

    def test_config_defaults(self):
        m = self._manager()
        assert m.config['host'] == 'localhost'
        assert m.config['port'] == '5432'
        assert m.connection is None

    def test_test_connection_success(self):
        _, connection, cursor = _psycopg2_mock()
        with patch('integrations.whatsapp_database_setup.psycopg2') as pg:
            pg.connect.return_value = connection
            pg.extras.DictCursor = MagicMock()
            m = self._manager()
            result = m.test_connection()
        assert result['success'] is True
        assert result['config']['host'] == 'localhost'
        connection.close.assert_called()

    def test_test_connection_failure(self):
        with patch('integrations.whatsapp_database_setup.psycopg2') as pg:
            pg.connect.side_effect = RuntimeError('no db')
            m = self._manager()
            result = m.test_connection()
        assert result['success'] is False
        assert 'no db' in result['error']

    def test_create_database_created(self):
        _, connection, cursor = _psycopg2_mock()
        cursor.fetchone.return_value = None  # does not exist
        with patch('integrations.whatsapp_database_setup.psycopg2') as pg:
            pg.connect.return_value = connection
            pg.extras.DictCursor = MagicMock()
            m = self._manager()
            m.config['database'] = 'atom_new'
            result = m.create_database()
        assert result['success'] is True
        assert result['created'] is True
        assert 'atom_new' in result['message']
        created_sql = [c[0][0] for c in cursor.execute.call_args_list]
        assert any('CREATE DATABASE' in s for s in created_sql)

    def test_create_database_already_exists(self):
        _, connection, cursor = _psycopg2_mock()
        cursor.fetchone.return_value = (1,)  # exists
        with patch('integrations.whatsapp_database_setup.psycopg2') as pg:
            pg.connect.return_value = connection
            pg.extras.DictCursor = MagicMock()
            m = self._manager()
            result = m.create_database()
        assert result['success'] is True
        assert result['created'] is False
        assert 'already exists' in result['message']

    def test_create_database_invalid_name(self):
        _, connection, cursor = _psycopg2_mock()
        cursor.fetchone.return_value = None
        with patch('integrations.whatsapp_database_setup.psycopg2') as pg:
            pg.connect.return_value = connection
            pg.extras.DictCursor = MagicMock()
            m = self._manager()
            m.config['database'] = 'bad-name; DROP TABLE x'
            result = m.create_database()
        assert result['success'] is False
        assert 'Invalid database name' in result['error']

    def test_create_database_connection_error(self):
        with patch('integrations.whatsapp_database_setup.psycopg2') as pg:
            pg.connect.side_effect = RuntimeError('refused')
            m = self._manager()
            result = m.create_database()
        assert result['success'] is False

    def test_initialize_tables_success(self):
        _, connection, cursor = _psycopg2_mock()
        with patch('integrations.whatsapp_database_setup.psycopg2') as pg:
            pg.connect.return_value = connection
            pg.extras.DictCursor = MagicMock()
            m = self._manager()
            result = m.initialize_tables()
        assert result['success'] is True
        assert len(result['tables']) == 4
        assert result['indexes_created'] == 8
        executed = [c[0][0] for c in cursor.execute.call_args_list]
        assert any('whatsapp_contacts' in s for s in executed)
        assert any('idx_whatsapp_contacts_phone_number' in s for s in executed)
        assert cursor.executemany.call_count == 4  # demo data
        connection.close.assert_called()

    def test_initialize_tables_failure_closes_connection(self):
        _, connection, cursor = _psycopg2_mock()
        cursor.execute.side_effect = RuntimeError('sql error')
        with patch('integrations.whatsapp_database_setup.psycopg2') as pg:
            pg.connect.return_value = connection
            pg.extras.DictCursor = MagicMock()
            m = self._manager()
            result = m.initialize_tables()
        assert result['success'] is False
        assert 'sql error' in result['error']
        connection.close.assert_called()

    def test_insert_demo_data_swallows_error(self):
        _, connection, cursor = _psycopg2_mock()
        cursor.executemany.side_effect = RuntimeError('insert failed')
        import integrations.whatsapp_database_setup as mod
        m = self._manager()
        # Should not raise — errors are logged only
        m._insert_demo_data(cursor)

    def test_get_status_success(self):
        _, connection, cursor = _psycopg2_mock()
        cursor.fetchall.side_effect = [
            [{'tablename': 'whatsapp_contacts'}],            # pg_stats
            [{'table_name': 'whatsapp_contacts', 'row_count': 3},
             {'table_name': 'whatsapp_messages', 'row_count': 2}],  # row counts
        ]
        with patch('integrations.whatsapp_database_setup.psycopg2') as pg:
            pg.connect.return_value = connection
            pg.extras.DictCursor = MagicMock()
            m = self._manager()
            result = m.get_status()
        assert result['success'] is True
        assert result['total_tables'] == 2
        assert result['table_statistics'][0]['tablename'] == 'whatsapp_contacts'
        assert result['row_counts'][1]['row_count'] == 2
        connection.close.assert_called()

    def test_get_status_failure(self):
        with patch('integrations.whatsapp_database_setup.psycopg2') as pg:
            pg.connect.side_effect = RuntimeError('boom')
            m = self._manager()
            result = m.get_status()
        assert result['success'] is False
        assert 'boom' in result['error']

    def _patch_manager_methods(self, monkeypatch, **methods):
        import integrations.whatsapp_database_setup as mod
        manager = MagicMock()
        manager.test_connection.return_value = methods.get(
            'test_connection', {'success': True})
        manager.create_database.return_value = methods.get(
            'create_database',
            {'success': True, 'created': True, 'database': 'atom_development'})
        manager.initialize_tables.return_value = methods.get(
            'initialize_tables',
            {'success': True,
             'tables': ['whatsapp_contacts', 'whatsapp_messages'],
             'indexes_created': 8})
        manager.get_status.return_value = methods.get(
            'get_status',
            {'success': True, 'database': 'db', 'total_tables': 4,
             'row_counts': [{'table_name': 'whatsapp_contacts', 'row_count': 3}]})
        monkeypatch.setattr(mod, 'WhatsAppDatabaseManager',
                            MagicMock(return_value=manager))
        return manager

    def test_setup_database_full_success(self, monkeypatch, capsys):
        import integrations.whatsapp_database_setup as mod
        self._patch_manager_methods(monkeypatch)
        result = mod.setup_database()
        assert result['setup_complete'] is True
        assert result['final_status'] == 'success'
        assert 'connection_test_passed' in result['steps_completed']
        assert 'database_created' in result['steps_completed']
        assert 'tables_initialized' in result['steps_completed']
        assert 'status_verified' in result['steps_completed']
        assert result['errors'] == []
        out = capsys.readouterr().out
        assert 'completed successfully' in out

    def test_setup_database_connection_failure(self, monkeypatch, capsys):
        import integrations.whatsapp_database_setup as mod
        self._patch_manager_methods(
            monkeypatch,
            test_connection={'success': False, 'error': 'refused'})
        result = mod.setup_database()
        assert result['setup_complete'] is False
        assert result['final_status'] == 'failed'
        assert any('Connection test failed' in e for e in result['errors'])
        assert result['steps_completed'] == []

    def test_setup_database_create_failure(self, monkeypatch, capsys):
        import integrations.whatsapp_database_setup as mod
        self._patch_manager_methods(
            monkeypatch,
            create_database={'success': False, 'error': 'cannot create'})
        result = mod.setup_database()
        assert result['setup_complete'] is False
        assert result['steps_completed'] == ['connection_test_passed']
        assert any('Database creation failed' in e for e in result['errors'])

    def test_setup_database_tables_failure(self, monkeypatch, capsys):
        import integrations.whatsapp_database_setup as mod
        self._patch_manager_methods(
            monkeypatch,
            initialize_tables={'success': False, 'error': 'DDL failed'})
        result = mod.setup_database()
        assert result['setup_complete'] is False
        assert any('Table initialization failed' in e for e in result['errors'])

    def test_setup_database_status_failure_still_ok(self, monkeypatch, capsys):
        import integrations.whatsapp_database_setup as mod
        self._patch_manager_methods(
            monkeypatch,
            get_status={'success': False, 'error': 'stats unavailable'})
        result = mod.setup_database()
        # Status failure does not abort — setup still completes
        assert result['setup_complete'] is True
        assert 'status_verified' not in result['steps_completed']
        assert 'database_status' not in result

    def test_setup_database_unexpected_exception(self, monkeypatch, capsys):
        import integrations.whatsapp_database_setup as mod
        manager = MagicMock()
        manager.test_connection.side_effect = RuntimeError('kaboom')
        monkeypatch.setattr(mod, 'WhatsAppDatabaseManager',
                            MagicMock(return_value=manager))
        result = mod.setup_database()
        assert result['setup_complete'] is False
        assert any('Setup process error' in e for e in result['errors'])

    def _run_main_block(self, monkeypatch, capsys, setup_succeeds):
        import io
        import runpy
        import sys

        # runpy executes a fresh module namespace: replace psycopg2 in
        # sys.modules so the fresh import gets our fake, and patch open.
        if setup_succeeds:
            _, connection, cursor = _psycopg2_mock()
            cursor.fetchone.return_value = (1,)
            cursor.fetchall.side_effect = [
                [{'tablename': 'whatsapp_contacts'}],           # pg_stats
                [{'table_name': 'whatsapp_contacts', 'row_count': 3}],
            ]
            fake_psycopg2 = MagicMock()
            fake_psycopg2.connect.return_value = connection
            fake_psycopg2.extras.DictCursor = MagicMock()
        else:
            fake_psycopg2 = MagicMock()
            fake_psycopg2.connect.side_effect = RuntimeError('refused')
        monkeypatch.setitem(sys.modules, 'psycopg2', fake_psycopg2)
        monkeypatch.setitem(sys.modules, 'psycopg2.extras',
                            fake_psycopg2.extras)

        opened = {}

        def fake_open(path, mode='r', *a, **k):
            handle = io.StringIO()
            handle.close = MagicMock()
            opened[path] = handle
            return handle

        monkeypatch.setattr('builtins.open', fake_open)
        runpy.run_module('integrations.whatsapp_database_setup',
                         run_name='__main__')
        return opened, capsys.readouterr().out

    def test_main_block_success_with_status(self, monkeypatch, capsys):
        opened, out = self._run_main_block(monkeypatch, capsys,
                                           setup_succeeds=True)
        assert 'WHATSAPP DATABASE SETUP RESULTS' in out
        assert 'Database Statistics' in out
        assert '/tmp/whatsapp_database_setup.json' in opened

    def test_main_block_failure_no_status(self, monkeypatch, capsys):
        opened, out = self._run_main_block(monkeypatch, capsys,
                                           setup_succeeds=False)
        assert 'FAILED' in out
        assert 'Errors Encountered' in out
        assert '/tmp/whatsapp_database_setup.json' in opened


# =========================================================================== #
# core/llm/registry/test_cache.py — module of importable test functions.
# We execute each function directly so its lines count toward coverage.
# =========================================================================== #
class TestRegistryTestCacheModule:
    def _functions(self):
        import core.llm.registry.test_cache as tc
        names = [
            'test_concurrent_swap_prevention',
            'test_concurrent_swap_blocks_second_attempt',
            'test_cache_consistency_during_swap',
            'test_lock_timeout_behavior',
            'test_swap_error_handling',
            'test_warm_cache_no_lock_required',
            'test_invalidate_tenant_clears_all_keys',
            'test_model_cache_operations',
        ]
        return [(name, getattr(tc, name)) for name in names]

    @pytest.fixture(autouse=True)
    def _fake_universal_cache(self):
        # RegistryCacheService.__init__ builds UniversalCacheService(); make
        # that construction trivially safe (no redis/config access).
        with patch('core.llm.registry.cache.UniversalCacheService'):
            yield

    def test_execute_all_test_functions(self):
        for name, fn in self._functions():
            result = fn()
            if asyncio.iscoroutine(result):
                asyncio.run(result)


# =========================================================================== #
# integrations/whatsapp_production_test.py — smoke tester with mocked requests
# =========================================================================== #
def _http_response(status_code=200, json_data=None, content_type='application/json',
                   text='plain'):
    response = MagicMock()
    response.status_code = status_code
    response.elapsed.total_seconds.return_value = 0.05
    response.headers = {'content-type': content_type}
    response.json.return_value = json_data if json_data is not None else {}
    response.text = text
    return response


class TestWhatsAppProductionTester:
    def _tester(self):
        from integrations.whatsapp_production_test import WhatsAppProductionTester
        return WhatsAppProductionTester()

    def test_api_endpoints_all_success(self):
        t = self._tester()
        resp = _http_response(200, {'status': 'ok'})
        with patch('integrations.whatsapp_production_test.requests') as req:
            req.get.return_value = resp
            req.post.return_value = resp
            summary = t.test_api_endpoints()
        assert summary['total_tests'] == 9
        assert summary['successful_tests'] == 9
        assert summary['success_rate'] == 100.0

    def test_api_endpoints_mixed_and_error_branches(self):
        t = self._tester()
        responses = iter([
            _http_response(200, {'status': 'ok'}),                       # ok
            _http_response(500, {'error': 'server exploded'}),           # error json branch
            _http_response(404, None, content_type='text/plain'),        # fail, text branch
            RuntimeError('connection refused'),                          # exception branch
        ])
        with patch('integrations.whatsapp_production_test.requests') as req:
            req.get.side_effect = lambda *a, **k: _next(responses)
            req.post.side_effect = lambda *a, **k: _next(responses)
            summary = t.test_api_endpoints()
        assert summary['successful_tests'] == 1
        error_results = [r for r in summary['results']
                         if r.get('status_code') == 'error']
        assert len(error_results) >= 1
        assert error_results[0]['error'] == 'connection refused'

    def test_message_capabilities_success(self):
        t = self._tester()
        resp = _http_response(201, {'message_id': 'm1'})
        with patch('integrations.whatsapp_production_test.requests') as req:
            req.post.return_value = resp
            summary = t.test_message_capabilities()
        assert summary['successful_tests'] == 2
        assert summary['success_rate'] == 100.0

    def test_message_capabilities_exceptions(self):
        t = self._tester()
        with patch('integrations.whatsapp_production_test.requests') as req:
            req.post.side_effect = RuntimeError('timeout')
            summary = t.test_message_capabilities()
        assert summary['successful_tests'] == 0
        assert 'timeout' in summary['results']['text_message']['error']
        assert 'timeout' in summary['results']['template_message']['error']

    def test_configuration_status_success_demo(self):
        t = self._tester()
        health = _http_response(200, {
            'status': 'healthy', 'configuration_type': 'demo',
            'is_demo': True, 'uptime_percentage': 99.9})
        profile = _http_response(200, {
            'business_profile': {'display_name': 'ATOM', 'id': '1'}})
        with patch('integrations.whatsapp_production_test.requests') as req:
            req.get.side_effect = [health, profile]
            summary = t.test_configuration_status()
        assert summary['successful_tests'] == 2
        results = {r['test']: r for r in summary['results']}
        assert results['Service Health']['is_demo'] is True
        assert results['Configuration Access']['has_business_profile'] is True
        assert results['Configuration Access']['profile_fields'] == \
            ['display_name', 'id']

    def test_configuration_status_exceptions_and_empty_profile(self):
        t = self._tester()
        profile = _http_response(200, {'business_profile': {}})
        with patch('integrations.whatsapp_production_test.requests') as req:
            req.get.side_effect = [RuntimeError('down'), profile]
            summary = t.test_configuration_status()
        assert summary['successful_tests'] == 1
        results = {r['test']: r for r in summary['results']}
        assert 'error' in results['Service Health']
        assert results['Configuration Access']['has_business_profile'] is False

    def test_configuration_status_profile_exception(self):
        t = self._tester()
        health = _http_response(200, {'status': 'ok'})
        with patch('integrations.whatsapp_production_test.requests') as req:
            req.get.side_effect = [health, RuntimeError('profile down')]
            summary = t.test_configuration_status()
        results = {r['test']: r for r in summary['results']}
        assert 'error' in results['Configuration Access']
        assert results['Configuration Access']['success'] is False

    def test_search_and_analytics_success(self):
        t = self._tester()
        search = _http_response(200, {'conversations': []})
        export = _http_response(200, {'data': []})
        with patch('integrations.whatsapp_production_test.requests') as req:
            req.get.side_effect = [search, export]
            summary = t.test_search_and_analytics()
        assert summary['successful_tests'] == 2
        results = {r['test']: r for r in summary['results']}
        assert results['Conversation Search']['has_results'] is True
        assert results['Analytics Export']['is_json'] is True

    def test_search_and_analytics_failures(self):
        t = self._tester()
        search = _http_response(200, {'no_conversations': True})
        export = _http_response(500, None, content_type='text/html')
        with patch('integrations.whatsapp_production_test.requests') as req:
            req.get.side_effect = [search, export, RuntimeError('nope')]
            summary = t.test_search_and_analytics()
        # Search returned 200 (success) but without 'conversations' key;
        # export returned 500 (failure)
        assert summary['successful_tests'] == 1

    def test_search_and_analytics_exception_branch(self):
        t = self._tester()
        with patch('integrations.whatsapp_production_test.requests') as req:
            req.get.side_effect = RuntimeError('nope')
            summary = t.test_search_and_analytics()
        assert all('error' in r for r in summary['results'])

    def test_run_comprehensive_test(self, capsys):
        t = self._tester()
        ok = _http_response(200, {'status': 'ok', 'is_demo': False,
                                  'uptime_percentage': 100})
        with patch('integrations.whatsapp_production_test.requests') as req:
            req.get.return_value = ok
            req.post.return_value = ok
            report = t.run_comprehensive_test()
        assert report['overall_summary']['total_test_suites'] == 4
        assert report['overall_summary']['status'] == 'PASS'
        assert report['production_readiness']['score'] >= 90
        out = capsys.readouterr().out
        assert 'COMPREHENSIVE TEST RESULTS' in out

    def test_run_comprehensive_test_demo_penalty(self):
        t = self._tester()
        ok = _http_response(200, {'status': 'ok', 'is_demo': True,
                                  'uptime_percentage': 100,
                                  'business_profile': {'x': 'y'}})
        with patch('integrations.whatsapp_production_test.requests') as req:
            req.get.return_value = ok
            req.post.return_value = ok
            report = t.run_comprehensive_test()
        readiness = report['production_readiness']
        assert readiness['is_demo_mode'] is True
        assert readiness['score'] == 80
        assert readiness['status'] == 'MOSTLY_READY'
        assert any('demo mode' in r for r in report['recommendations'])

    def test_generate_recommendations_all_branches_and_cap(self):
        t = self._tester()
        test_results = [
            {'test_name': 'API Endpoints', 'success_rate': 50,
             'results': []},
            {'test_name': 'Message Capabilities', 'success_rate': 50,
             'results': []},
            {'test_name': 'Configuration Status', 'success_rate': 40,
             'results': [{'is_demo': True}]},
            {'test_name': 'Search and Analytics', 'success_rate': 10,
             'results': []},
        ]
        recs = t._generate_recommendations(test_results)
        assert len(recs) == 5  # capped at 5
        assert any('API endpoints' in r for r in recs)

    def test_generate_recommendations_perfect_run(self):
        t = self._tester()
        test_results = [
            {'test_name': 'API Endpoints', 'success_rate': 100, 'results': []},
            {'test_name': 'Message Capabilities', 'success_rate': 100,
             'results': []},
            {'test_name': 'Configuration Status', 'success_rate': 100,
             'results': [{'is_demo': False}]},
            {'test_name': 'Search and Analytics', 'success_rate': 100,
             'results': []},
        ]
        recs = t._generate_recommendations(test_results)
        assert len(recs) == 3  # only the always-on security recommendations
        assert 'webhook signature verification' in recs[0]

    def test_assess_production_readiness_bands(self):
        from integrations.whatsapp_production_test import WhatsAppProductionTester
        results = [
            {'test_name': 'X', 'success_rate': 100, 'results': []},
        ]
        cases = [
            (95, 'PRODUCTION_READY'),
            (85, 'MOSTLY_READY'),
            (65, 'NEEDS_WORK'),
            (40, 'NOT_READY'),
        ]
        for rate, status in cases:
            readiness = WhatsAppProductionTester()._assess_production_readiness(
                results, rate)
            assert readiness['status'] == status
            assert readiness['is_demo_mode'] is False

    def test_assess_production_readiness_clamping_and_critical(self):
        t = self._tester()
        results = [
            {'test_name': 'Configuration Status', 'success_rate': 0,
             'results': [{'is_demo': True}]},
            {'test_name': 'API Endpoints', 'success_rate': 10, 'results': []},
            {'test_name': 'Message Capabilities', 'success_rate': 20,
             'results': []},
        ]
        readiness = t._assess_production_readiness(results, 20)
        # 20 - 20 (demo) - 30 (3 critical) = -30 -> clamped to 0
        assert readiness['score'] == 0
        assert readiness['critical_failures'] == 3
        assert readiness['status'] == 'NOT_READY'
        # Non-clamped upper bound
        readiness_hi = t._assess_production_readiness([], 150)
        assert readiness_hi['score'] == 100

    def test_run_production_test_success_writes_report(self, tmp_path,
                                                       monkeypatch):
        import integrations.whatsapp_production_test as mod
        tester = MagicMock()
        ok_report = {'overall_summary': {'status': 'PASS'}}
        tester.run_comprehensive_test.return_value = ok_report
        monkeypatch.setattr(mod, 'WhatsAppProductionTester',
                            MagicMock(return_value=tester))
        opened = {}
        import io, json as jsonlib

        def fake_open(path, mode='r', *a, **k):
            handle = io.StringIO()
            handle.close = MagicMock()
            opened[path] = handle
            return handle

        monkeypatch.setattr('builtins.open', fake_open)
        with patch('integrations.whatsapp_production_test.requests'):
            result = mod.run_production_test()
        assert result is ok_report
        assert '/tmp/whatsapp_production_test_report.json' in opened

    def test_run_production_test_error_path(self, monkeypatch):
        import integrations.whatsapp_production_test as mod
        tester = MagicMock()
        tester.run_comprehensive_test.side_effect = RuntimeError('crashed')
        monkeypatch.setattr(mod, 'WhatsAppProductionTester',
                            MagicMock(return_value=tester))
        import io
        opened = {}

        def fake_open(path, mode='r', *a, **k):
            handle = io.StringIO()
            handle.close = MagicMock()
            opened[path] = handle
            return handle

        monkeypatch.setattr('builtins.open', fake_open)
        result = mod.run_production_test()
        assert result['error'] == 'crashed'
        assert 'timestamp' in result
        assert '/tmp/whatsapp_production_test_error.json' in opened


def _next(iterator):
    value = next(iterator)
    if isinstance(value, Exception):
        raise value
    return value
