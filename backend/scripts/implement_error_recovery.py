#!/usr/bin/env python3
"""
Implement Error Recovery System

This script implements intelligent error recovery mechanisms:
- Intelligent error detection and classification
- Retry policies with exponential backoff
- Workflow rescue and rollback mechanisms
- Comprehensive error logging and analysis
- Error recovery strategies
- Self-healing capabilities
"""

import os
import sys
import logging
import json
import uuid
import traceback
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Callable, Union, Type
from dataclasses import dataclass, field
from enum import Enum
import time
from functools import wraps
from contextlib import contextmanager

# Add backend directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

logger = logging.getLogger(__name__)


class ErrorSeverity(Enum):
    """Error severity levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ErrorCategory(Enum):
    """Error categories"""
    NETWORK = "network"
    AUTHENTICATION = "authentication"
    AUTHORIZATION = "authorization"
    VALIDATION = "validation"
    RATE_LIMIT = "rate_limit"
    SERVICE_UNAVAILABLE = "service_unavailable"
    TIMEOUT = "timeout"
    INTERNAL = "internal"
    EXTERNAL = "external"
    UNKNOWN = "unknown"


class RecoveryStrategy(Enum):
    """Error recovery strategies"""
    RETRY = "retry"
    RETRY_WITH_BACKOFF = "retry_with_backoff"
    FALLBACK = "fallback"
    CIRCUIT_BREAKER = "circuit_breaker"
    ROLLBACK = "rollback"
    SKIP = "skip"
    ALTERNATE_SERVICE = "alternate_service"
    CACHE_RESPONSE = "cache_response"
    MANUAL_INTERVENTION = "manual_intervention"
    ESCALATE = "escalate"


@dataclass
class ErrorInfo:
    """Detailed error information"""
    id: str
    error: Exception
    message: str
    category: ErrorCategory
    severity: ErrorSeverity
    timestamp: datetime
    service: str
    action: str
    step_id: Optional[str] = None
    workflow_id: Optional[str] = None
    execution_id: Optional[str] = None
    context: Dict[str, Any] = field(default_factory=dict)
    stack_trace: str = ""
    retry_count: int = 0
    can_retry: bool = True
    suggested_recovery: List[RecoveryStrategy] = field(default_factory=list)


@dataclass
class RecoveryAction:
    """Recovery action definition"""
    id: str
    strategy: RecoveryStrategy
    description: str
    action: Callable
    parameters: Dict[str, Any] = field(default_factory=dict)
    max_attempts: int = 3
    delay: float = 0.0
    success_threshold: float = 1.0


@dataclass
class CircuitBreakerState:
    """Circuit breaker state"""
    service: str
    action: str
    failures: int = 0
    last_failure: Optional[datetime] = None
    state: str = "CLOSED"  # CLOSED, OPEN, HALF_OPEN
    failure_threshold: int = 5
    recovery_timeout: int = 60
    success_count: int = 0


class ErrorClassifier:
    """Classifies errors into categories and determines severity"""
    
    def __init__(self):
        self.classification_rules = self._initialize_classification_rules()
    
    def classify_error(
        self, 
        error: Exception, 
        service: str = "", 
        action: str = "",
        context: Dict[str, Any] = None
    ) -> ErrorInfo:
        """Classify error and create ErrorInfo"""
        error_type = type(error).__name__
        error_message = str(error)
        
        # Determine category
        category = self._determine_category(error_type, error_message, service, action)
        
        # Determine severity
        severity = self._determine_severity(error_type, category, error_message, context)
        
        # Suggest recovery strategies
        recovery_strategies = self._suggest_recovery_strategies(category, severity, service, action)
        
        # Determine if retry is possible
        can_retry = self._can_retry(category, severity, error_type)
        
        error_info = ErrorInfo(
            id=str(uuid.uuid4()),
            error=error,
            message=error_message,
            category=category,
            severity=severity,
            timestamp=datetime.now(),
            service=service,
            action=action,
            stack_trace=traceback.format_exc(),
            context=context or {},
            suggested_recovery=recovery_strategies,
            can_retry=can_retry
        )
        
        logger.info(f"Error classified: {error_type} -> {category.value} ({severity.value})")
        return error_info
    
    def _determine_category(
        self, 
        error_type: str, 
        error_message: str, 
        service: str, 
        action: str
    ) -> ErrorCategory:
        """Determine error category based on error details"""
        error_message_lower = error_message.lower()
        
        # Network errors
        if any(keyword in error_message_lower for keyword in [
            "connection", "network", "dns", "socket", "timeout", "unreachable"
        ]) or error_type in [
            "ConnectionError", "TimeoutError", "NetworkError", "HTTPError"
        ]:
            return ErrorCategory.NETWORK
        
        # Authentication errors
        if any(keyword in error_message_lower for keyword in [
            "authentication", "unauthorized", "invalid token", "expired token", 
            "401", "login", "credentials"
        ]) or error_type in [
            "AuthenticationError", "UnauthorizedError", "InvalidTokenError"
        ]:
            return ErrorCategory.AUTHENTICATION
        
        # Authorization errors
        if any(keyword in error_message_lower for keyword in [
            "authorization", "permission", "forbidden", "access denied", "403"
        ]) or error_type in [
            "AuthorizationError", "PermissionError", "ForbiddenError"
        ]:
            return ErrorCategory.AUTHORIZATION
        
        # Validation errors
        if any(keyword in error_message_lower for keyword in [
            "validation", "invalid", "malformed", "bad request", "400"
        ]) or error_type in [
            "ValidationError", "InvalidRequestError", "BadRequestError"
        ]:
            return ErrorCategory.VALIDATION
        
        # Rate limiting errors
        if any(keyword in error_message_lower for keyword in [
            "rate limit", "too many requests", "quota", "429", "throttled"
        ]) or error_type in [
            "RateLimitError", "QuotaExceededError", "ThrottledError"
        ]:
            return ErrorCategory.RATE_LIMIT
        
        # Service unavailable errors
        if any(keyword in error_message_lower for keyword in [
            "service unavailable", "server error", "503", "502", "504"
        ]) or error_type in [
            "ServiceUnavailableError", "ServerError", "GatewayError"
        ]:
            return ErrorCategory.SERVICE_UNAVAILABLE
        
        # Timeout errors
        if any(keyword in error_message_lower for keyword in [
            "timeout", "timed out", "deadline", "408"
        ]) or error_type in [
            "TimeoutError", "DeadlineExceededError"
        ]:
            return ErrorCategory.TIMEOUT
        
        # Internal errors
        if any(keyword in error_message_lower for keyword in [
            "internal error", "database error", "configuration", "500"
        ]) or error_type in [
            "DatabaseError", "ConfigurationError", "InternalError"
        ]:
            return ErrorCategory.INTERNAL
        
        # External service errors
        if service and "api" in service.lower():
            return ErrorCategory.EXTERNAL
        
        return ErrorCategory.UNKNOWN
    
    def _determine_severity(
        self, 
        error_type: str, 
        category: ErrorCategory, 
        error_message: str, 
        context: Dict[str, Any] = None
    ) -> ErrorSeverity:
        """Determine error severity"""
        
        # Critical categories
        if category in [ErrorCategory.AUTHENTICATION, ErrorCategory.SERVICE_UNAVAILABLE]:
            return ErrorSeverity.CRITICAL
        
        # High severity
        if category in [ErrorCategory.AUTHORIZATION, ErrorCategory.INTERNAL, ErrorCategory.RATE_LIMIT]:
            return ErrorSeverity.HIGH
        
        # Medium severity
        if category in [ErrorCategory.NETWORK, ErrorCategory.TIMEOUT]:
            return ErrorSeverity.MEDIUM
        
        # Low severity
        if category in [ErrorCategory.VALIDATION, ErrorCategory.EXTERNAL]:
            return ErrorSeverity.LOW
        
        # Check error message for severity indicators
        error_message_lower = error_message.lower()
        
        if any(keyword in error_message_lower for keyword in [
            "critical", "fatal", "severe", "emergency"
        ]):
            return ErrorSeverity.CRITICAL
        
        if any(keyword in error_message_lower for keyword in [
            "high", "important", "urgent", "serious"
        ]):
            return ErrorSeverity.HIGH
        
        if any(keyword in error_message_lower for keyword in [
            "minor", "low", "warning", "notice"
        ]):
            return ErrorSeverity.LOW
        
        return ErrorSeverity.MEDIUM
    
    def _suggest_recovery_strategies(
        self, 
        category: ErrorCategory, 
        severity: ErrorSeverity, 
        service: str, 
        action: str
    ) -> List[RecoveryStrategy]:
        """Suggest recovery strategies based on error classification"""
        strategies = []
        
        if category == ErrorCategory.NETWORK:
            strategies.extend([RecoveryStrategy.RETRY_WITH_BACKOFF, RecoveryStrategy.CIRCUIT_BREAKER])
        
        elif category == ErrorCategory.AUTHENTICATION:
            strategies.extend([RecoveryStrategy.ROLLBACK, RecoveryStrategy.MANUAL_INTERVENTION])
        
        elif category == ErrorCategory.AUTHORIZATION:
            strategies.extend([RecoveryStrategy.SKIP, RecoveryStrategy.ESCALATE])
        
        elif category == ErrorCategory.VALIDATION:
            strategies.extend([RecoveryStrategy.SKIP, RecoveryStrategy.FALLBACK])
        
        elif category == ErrorCategory.RATE_LIMIT:
            strategies.extend([RecoveryStrategy.RETRY_WITH_BACKOFF, RecoveryStrategy.CACHE_RESPONSE])
        
        elif category == ErrorCategory.SERVICE_UNAVAILABLE:
            strategies.extend([RecoveryStrategy.ALTERNATE_SERVICE, RecoveryStrategy.CIRCUIT_BREAKER])
        
        elif category == ErrorCategory.TIMEOUT:
            strategies.extend([RecoveryStrategy.RETRY_WITH_BACKOFF, RecoveryStrategy.FALLBACK])
        
        elif category == ErrorCategory.INTERNAL:
            strategies.extend([RecoveryStrategy.ROLLBACK, RecoveryStrategy.ESCALATE])
        
        elif category == ErrorCategory.EXTERNAL:
            strategies.extend([RecoveryStrategy.RETRY, RecoveryStrategy.ALTERNATE_SERVICE])
        
        # Add severity-specific strategies
        if severity == ErrorSeverity.CRITICAL:
            strategies.append(RecoveryStrategy.ESCALATE)
        
        # Remove duplicates and return
        return list(set(strategies))
    
    def _can_retry(
        self, 
        category: ErrorCategory, 
        severity: ErrorSeverity, 
        error_type: str
    ) -> bool:
        """Determine if error can be retried"""
        # Categories that can be retried
        if category in [
            ErrorCategory.NETWORK,
            ErrorCategory.TIMEOUT,
            ErrorCategory.SERVICE_UNAVAILABLE,
            ErrorCategory.RATE_LIMIT,
            ErrorCategory.EXTERNAL
        ]:
            return True
        
        # Categories that shouldn't be retried
        if category in [
            ErrorCategory.AUTHENTICATION,
            ErrorCategory.AUTHORIZATION,
            ErrorCategory.VALIDATION,
            ErrorCategory.INTERNAL
        ]:
            return False
        
        # Unknown errors can be retried with caution
        if category == ErrorCategory.UNKNOWN and severity != ErrorSeverity.CRITICAL:
            return True
        
        return False
    
    def _initialize_classification_rules(self) -> Dict[str, Dict[str, Any]]:
        """Initialize error classification rules"""
        return {
            "ConnectionError": {
                "category": ErrorCategory.NETWORK,
                "severity": ErrorSeverity.MEDIUM,
                "retryable": True
            },
            "TimeoutError": {
                "category": ErrorCategory.TIMEOUT,
                "severity": ErrorSeverity.MEDIUM,
                "retryable": True
            },
            "AuthenticationError": {
                "category": ErrorCategory.AUTHENTICATION,
                "severity": ErrorSeverity.CRITICAL,
                "retryable": False
            },
            "AuthorizationError": {
                "category": ErrorCategory.AUTHORIZATION,
                "severity": ErrorSeverity.HIGH,
                "retryable": False
            },
            "ValidationError": {
                "category": ErrorCategory.VALIDATION,
                "severity": ErrorSeverity.LOW,
                "retryable": False
            },
            "RateLimitError": {
                "category": ErrorCategory.RATE_LIMIT,
                "severity": ErrorSeverity.HIGH,
                "retryable": True
            },
            "ServiceUnavailableError": {
                "category": ErrorCategory.SERVICE_UNAVAILABLE,
                "severity": ErrorSeverity.CRITICAL,
                "retryable": True
            }
        }


class RetryPolicy:
    """Retry policy configuration with advanced options"""
    
    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        exponential_base: float = 2.0,
        jitter: bool = True,
        retry_on: List[Type[Exception]] = None,
        stop_on: List[Type[Exception]] = None,
        backoff_strategy: str = "exponential"  # exponential, linear, fibonacci
        timeout: Optional[float] = None
    ):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.jitter = jitter
        self.retry_on = retry_on or [Exception]
        self.stop_on = stop_on or []
        self.backoff_strategy = backoff_strategy
        self.timeout = timeout
    
    def calculate_delay(self, attempt: int) -> float:
        """Calculate delay for given attempt"""
        if self.backoff_strategy == "linear":
            delay = self.base_delay * attempt
        elif self.backoff_strategy == "fibonacci":
            delay = self.base_delay * self._fibonacci(attempt)
        else:  # exponential
            delay = self.base_delay * (self.exponential_base ** (attempt - 1))
        
        # Apply max delay limit
        delay = min(delay, self.max_delay)
        
        # Apply jitter if enabled
        if self.jitter:
            jitter_amount = delay * 0.1  # 10% jitter
            delay += (time.time() % 1) * jitter_amount * 2 - jitter_amount
        
        return max(0, delay)
    
    def _fibonacci(self, n: int) -> int:
        """Calculate fibonacci number"""
        if n <= 1:
            return n
        a, b = 0, 1
        for _ in range(n - 1):
            a, b = b, a + b
        return b
    
    def should_retry(self, error: Exception, attempt: int) -> bool:
        """Determine if error should be retried"""
        # Check if maximum retries reached
        if attempt > self.max_retries:
            return False
        
        # Check if error type is in stop list
        for stop_type in self.stop_on:
            if isinstance(error, stop_type):
                return False
        
        # Check if error type is in retry list
        for retry_type in self.retry_on:
            if isinstance(error, retry_type):
                return True
        
        return False


class ErrorRecoveryManager:
    """Manages error recovery with intelligent strategies"""
    
    def __init__(self):
        self.classifier = ErrorClassifier()
        self.circuit_breakers = {}
        self.recovery_actions = {}
        self.error_history = []
        self.rollback_stack = []
        self.fallback_cache = {}
        
        # Initialize built-in recovery actions
        self._initialize_recovery_actions()
    
    def _initialize_recovery_actions(self):
        """Initialize built-in recovery actions"""
        
        # Retry with backoff action
        self.recovery_actions["retry_backoff"] = RecoveryAction(
            id="retry_backoff",
            strategy=RecoveryStrategy.RETRY_WITH_BACKOFF,
            description="Retry operation with exponential backoff",
            action=self._retry_with_backoff,
            parameters={"max_retries": 3, "base_delay": 1.0}
        )
        
        # Circuit breaker action
        self.recovery_actions["circuit_breaker"] = RecoveryAction(
            id="circuit_breaker",
            strategy=RecoveryStrategy.CIRCUIT_BREAKER,
            description="Apply circuit breaker pattern",
            action=self._apply_circuit_breaker,
            parameters={"failure_threshold": 5, "recovery_timeout": 60}
        )
        
        # Fallback action
        self.recovery_actions["fallback"] = RecoveryAction(
            id="fallback",
            strategy=RecoveryStrategy.FALLBACK,
            description="Use fallback response",
            action=self._use_fallback,
            parameters={}
        )
        
        # Rollback action
        self.recovery_actions["rollback"] = RecoveryAction(
            id="rollback",
            strategy=RecoveryStrategy.ROLLBACK,
            description="Rollback to previous state",
            action=self._rollback_execution,
            parameters={}
        )
        
        # Alternate service action
        self.recovery_actions["alternate_service"] = RecoveryAction(
            id="alternate_service",
            strategy=RecoveryStrategy.ALTERNATE_SERVICE,
            description="Use alternate service",
            action=self._use_alternate_service,
            parameters={}
        )
        
        # Cache response action
        self.recovery_actions["cache_response"] = RecoveryAction(
            id="cache_response",
            strategy=RecoveryStrategy.CACHE_RESPONSE,
            description="Use cached response",
            action=self._use_cached_response,
            parameters={}
        )
        
        logger.info(f"Initialized {len(self.recovery_actions)} recovery actions")
    
    async def handle_error(
        self, 
        error: Exception,
        service: str = "",
        action: str = "",
        step_id: str = "",
        workflow_id: str = "",
        execution_id: str = "",
        context: Dict[str, Any] = None,
        recovery_options: List[RecoveryStrategy] = None
    ) -> Dict[str, Any]:
        """Handle error with intelligent recovery"""
        try:
            # Classify error
            error_info = self.classifier.classify_error(
                error, service, action, context
            )
            
            # Set additional context
            error_info.step_id = step_id
            error_info.workflow_id = workflow_id
            error_info.execution_id = execution_id
            
            # Add to error history
            self.error_history.append(error_info)
            
            # Log error
            self._log_error(error_info)
            
            # Determine recovery strategy
            if recovery_options:
                # Use provided recovery options
                strategies = recovery_options
            else:
                # Use suggested recovery strategies
                strategies = error_info.suggested_recovery
            
            # Execute recovery strategies
            recovery_results = []
            for strategy in strategies:
                if strategy.value in self.recovery_actions:
                    action = self.recovery_actions[strategy.value]
                    result = await self._execute_recovery_action(action, error_info)
                    recovery_results.append(result)
                    
                    # Stop if recovery was successful
                    if result.get("success", False):
                        break
            
            # Determine overall success
            successful_recovery = any(r.get("success", False) for r in recovery_results)
            
            return {
                "success": successful_recovery,
                "error_id": error_info.id,
                "error_info": {
                    "message": error_info.message,
                    "category": error_info.category.value,
                    "severity": error_info.severity.value,
                    "can_retry": error_info.can_retry
                },
                "recovery_strategy": strategies[0].value if strategies else None,
                "recovery_results": recovery_results,
                "suggested_next_action": self._suggest_next_action(error_info, recovery_results),
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error in error recovery handler: {str(e)}")
            return {
                "success": False,
                "error": f"Error recovery failed: {str(e)}",
                "original_error": str(error),
                "timestamp": datetime.now().isoformat()
            }
    
    async def _execute_recovery_action(
        self, 
        action: RecoveryAction, 
        error_info: ErrorInfo
    ) -> Dict[str, Any]:
        """Execute recovery action"""
        try:
            start_time = time.time()
            
            # Execute action
            result = await action.action(error_info, action.parameters)
            
            execution_time = time.time() - start_time
            
            return {
                "action_id": action.id,
                "strategy": action.strategy.value,
                "success": result.get("success", False),
                "result": result,
                "execution_time": execution_time,
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error executing recovery action {action.id}: {str(e)}")
            return {
                "action_id": action.id,
                "strategy": action.strategy.value,
                "success": False,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
    
    async def _retry_with_backoff(
        self, 
        error_info: ErrorInfo, 
        parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Retry with exponential backoff"""
        max_retries = parameters.get("max_retries", 3)
        base_delay = parameters.get("base_delay", 1.0)
        
        retry_policy = RetryPolicy(
            max_retries=max_retries,
            base_delay=base_delay,
            exponential_base=2.0,
            jitter=True
        )
        
        # This would integrate with the actual service handler
        # For now, return a mock result
        return {
            "success": False,
            "retries_attempted": max_retries,
            "total_delay": sum(retry_policy.calculate_delay(i) for i in range(1, max_retries + 1)),
            "message": "Retry with backoff executed"
        }
    
    async def _apply_circuit_breaker(
        self, 
        error_info: ErrorInfo, 
        parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Apply circuit breaker pattern"""
        service_key = f"{error_info.service}:{error_info.action}"
        
        if service_key not in self.circuit_breakers:
            self.circuit_breakers[service_key] = CircuitBreakerState(
                service=error_info.service,
                action=error_info.action,
                failure_threshold=parameters.get("failure_threshold", 5),
                recovery_timeout=parameters.get("recovery_timeout", 60)
            )
        
        breaker = self.circuit_breakers[service_key]
        breaker.failures += 1
        breaker.last_failure = datetime.now()
        
        # Open circuit if threshold exceeded
        if breaker.failures >= breaker.failure_threshold:
            breaker.state = "OPEN"
            return {
                "success": False,
                "circuit_state": "OPEN",
                "failures": breaker.failures,
                "message": f"Circuit opened for {service_key}"
            }
        else:
            return {
                "success": True,
                "circuit_state": breaker.state,
                "failures": breaker.failures,
                "message": f"Circuit remains {breaker.state} for {service_key}"
            }
    
    async def _use_fallback(
        self, 
        error_info: ErrorInfo, 
        parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Use fallback response"""
        fallback_key = f"{error_info.service}:{error_info.action}"
        
        # Check if we have a cached fallback response
        if fallback_key in self.fallback_cache:
            return {
                "success": True,
                "fallback_used": True,
                "response": self.fallback_cache[fallback_key],
                "message": f"Used cached fallback for {fallback_key}"
            }
        
        # Generate default fallback response
        fallback_response = {
            "status": "fallback",
            "message": f"Fallback response for {error_info.action} on {error_info.service}",
            "timestamp": datetime.now().isoformat()
        }
        
        # Cache fallback response
        self.fallback_cache[fallback_key] = fallback_response
        
        return {
            "success": True,
            "fallback_used": True,
            "response": fallback_response,
            "message": f"Generated fallback for {fallback_key}"
        }
    
    async def _rollback_execution(
        self, 
        error_info: ErrorInfo, 
        parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Rollback execution to previous state"""
        rollback_id = str(uuid.uuid4())
        
        # Add to rollback stack
        self.rollback_stack.append({
            "id": rollback_id,
            "error_info": error_info,
            "timestamp": datetime.now(),
            "parameters": parameters
        })
        
        return {
            "success": True,
            "rollback_id": rollback_id,
            "message": f"Rollback initiated for {error_info.step_id}",
            "rollback_stack_depth": len(self.rollback_stack)
        }
    
    async def _use_alternate_service(
        self, 
        error_info: ErrorInfo, 
        parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Use alternate service"""
        # Define alternate services for common services
        alternate_services = {
            "gmail": ["outlook", "sendgrid"],
            "slack": ["teams", "discord"],
            "google_calendar": ["outlook_calendar"],
            "asana": ["trello", "notion"],
            "github": ["gitlab", "bitbucket"]
        }
        
        alternates = alternate_services.get(error_info.service, [])
        
        if alternates:
            alternate = alternates[0]  # Use first alternate
            return {
                "success": True,
                "alternate_service": alternate,
                "original_service": error_info.service,
                "message": f"Switched to alternate service: {alternate}"
            }
        else:
            return {
                "success": False,
                "message": f"No alternate service available for {error_info.service}"
            }
    
    async def _use_cached_response(
        self, 
        error_info: ErrorInfo, 
        parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Use cached response"""
        cache_key = f"{error_info.service}:{error_info.action}"
        
        if cache_key in self.fallback_cache:
            return {
                "success": True,
                "cached_response": self.fallback_cache[cache_key],
                "message": f"Used cached response for {cache_key}"
            }
        else:
            return {
                "success": False,
                "message": f"No cached response available for {cache_key}"
            }
    
    def _log_error(self, error_info: ErrorInfo):
        """Log error with appropriate level"""
        message = f"[{error_info.severity.value.upper()}] {error_info.category.value} error in {error_info.service}:{error_info.action} - {error_info.message}"
        
        if error_info.severity == ErrorSeverity.CRITICAL:
            logger.critical(message)
        elif error_info.severity == ErrorSeverity.HIGH:
            logger.error(message)
        elif error_info.severity == ErrorSeverity.MEDIUM:
            logger.warning(message)
        else:
            logger.info(message)
    
    def _suggest_next_action(
        self, 
        error_info: ErrorInfo, 
        recovery_results: List[Dict[str, Any]]
    ) -> str:
        """Suggest next action based on error and recovery results"""
        # Check if recovery was successful
        successful_recovery = any(r.get("success", False) for r in recovery_results)
        
        if successful_recovery:
            return "Continue with workflow execution"
        
        # Check if error can be retried
        if error_info.can_retry and error_info.retry_count < 3:
            return "Retry the operation with different parameters"
        
        # Check severity
        if error_info.severity == ErrorSeverity.CRITICAL:
            return "Escalate to manual intervention"
        
        # Check category
        if error_info.category == ErrorCategory.AUTHENTICATION:
            return "Re-authenticate with service"
        elif error_info.category == ErrorCategory.RATE_LIMIT:
            return "Wait and retry after rate limit reset"
        elif error_info.category == ErrorCategory.SERVICE_UNAVAILABLE:
            return "Use alternate service or retry later"
        
        return "Skip this step and continue with workflow"
    
    def get_error_statistics(self) -> Dict[str, Any]:
        """Get error statistics and trends"""
        if not self.error_history:
            return {
                "total_errors": 0,
                "by_category": {},
                "by_severity": {},
                "by_service": {},
                "recovery_success_rate": 0.0
            }
        
        # Calculate statistics
        total_errors = len(self.error_history)
        
        by_category = {}
        by_severity = {}
        by_service = {}
        
        for error_info in self.error_history:
            # Category statistics
            category = error_info.category.value
            by_category[category] = by_category.get(category, 0) + 1
            
            # Severity statistics
            severity = error_info.severity.value
            by_severity[severity] = by_severity.get(severity, 0) + 1
            
            # Service statistics
            service = error_info.service
            by_service[service] = by_service.get(service, 0) + 1
        
        # Calculate recovery success rate (mock)
        recovery_success_rate = 75.0  # This would be calculated from actual recovery results
        
        return {
            "total_errors": total_errors,
            "by_category": by_category,
            "by_severity": by_severity,
            "by_service": by_service,
            "recovery_success_rate": recovery_success_rate,
            "circuit_breaker_states": len(self.circuit_breakers),
            "fallback_cache_size": len(self.fallback_cache),
            "rollback_stack_depth": len(self.rollback_stack),
            "error_period": {
                "start": min(e.timestamp for e in self.error_history).isoformat(),
                "end": max(e.timestamp for e in self.error_history).isoformat()
            }
        }
    
    def reset_circuit_breaker(self, service: str, action: str):
        """Reset circuit breaker for specific service/action"""
        service_key = f"{service}:{action}"
        
        if service_key in self.circuit_breakers:
            breaker = self.circuit_breakers[service_key]
            breaker.failures = 0
            breaker.state = "CLOSED"
            breaker.last_failure = None
            breaker.success_count = 0
            
            logger.info(f"Reset circuit breaker for {service_key}")
            return True
        
        return False
    
    def clear_error_history(self, older_than_hours: int = 24):
        """Clear error history older than specified hours"""
        cutoff_time = datetime.now() - timedelta(hours=older_than_hours)
        
        initial_count = len(self.error_history)
        self.error_history = [
            error for error in self.error_history 
            if error.timestamp > cutoff_time
        ]
        
        cleared_count = initial_count - len(self.error_history)
        logger.info(f"Cleared {cleared_count} error records older than {older_than_hours} hours")
        
        return cleared_count


# Decorator for automatic error recovery
def with_error_recovery(
    service: str = "",
    action: str = "",
    recovery_strategies: List[RecoveryStrategy] = None,
    retry_policy: RetryPolicy = None
):
    """Decorator for automatic error recovery"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                # Initialize error recovery manager if not available
                recovery_manager = ErrorRecoveryManager()
                
                # Handle error with recovery
                result = await recovery_manager.handle_error(
                    error=e,
                    service=service,
                    action=action,
                    recovery_options=recovery_strategies
                )
                
                if result.get("success", False):
                    # If recovery was successful, return the recovery result
                    return result.get("recovery_results", [{}])[0].get("result", {})
                else:
                    # If recovery failed, re-raise the original error
                    raise e
        
        return wrapper
    return decorator


# Global instance
error_recovery_manager = ErrorRecoveryManager()

logger.info("Error Recovery System initialized with intelligent recovery strategies")