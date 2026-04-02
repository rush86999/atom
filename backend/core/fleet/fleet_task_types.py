from enum import Enum
from typing import Dict

class FailurePolicy(str, Enum):
    STOP_ON_FAILURE = "stop"        # Halt the entire chain if this link fails
    CONTINUE_ON_FAILURE = "continue" # Allow other parallel links to finish, mark chain as partial
    RETRY_THEN_STOP = "retry_stop"   # Specific for critical but flaky tasks

class FleetTaskType(str, Enum):
    DATA_PROCESSING = "data_processing" # High volume, parallelizable, usually continue on failure
    RESEARCH = "research"               # Multi-agent lookup, usually continue on failure
    TRANSACTIONAL = "transactional"     # Sequential/Critical, usually stop on failure
    CREATIVE = "creative"               # Iterative, stop on failure
    ANALYSIS = "analysis"               # Summarization, continue on failure

# Default policies for task types
DEFAULT_FAILURE_POLICIES: Dict[FleetTaskType, FailurePolicy] = {
    FleetTaskType.DATA_PROCESSING: FailurePolicy.CONTINUE_ON_FAILURE,
    FleetTaskType.RESEARCH: FailurePolicy.CONTINUE_ON_FAILURE,
    FleetTaskType.TRANSACTIONAL: FailurePolicy.STOP_ON_FAILURE,
    FleetTaskType.CREATIVE: FailurePolicy.STOP_ON_FAILURE,
    FleetTaskType.ANALYSIS: FailurePolicy.CONTINUE_ON_FAILURE,
}
