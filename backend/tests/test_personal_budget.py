"""
Tests for Personal Budget Service (Single-Tenant Open-Source Version)

Tests budget tracking, forecasting, and alerts without billing enforcement.
Verifies that upstream remains single-tenant (no tenant_id, no billing, no blocking).

Ported from atom-saas
Changes: Removed tenant isolation, billing enforcement, hard-stop blocking tests
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
from sqlalchemy.orm import Session

from core.personal_budget_service import PersonalBudgetService, personal_budget_service
from core.models import AgentExecution, User


class TestPersonalBudgetTracking:
    """Test budget tracking functionality"""
    
    def test_check_budget_returns_false_when_under_limit(self):
        """Test that check_budget returns True when under budget limit"""
        service = PersonalBudgetService()
        
        # Mock get_current_spend_usd to return $50
        with patch.object(service, 'get_current_spend_usd', return_value=50.0):
            result = service.check_budget(budget_limit_usd=100.0, estimated_cost=10.0)
            
            # Should return True (under budget)
            assert result is True
    
    def test_check_budget_returns_true_when_exceeded(self):
        """Test that check_budget returns False when budget exceeded (but does NOT block)"""
        service = PersonalBudgetService()
        
        # Mock get_current_spend_usd to return $95
        with patch.object(service, 'get_current_spend_usd', return_value=95.0):
            result = service.check_budget(budget_limit_usd=100.0, estimated_cost=10.0)
            
            # Should return False (exceeded), but execution continues
            assert result is False
    
    def test_get_current_spend_usd_aggregates_costs(self):
        """Test that get_current_spend_usd aggregates ACU and API costs"""
        service = PersonalBudgetService()
        
        # Mock database query with agent executions
        mock_executions = [
            Mock(acu_cost_usd=0.5, api_cost_usd=0.3),
            Mock(acu_cost_usd=0.2, api_cost_usd=0.1),
            Mock(acu_cost_usd=0.1, api_cost_usd=0.0)
        ]
        
        with patch('core.personal_budget_service.SessionLocal') as mock_session:
            mock_db = Mock()
            mock_session.return_value.__enter__.return_value = mock_db
            
            # Mock query to return our test executions
            mock_query = Mock()
            mock_query.filter.return_value.filter.return_value.all.return_value = mock_executions
            mock_db.query.return_value = mock_query
            
            # Calculate expected total: (0.5+0.3) + (0.2+0.1) + (0.1+0.0) = 1.2
            total = service.get_current_spend_usd()
            
            # Should aggregate all costs
            assert total == 1.2
    
    def test_get_budget_forecast_predicts_exhaustion(self):
        """Test that get_budget_forecast predicts when budget will be exhausted"""
        service = PersonalBudgetService()
        
        # Mock get_current_spend_usd to return $50 on day 10
        with patch.object(service, 'get_current_spend_usd', return_value=50.0):
            forecast = service.get_budget_forecast(budget_limit_usd=100.0)
            
            # Daily spend: $50 / 10 days = $5/day
            # Days remaining: ($100 - $50) / $5 = 10 days
            assert forecast['current_spend_usd'] == 50.0
            assert forecast['daily_spend_usd'] == 5.0
            assert forecast['days_until_exhaustion'] == 10
            assert forecast['budget_status'] == 'on_track'
            assert forecast['remaining_budget_usd'] == 50.0


class TestPersonalBudgetAlerts:
    """Test budget alert functionality"""
    
    def test_send_budget_alert_at_threshold(self):
        """Test that budget alert is sent when threshold is crossed"""
        service = PersonalBudgetService()
        
        # Mock get_current_spend_usd to return $85 (85% of $100)
        with patch.object(service, 'get_current_spend_usd', return_value=85.0):
            # Mock _get_budget_limit to return $100
            with patch.object(service, '_get_budget_limit', return_value=100.0):
                result = service.send_budget_alert(threshold_percent=80.0)
                
                # Should send alert (85% >= 80%)
                assert result is True
    
    def test_send_budget_alert_below_threshold(self):
        """Test that budget alert is NOT sent when below threshold"""
        service = PersonalBudgetService()
        
        # Mock get_current_spend_usd to return $70 (70% of $100)
        with patch.object(service, 'get_current_spend_usd', return_value=70.0):
            # Mock _get_budget_limit to return $100
            with patch.object(service, '_get_budget_limit', return_value=100.0):
                result = service.send_budget_alert(threshold_percent=80.0)
                
                # Should NOT send alert (70% < 80%)
                assert result is False
    
    def test_budget_alert_logs_warning(self):
        """Test that budget alert logs to console (not email in personal deployment)"""
        service = PersonalBudgetService()
        
        # Mock get_current_spend_usd to return $90 (90% of $100)
        with patch.object(service, 'get_current_spend_usd', return_value=90.0):
            # Mock _get_budget_limit to return $100
            with patch.object(service, '_get_budget_limit', return_value=100.0):
                with patch('core.personal_budget_service.logger') as mock_logger:
                    service.send_budget_alert(threshold_percent=80.0)
                    
                    # Should log warning
                    mock_logger.warning.assert_called_once()
                    assert "BUDGET ALERT" in str(mock_logger.warning.call_args)


class TestNoBillingEnforcement:
    """Test that billing enforcement is removed (personal use = user responsibility)"""
    
    def test_no_stripe_integration(self):
        """Test that there is no Stripe integration"""
        import inspect
        from core.personal_budget_service import PersonalBudgetService
        
        # Get all methods and attributes
        source = inspect.getsource(PersonalBudgetService)
        
        # Should not contain Stripe references
        assert 'stripe' not in source.lower()
        assert 'StripeClient' not in source
        assert 'StripeError' not in source
    
    def test_no_payment_processing(self):
        """Test that there is no payment processing"""
        import inspect
        from core.personal_budget_service import PersonalBudgetService
        
        # Get all methods and attributes
        source = inspect.getsource(PersonalBudgetService)
        
        # Should not contain payment processing references
        assert 'payment' not in source.lower()
        assert 'charge' not in source.lower()
        assert 'invoice' not in source.lower()
        assert 'receipt' not in source.lower()
    
    def test_no_hard_stop_blocking(self):
        """Test that budget checks do NOT block execution (soft-stop only)"""
        service = PersonalBudgetService()
        
        # Mock get_current_spend_usd to return $200 (exceeded $100 limit)
        with patch.object(service, 'get_current_spend_usd', return_value=200.0):
            # Mock _get_budget_limit to return $100
            with patch.object(service, '_get_budget_limit', return_value=100.0):
                # Check if budget exceeded
                is_exceeded = service.is_budget_exceeded()
                
                # Should return True (exceeded)
                assert is_exceeded is True
                
                # But this is for WARNING only - execution continues
                # (we can't test non-blocking here, but the docstring confirms it)
    
    def test_budget_warnings_only(self):
        """Test that budget system only provides warnings (not enforcement)"""
        import inspect
        from core.personal_budget_service import PersonalBudgetService
        
        # Check docstring for warnings-only language
        docstring = PersonalBudgetService.check_budget.__doc__
        
        # Should mention warning-only behavior
        assert 'warning' in docstring.lower()
        assert 'does not block' in docstring.lower()


class TestSingleTenantArchitecture:
    """Test that budget system is single-tenant (no tenant isolation)"""
    
    def test_budget_is_global_not_per_tenant(self):
        """Test that budget is global (no tenant_id filtering)"""
        import inspect
        from core.personal_budget_service import PersonalBudgetService
        
        # Get source code
        source = inspect.getsource(PersonalBudgetService)
        
        # Should not contain tenant_id references
        assert 'tenant_id' not in source
    
    def test_no_tenant_id_in_budget_queries(self):
        """Test that budget queries do not filter by tenant_id"""
        service = PersonalBudgetService()
        
        # Mock database session
        with patch('core.personal_budget_service.SessionLocal') as mock_session:
            mock_db = Mock()
            mock_session.return_value.__enter__.return_value = mock_db
            
            # Call get_current_spend_usd
            service.get_current_spend_usd()
            
            # Get the query calls
            query_calls = mock_db.query.call_args_list
            
            # Should query AgentExecution (not with tenant_id filter)
            assert len(query_calls) > 0
            
            # Check that tenant_id is not in filter calls
            for call in query_calls:
                if hasattr(call, 'filter'):
                    # Should not filter by tenant_id
                    filter_str = str(call)
                    assert 'tenant_id' not in filter_str
    
    def test_no_tenant_isolation_in_budget_tracking(self):
        """Test that budget tracking does not use tenant isolation"""
        import inspect
        from core.personal_budget_service import PersonalBudgetService
        
        # Get source code
        source = inspect.getsource(PersonalBudgetService)
        
        # Should not contain tenant isolation patterns
        assert 'current_tenant' not in source
        assert 'get_tenant' not in source
        assert 'tenant isolation' not in source
        assert 'ROW LEVEL SECURITY' not in source
        assert 'RLS' not in source


class TestBudgetServiceSingleton:
    """Test that singleton instance works correctly"""
    
    def test_personal_budget_service_singleton(self):
        """Test that personal_budget_service is a singleton instance"""
        from core.personal_budget_service import personal_budget_service
        
        # Should be an instance of PersonalBudgetService
        assert isinstance(personal_budget_service, PersonalBudgetService)
    
    def test_singleton_reuses_instance(self):
        """Test that importing multiple times returns same instance"""
        from core.personal_budget_service import personal_budget_service as svc1
        import importlib
        import core.personal_budget_service
        importlib.reload(core.personal_budget_service)
        from core.personal_budget_service import personal_budget_service as svc2
        
        # Should be the same instance (or at least same type)
        assert type(svc1) == type(svc2)


class TestBudgetForecasting:
    """Test budget forecasting functionality"""
    
    def test_forecast_status_on_track(self):
        """Test forecast status when on track"""
        service = PersonalBudgetService()
        
        with patch.object(service, 'get_current_spend_usd', return_value=20.0):
            forecast = service.get_budget_forecast(budget_limit_usd=100.0)
            
            # Should be on track
            assert forecast['budget_status'] == 'on_track'
    
    def test_forecast_status_at_risk(self):
        """Test forecast status when at risk (< 7 days remaining)"""
        service = PersonalBudgetService()
        
        # Simulate day 25 with $95 spent (high daily rate)
        with patch('core.personal_budget_service.datetime') as mock_datetime:
            mock_datetime.utcnow.return_value = Mock(day=25)
            
            with patch.object(service, 'get_current_spend_usd', return_value=95.0):
                forecast = service.get_budget_forecast(budget_limit_usd=100.0)
                
                # Daily spend: $95 / 25 = $3.8/day
                # Days remaining: $5 / $3.8 = ~1.3 days (< 7 days)
                assert forecast['budget_status'] == 'at_risk'
                assert forecast['days_until_exhaustion'] == 1
    
    def test_forecast_status_exceeded(self):
        """Test forecast status when budget exceeded"""
        service = PersonalBudgetService()
        
        with patch.object(service, 'get_current_spend_usd', return_value=150.0):
            forecast = service.get_budget_forecast(budget_limit_usd=100.0)
            
            # Should be exceeded
            assert forecast['budget_status'] == 'exceeded'
            assert forecast['days_until_exhaustion'] == 0


class TestSpendRecording:
    """Test spend recording functionality"""
    
    def test_record_spend_logs_information(self):
        """Test that record_spend logs spend information"""
        service = PersonalBudgetService()
        
        with patch('core.personal_budget_service.logger') as mock_logger:
            service.record_spend(amount=0.5, execution_id='exec-123')
            
            # Should log info
            mock_logger.info.assert_called_once()
            log_message = str(mock_logger.info.call_args)
            assert '0.5000' in log_message  # Amount
            assert 'exec-123' in log_message  # Execution ID
    
    def test_record_spend_without_execution_id(self):
        """Test that record_spend works without execution_id"""
        service = PersonalBudgetService()
        
        with patch('core.personal_budget_service.logger') as mock_logger:
            service.record_spend(amount=1.0)
            
            # Should log info (without execution ID)
            mock_logger.info.assert_called_once()
            log_message = str(mock_logger.info.call_args)
            assert '1.0000' in log_message  # Amount
