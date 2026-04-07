# Refactoring Plan: Large Files

**Last Updated**: February 4, 2026

This document outlines the plan to refactor large files (>500 lines) into smaller, more maintainable modules.

---

## Overview

Several files in the codebase have grown beyond maintainable sizes. Large files are difficult to:
- Navigate and understand
- Test effectively
- Modify without introducing bugs
- Review in pull requests

**Goal**: Break down large files into focused modules with clear responsibilities.

---

## Files to Refactor

### Priority 1: Critical

| File | Lines | Status | Priority |
|------|-------|--------|----------|
| `backend/advanced_workflow_orchestrator.py` | 3,291 | Active | HIGH |
| `backend/core/llm/byok_handler.py` | 1,161 | Active | HIGH |
| `backend/core/agent_governance_service.py` | 538 | Active | MEDIUM |
| `backend/core/api_routes.py` | 555 | Active | MEDIUM |

---

## 1. Advanced Workflow Orchestrator (3,291 lines)

### Current Structure

```python
# advanced_workflow_orchestrator.py

class WorkflowStepType(Enum)           # Lines 37-83
class WorkflowStatus(Enum)             # Lines 84-93
class RetryPolicy                      # Lines 94-116
class WorkflowStep                     # Lines 117-131
class WorkflowContext                  # Lines 132-146
class WorkflowDefinition               # Lines 147-156
class AdvancedWorkflowOrchestrator:    # Lines 157-3291
    # ~50+ methods
```

### Proposed New Structure

```
backend/core/workflow/
├── __init__.py
├── models.py                    # Data models (StepType, Status, RetryPolicy, Step, Context, Definition)
├── orchestrator.py              # Main orchestration logic
├── executors/
│   ├── __init__.py
│   ├── base.py                  # Base executor interface
│   ├── nlu_executor.py          # NLU analysis execution
│   ├── integration_executors.py # Email, Slack, Asana, Notion, Gmail, HubSpot, Salesforce
│   ├── data_executors.py        # API calls, data transformation
│   ├── logic_executors.py       # Conditional logic, parallel execution
│   ├── financial_executors.py   # Invoice processing, B2B PO detection, cost leak detection
│   └── agent_executors.py       # Agent execution, background agents
├── utils/
│   ├── __init__.py
│   ├── variable_resolver.py     # Variable resolution logic
│   ├── condition_evaluator.py   # Condition evaluation logic
│   └── persistence.py           # Execution state persistence
└── templates/
    ├── __init__.py
    └── predefined_workflows.py  # Predefined workflow definitions
```

### Module Breakdown

#### `models.py` (~200 lines)

**Purpose**: Define all workflow data models

**Classes to move**:
- `WorkflowStepType` (Enum)
- `WorkflowStatus` (Enum)
- `RetryPolicy` (dataclass)
- `WorkflowStep` (dataclass)
- `WorkflowContext` (dataclass)
- `WorkflowDefinition` (dataclass)

**Example**:
```python
# backend/core/workflow/models.py

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

class WorkflowStepType(Enum):
    """Types of workflow steps"""
    NLU_ANALYSIS = "nlu_analysis"
    TASK_CREATION = "task_creation"
    EMAIL_SEND = "email_send"
    # ... all step types

class WorkflowStatus(Enum):
    """Workflow execution status"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    WAITING_APPROVAL = "waiting_approval"

@dataclass
class RetryPolicy:
    """Configuration for retry behavior"""
    max_retries: int = 3
    initial_delay_seconds: float = 1.0
    max_delay_seconds: float = 60.0
    exponential_base: float = 2.0
    retryable_errors: List[str] = field(default_factory=list)

    def get_delay(self, attempt: int) -> float:
        """Calculate delay for retry attempt"""
        pass

    def should_retry(self, error: str, attempt: int) -> bool:
        """Determine if error is retryable"""
        pass

@dataclass
class WorkflowStep:
    """A single workflow step"""
    id: str
    type: WorkflowStepType
    name: str
    config: Dict[str, Any] = field(default_factory=dict)
    next_steps: List[str] = field(default_factory=list)
    condition: Optional[str] = None
    retry_policy: Optional[RetryPolicy] = None

@dataclass
class WorkflowContext:
    """Context for workflow execution"""
    execution_id: str
    workflow_id: str
    variables: Dict[str, Any] = field(default_factory=dict)
    step_results: Dict[str, Any] = field(default_factory=dict)
    current_step_id: Optional[str] = None
    status: WorkflowStatus = WorkflowStatus.PENDING
    error: Optional[str] = None
    snapshot_data: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class WorkflowDefinition:
    """Definition of a workflow"""
    id: str
    name: str
    description: str
    steps: Dict[str, WorkflowStep]
    start_step_id: str
    category: str = "automation"
    tags: List[str] = field(default_factory=list)
    complexity_score: int = 0
```

#### `orchestrator.py` (~600 lines)

**Purpose**: Main orchestration logic (workflow lifecycle)

**Methods to keep**:
- `__init__`
- `trigger_event`
- `generate_dynamic_workflow`
- `execute_workflow`
- `resume_workflow`
- `fork_execution`
- `_run_forked_execution`
- `_continue_workflow`
- `_save_execution_state`
- `_load_execution_state`
- `_create_snapshot`
- `_restore_active_executions`
- `get_workflow_definitions`
- `get_workflow_execution_stats`
- `_calculate_complexity_score`

**Example**:
```python
# backend/core/workflow/orchestrator.py

from typing import Dict, List, Optional, Any
from .models import WorkflowDefinition, WorkflowContext, WorkflowStatus
from .executors import get_executor
from .utils.persistence import save_execution_state, load_execution_state

class AdvancedWorkflowOrchestrator:
    """Orchestrates complex multi-step workflows"""

    def __init__(self):
        self.ai_service = self._initialize_ai_service()
        self.predefined_workflows = self._load_predefined_workflows()

    async def execute_workflow(
        self,
        workflow_id: str,
        input_data: Dict[str, Any],
        user_id: Optional[str] = None,
        resume_from_step: Optional[str] = None
    ) -> WorkflowContext:
        """Execute a workflow with the given input data"""
        # Workflow execution logic
        pass

    async def resume_workflow(self, execution_id: str, step_id: str) -> WorkflowContext:
        """Resume a paused or failed workflow"""
        pass

    async def fork_execution(
        self,
        original_execution_id: str,
        step_id: str,
        new_variables: Optional[Dict[str, Any]] = None
    ) -> Optional[str]:
        """Create a fork of an execution at a specific step"""
        pass
```

#### `executors/base.py` (~100 lines)

**Purpose**: Base executor interface and common logic

**Example**:
```python
# backend/core/workflow/executors/base.py

from abc import ABC, abstractmethod
from typing import Dict, Any
from ..models import WorkflowStep, WorkflowContext

class BaseStepExecutor(ABC):
    """Base class for workflow step executors"""

    def __init__(self, orchestrator):
        self.orchestrator = orchestrator

    @abstractmethod
    async def execute(self, step: WorkflowStep, context: WorkflowContext) -> Dict[str, Any]:
        """Execute a workflow step"""
        pass

    async def with_retry(
        self,
        step: WorkflowStep,
        context: WorkflowContext,
        execution_func: callable
    ) -> Dict[str, Any]:
        """Execute step with retry logic"""
        if not step.retry_policy:
            return await execution_func()

        retry_policy = step.retry_policy
        last_error = None

        for attempt in range(retry_policy.max_retries + 1):
            try:
                return await execution_func()
            except Exception as e:
                last_error = str(e)
                if not retry_policy.should_retry(last_error, attempt):
                    break

                delay = retry_policy.get_delay(attempt)
                await asyncio.sleep(delay)

        raise Exception(f"Step failed after {retry_policy.max_retries} retries: {last_error}")
```

#### `executors/integration_executors.py` (~400 lines)

**Purpose**: Integration step executors

**Methods to move**:
- `_execute_email_send`
- `_execute_slack_notification`
- `_execute_asana_integration`
- `_execute_notion_integration`
- `_execute_gmail_fetch`
- `_execute_gmail_integration`
- `_execute_gmail_search`
- `_execute_hubspot_integration`
- `_execute_salesforce_integration`

**Example**:
```python
# backend/core/workflow/executors/integration_executors.py

from typing import Dict, Any
from ..models import WorkflowStep, WorkflowContext
from .base import BaseStepExecutor

class EmailExecutor(BaseStepExecutor):
    """Execute email send steps"""

    async def execute(self, step: WorkflowStep, context: WorkflowContext) -> Dict[str, Any]:
        """Send email"""
        to = self.orchestrator._resolve_variables(step.config.get("to"), context)
        subject = self.orchestrator._resolve_variables(step.config.get("subject"), context)
        body = self.orchestrator._resolve_variables(step.config.get("body"), context)

        # Email sending logic
        return {"success": True, "to": to}

class SlackExecutor(BaseStepExecutor):
    """Execute Slack notification steps"""

    async def execute(self, step: WorkflowStep, context: WorkflowContext) -> Dict[str, Any]:
        """Send Slack notification"""
        pass

class AsanaExecutor(BaseStepExecutor):
    """Execute Asana integration steps"""

    async def execute(self, step: WorkflowStep, context: WorkflowContext) -> Dict[str, Any]:
        """Execute Asana task"""
        pass
```

#### `executors/logic_executors.py` (~300 lines)

**Purpose**: Logic control executors

**Methods to move**:
- `_execute_conditional_logic`
- `_execute_parallel_execution`
- `_execute_delay`

**Example**:
```python
# backend/core/workflow/executors/logic_executors.py

from typing import Dict, Any
from ..models import WorkflowStep, WorkflowContext, WorkflowDefinition
from .base import BaseStepExecutor

class ConditionalLogicExecutor(BaseStepExecutor):
    """Execute conditional logic steps"""

    async def execute(self, step: WorkflowStep, context: WorkflowContext) -> Dict[str, Any]:
        """Evaluate conditions and route to appropriate next steps"""
        conditions = step.config.get("conditions", {})
        result = await self.orchestrator._check_conditions(conditions, context)
        return {"condition_met": result}

class ParallelExecutionExecutor(BaseStepExecutor):
    """Execute parallel execution steps"""

    async def execute(self, step: WorkflowStep, context: WorkflowContext) -> Dict[str, Any]:
        """Execute multiple steps in parallel"""
        pass

class DelayExecutor(BaseStepExecutor):
    """Execute delay steps"""

    async def execute(self, step: WorkflowStep, context: WorkflowContext) -> Dict[str, Any]:
        """Delay execution for specified time"""
        delay_seconds = step.config.get("delay_seconds", 0)
        await asyncio.sleep(delay_seconds)
        return {"delayed": True, "seconds": delay_seconds}
```

#### `executors/data_executors.py` (~250 lines)

**Purpose**: Data processing executors

**Methods to move**:
- `_execute_api_call`
- `_execute_data_transformation` (if exists)
- `_execute_notion_search`
- `_execute_notion_db_query`
- `_execute_app_search`

**Example**:
```python
# backend/core/workflow/executors/data_executors.py

from typing import Dict, Any
from ..models import WorkflowStep, WorkflowContext
from .base import BaseStepExecutor

class ApiCallExecutor(BaseStepExecutor):
    """Execute API call steps"""

    async def execute(self, step: WorkflowStep, context: WorkflowContext) -> Dict[str, Any]:
        """Make HTTP API call"""
        url = self.orchestrator._resolve_variables(step.config.get("url"), context)
        method = step.config.get("method", "GET")
        headers = step.config.get("headers", {})
        body = step.config.get("body")

        # API call logic
        async with aiohttp.request(method, url, headers=headers, json=body) as response:
            return await response.json()

class NotionSearchExecutor(BaseStepExecutor):
    """Execute Notion search steps"""

    async def execute(self, step: WorkflowStep, context: WorkflowContext) -> Dict[str, Any]:
        """Search Notion database"""
        pass
```

#### `executors/financial_executors.py` (~200 lines)

**Purpose**: Financial and business operation executors

**Methods to move**:
- `_execute_invoice_processing`
- `_execute_b2b_po_detection`
- `_execute_cost_leak_detection` (if exists)
- `_execute_budget_check` (if exists)

**Example**:
```python
# backend/core/workflow/executors/financial_executors.py

from typing import Dict, Any
from ..models import WorkflowStep, WorkflowContext
from .base import BaseStepExecutor

class InvoiceProcessingExecutor(BaseStepExecutor):
    """Execute invoice processing steps"""

    async def execute(self, step: WorkflowStep, context: WorkflowContext) -> Dict[str, Any]:
        """Process invoice data"""
        pass

class B2bPoDetectionExecutor(BaseStepExecutor):
    """Execute B2B PO detection steps"""

    async def execute(self, step: WorkflowStep, context: WorkflowContext) -> Dict[str, Any]:
        """Detect B2B purchase orders"""
        pass
```

#### `executors/agent_executors.py` (~200 lines)

**Purpose**: Agent-related executors

**Methods to move**:
- `_execute_agent_execution`
- `_execute_background_agent_start`
- `_execute_background_agent_stop`
- `_execute_business_agent_execution`

**Example**:
```python
# backend/core/workflow/executors/agent_executors.py

from typing import Dict, Any
from ..models import WorkflowStep, WorkflowContext
from .base import BaseStepExecutor

class AgentExecutionExecutor(BaseStepExecutor):
    """Execute agent execution steps"""

    async def execute(self, step: WorkflowStep, context: WorkflowContext) -> Dict[str, Any]:
        """Execute a Computer Use Agent"""
        pass

class BackgroundAgentStartExecutor(BaseStepExecutor):
    """Execute background agent start steps"""

    async def execute(self, step: WorkflowStep, context: WorkflowContext) -> Dict[str, Any]:
        """Start a background agent"""
        pass
```

#### `utils/variable_resolver.py` (~200 lines)

**Purpose**: Variable resolution logic

**Methods to move**:
- `_resolve_variables`

**Example**:
```python
# backend/core/workflow/utils/variable_resolver.py

import re
from typing import Any, Dict
from ..models import WorkflowContext

class VariableResolver:
    """Resolve variables in workflow configurations"""

    def __init__(self, context: WorkflowContext):
        self.context = context

    def resolve(self, value: Any) -> Any:
        """Resolve variables in a value"""
        if isinstance(value, str):
            return self._resolve_string(value)
        elif isinstance(value, dict):
            return {k: self.resolve(v) for k, v in value.items()}
        elif isinstance(value, list):
            return [self.resolve(item) for item in value]
        return value

    def _resolve_string(self, value: str) -> Any:
        """Resolve variables in a string"""
        # Check for variable references like ${variable_name}
        pattern = r'\$\{([^}]+)\}'

        def replace_var(match):
            var_path = match.group(1)
            return self._get_variable_value(var_path)

        return re.sub(pattern, replace_var, value)

    def _get_variable_value(self, path: str) -> Any:
        """Get variable value from context using dot notation"""
        keys = path.split('.')
        value = self.context.variables

        for key in keys:
            if isinstance(value, dict):
                value = value.get(key)
            else:
                return None

        return value
```

#### `utils/condition_evaluator.py` (~150 lines)

**Purpose**: Condition evaluation logic

**Methods to move**:
- `_check_conditions`
- `_evaluate_condition`

**Example**:
```python
# backend/core/workflow/utils/condition_evaluator.py

import ast
import operator
from typing import Dict, Any
from ..models import WorkflowContext

class ConditionEvaluator:
    """Evaluate conditions for workflow routing"""

    OPERATORS = {
        '==': operator.eq,
        '!=': operator.ne,
        '>': operator.gt,
        '<': operator.lt,
        '>=': operator.ge,
        '<=': operator.le,
        'and': lambda a, b: a and b,
        'or': lambda a, b: a or b,
        'not': lambda a: not a,
    }

    def __init__(self, context: WorkflowContext):
        self.context = context

    async def check_conditions(self, conditions: Dict[str, Any]) -> bool:
        """Check if conditions are met"""
        pass

    async def evaluate(self, condition: str) -> bool:
        """Evaluate a condition string"""
        pass
```

#### `utils/persistence.py` (~200 lines)

**Purpose**: Execution state persistence

**Methods to move**:
- `_save_execution_state`
- `_load_execution_state`

**Example**:
```python
# backend/core/workflow/utils/persistence.py

from typing import Optional
from ..models import WorkflowContext

async def save_execution_state(context: WorkflowContext) -> bool:
    """Save workflow execution state to database"""
    try:
        from core.database import get_db_session
        from core.models import WorkflowExecution, WorkflowExecutionStatus

        with get_db_session(commit=True) as db:
            execution = WorkflowExecution(
                execution_id=context.execution_id,
                workflow_id=context.workflow_id,
                status=context.status.value,
                input_data=context.variables,
                output_data=context.step_results,
                current_step_id=context.current_step_id
            )
            db.add(execution)
        return True
    except Exception as e:
        return False

async def load_execution_state(execution_id: str) -> Optional[WorkflowContext]:
    """Load workflow execution state from database"""
    try:
        from core.database import get_db_session
        from core.models import WorkflowExecution
        from sqlalchemy import select

        with get_db_session() as db:
            result = db.execute(
                select(WorkflowExecution).where(
                    WorkflowExecution.execution_id == execution_id
                )
            )
            execution = result.scalar_one_or_none()

            if execution:
                return WorkflowContext(
                    execution_id=execution.execution_id,
                    workflow_id=execution.workflow_id,
                    variables=execution.input_data or {},
                    step_results=execution.output_data or {},
                    current_step_id=execution.current_step_id,
                    status=WorkflowStatus(execution.status)
                )
        return None
    except Exception as e:
        return None
```

#### `templates/predefined_workflows.py` (~500 lines)

**Purpose**: Predefined workflow definitions

**Methods to move**:
- `_load_predefined_workflows`

**Example**:
```python
# backend/core/workflow/templates/predefined_workflows.py

from typing import Dict, List
from ..models import WorkflowDefinition, WorkflowStep, WorkflowStepType

def load_predefined_workflows() -> Dict[str, WorkflowDefinition]:
    """Load all predefined workflow templates"""
    return {
        "email_follow_up": create_email_follow_up_workflow(),
        "task_creation": create_task_creation_workflow(),
        "invoice_processing": create_invoice_processing_workflow(),
        # ... more workflows
    }

def create_email_follow_up_workflow() -> WorkflowDefinition:
    """Create email follow-up workflow"""
    return WorkflowDefinition(
        id="email_follow_up",
        name="Email Follow-Up",
        description="Send follow-up emails to leads",
        steps={
            "step_1": WorkflowStep(
                id="step_1",
                type=WorkflowStepType.NLU_ANALYSIS,
                name="Analyze Lead",
                config={"prompt": "Analyze lead information"}
            ),
            "step_2": WorkflowStep(
                id="step_2",
                type=WorkflowStepType.EMAIL_SEND,
                name="Send Email",
                config={"to": "${email}", "subject": "Follow-up"}
            )
        },
        start_step_id="step_1"
    )
```

### Migration Steps

1. **Create new directory structure**
   ```bash
   mkdir -p backend/core/workflow/{executors,utils,templates}
   touch backend/core/workflow/__init__.py
   touch backend/core/workflow/executors/__init__.py
   touch backend/core/workflow/utils/__init__.py
   touch backend/core/workflow/templates/__init__.py
   ```

2. **Move models** (Low risk)
   - Create `models.py`
   - Move dataclasses and enums
   - Update imports in `orchestrator.py`

3. **Create executor base** (Low risk)
   - Create `executors/base.py`
   - Define base executor interface

4. **Move executors** (Medium risk)
   - Create each executor module
   - Move specific executor methods
   - Update `orchestrator.py` to use executors

5. **Create utilities** (Medium risk)
   - Create `utils/variable_resolver.py`
   - Create `utils/condition_evaluator.py`
   - Create `utils/persistence.py`
   - Update `orchestrator.py` imports

6. **Move templates** (Low risk)
   - Create `templates/predefined_workflows.py`
   - Move predefined workflow definitions

7. **Update main orchestrator** (High risk)
   - Refactor `orchestrator.py` to use new modules
   - Update all imports
   - Test thoroughly

8. **Update imports across codebase**
   - Update imports in other files that reference `advanced_workflow_orchestrator`
   - Ensure backward compatibility if needed

9. **Testing**
   - Run all workflow tests
   - Test executor modules independently
   - Test integration between modules

10. **Cleanup**
    - Remove old file after verification
    - Update documentation

---

## 2. BYOK Handler (1,161 lines)

### Current Structure

```python
# core/llm/byok_handler.py

class ByoHandler:                      # Main class (~1100 lines)
    # Multiple LLM provider integrations
    # Token streaming logic
    # Provider selection logic
    # Error handling
```

### Proposed New Structure

```
backend/core/llm/
├── byok_handler.py              # Main handler (coordinator)
├── providers/
│   ├── __init__.py
│   ├── base.py                  # Base provider interface
│   ├── openai.py                # OpenAI provider
│   ├── anthropic.py             # Anthropic provider
│   ├── google.py                # Google Gemini provider
│   ├── deepseek.py              # DeepSeek provider
│   └── provider_factory.py      # Provider factory
├── streaming/
│   ├── __init__.py
│   ├── token_stream.py          # Token streaming logic
│   └── stream_processor.py     # Stream processing utilities
└── utils/
    ├── __init__.py
    ├── token_counter.py         # Token counting utilities
    └── cost_calculator.py       # Cost calculation
```

### Module Breakdown

#### `providers/base.py` (~150 lines)

```python
from abc import ABC, abstractmethod
from typing import AsyncIterator, Dict, Any, Optional

class BaseLLMProvider(ABC):
    """Base interface for LLM providers"""

    def __init__(self, api_key: str, config: Dict[str, Any] = None):
        self.api_key = api_key
        self.config = config or {}

    @abstractmethod
    async def stream_completion(
        self,
        messages: list,
        **kwargs
    ) -> AsyncIterator[str]:
        """Stream completion tokens"""
        pass

    @abstractmethod
    async def chat_completion(
        self,
        messages: list,
        **kwargs
    ) -> Dict[str, Any]:
        """Non-streaming completion"""
        pass

    @abstractmethod
    def count_tokens(self, text: str) -> int:
        """Count tokens for text"""
        pass

    @abstractmethod
    def get_model_info(self) -> Dict[str, Any]:
        """Get model information"""
        pass
```

#### `providers/openai.py` (~200 lines)

```python
from .base import BaseLLMProvider
from typing import AsyncIterator, Dict, Any

class OpenAIProvider(BaseLLMProvider):
    """OpenAI GPT provider"""

    async def stream_completion(
        self,
        messages: list,
        model: str = "gpt-4",
        **kwargs
    ) -> AsyncIterator[str]:
        """Stream OpenAI completion"""
        # OpenAI-specific implementation
        pass
```

#### `byok_handler.py` (refactored, ~400 lines)

```python
from typing import Dict, Any, AsyncIterator
from .providers.provider_factory import get_provider
from .streaming.token_stream import TokenStream

class ByoHandler:
    """BYOK LLM handler with multi-provider support"""

    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.default_provider = self.config.get("default_provider", "openai")
        self.providers = {}

    def get_provider(self, provider_name: str = None):
        """Get LLM provider instance"""
        provider_name = provider_name or self.default_provider
        if provider_name not in self.providers:
            self.providers[provider_name] = get_provider(provider_name)
        return self.providers[provider_name]

    async def stream_completion(
        self,
        messages: list,
        provider: str = None,
        **kwargs
    ) -> AsyncIterator[str]:
        """Stream completion from provider"""
        provider_instance = self.get_provider(provider)
        async for token in provider_instance.stream_completion(messages, **kwargs):
            yield token
```

---

## 3. Agent Governance Service (538 lines)

### Current Structure

```python
# core/agent_governance_service.py

class AgentGovernanceService:          # Main class
    # Agent lifecycle management
    # Permission checks
    # Maturity tracking
```

### Proposed Refactoring

The file is already relatively well-organized. Suggested improvements:

1. Extract agent permission logic to `agent_permissions.py`
2. Extract maturity tracking to `agent_maturity.py`
3. Keep main orchestration in `agent_governance_service.py`

**New Structure**:
```
backend/core/governance/
├── __init__.py
├── agent_governance_service.py    # Main service (orchestration)
├── agent_permissions.py           # Permission checking logic
├── agent_maturity.py              # Maturity level tracking
└── models.py                      # Governance-related models
```

---

## 4. API Routes (555 lines)

### Current Structure

```python
# core/api_routes.py

# Multiple API endpoints mixed together
# User management
# Authentication
# Various utilities
```

### Proposed Refactoring

```
backend/core/api/
├── __init__.py
├── user_routes.py               # User management endpoints
├── auth_routes.py               # Authentication endpoints
├── utility_routes.py            # Utility endpoints
└── middleware.py                # API middleware
```

---

## Testing Strategy

### Before Refactoring

1. **Run existing tests**
   ```bash
   pytest backend/tests/ -v
   ```

2. **Create test coverage baseline**
   ```bash
   pytest backend/tests/ --cov=backend --cov-report=html
   ```

3. **Document current behavior**
   - Record all test results
   - Note any failing tests
   - Document edge cases

### During Refactoring

1. **Test each module independently**
   ```bash
   pytest backend/tests/workflow/test_executors.py -v
   pytest backend/tests/workflow/test_utils.py -v
   ```

2. **Integration testing**
   ```bash
   pytest backend/tests/workflow/test_integration.py -v
   ```

3. **Maintain test coverage**
   - Ensure coverage doesn't decrease
   - Add tests for new modules

### After Refactoring

1. **Full test suite**
   ```bash
   pytest backend/tests/ -v
   ```

2. **Performance testing**
   - Ensure no performance regression
   - Profile if needed

3. **Documentation update**
   - Update imports in documentation
   - Update code examples

---

## Risk Mitigation

### High-Risk Changes

1. **Advanced Workflow Orchestrator**: Critical business logic
   - **Risk**: Breaking workflow execution
   - **Mitigation**: Comprehensive testing, gradual migration

2. **BYOK Handler**: Core LLM integration
   - **Risk**: Breaking LLM calls
   - **Mitigation**: Provider abstraction, backward compatibility

### Medium-Risk Changes

1. **Agent Governance Service**: Governance logic
   - **Risk**: Breaking permission checks
   - **Mitigation**: Maintain public API, thorough testing

2. **API Routes**: API endpoints
   - **Risk**: Breaking API contracts
   - **Mitigation**: API versioning, integration tests

### Low-Risk Changes

1. **Extracting utilities**: Reusable functions
   - **Risk**: Import errors
   - **Mitigation**: Clear import paths

---

## Rollback Plan

If issues arise after refactoring:

1. **Git Revert**
   ```bash
   git revert <commit-hash>
   ```

2. **Feature Flags**
   - Keep old code behind feature flag
   - Enable new code gradually

3. **Backward Compatibility**
   - Maintain old imports
   - Deprecate gradually

---

## Estimated Effort

| File | Lines | Modules | Estimated Time | Risk Level |
|------|-------|---------|----------------|------------|
| Advanced Workflow Orchestrator | 3,291 | 15+ | 24-32 hours | HIGH |
| BYOK Handler | 1,161 | 8 | 16-20 hours | HIGH |
| Agent Governance Service | 538 | 3 | 8-12 hours | MEDIUM |
| API Routes | 555 | 4 | 6-8 hours | MEDIUM |
| **Total** | **5,545** | **30+** | **54-72 hours** | **HIGH** |

---

## Recommendations

### Immediate Actions

1. **Start with low-risk refactoring**
   - Agent Governance Service (well-contained)
   - API Routes (clear boundaries)

2. **Defer high-risk refactoring**
   - Advanced Workflow Orchestrator (requires careful planning)
   - BYOK Handler (critical path)

### Long-term Strategy

1. **Establish patterns**
   - Create module structure standards
   - Document best practices

2. **Incremental improvements**
   - Refactor one file at a time
   - Test thoroughly between changes

3. **Prevent future growth**
   - Set maximum file size limits
   - Code review guidelines

---

## Success Criteria

Refactoring is successful when:

- ✅ All tests pass
- ✅ No functionality regression
- ✅ Code is more maintainable
- ✅ File sizes are under 500 lines
- ✅ Clear separation of concerns
- ✅ Improved test coverage

---

## Next Steps

1. **Review and approve this plan**
2. **Create feature branches for each file**
3. **Implement refactoring incrementally**
4. **Test thoroughly at each step**
5. **Update documentation**
6. **Merge and monitor**

---

*Last updated: February 4, 2026*
