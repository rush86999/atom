import re
import logging
from typing import Dict, List, Set, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class OptimizationSuggestion:
    type: str # "parallelization", "dead_code", etc.
    description: str
    affected_nodes: List[str]
    savings_estimate_ms: int
    action: str # "reconfigure_parallel"

class WorkflowOptimizer:
    """
    Static Analysis engine for Workflows.
    """
    
    def __init__(self):
        # Regex to find {{ variable }} patterns
        self.var_pattern = re.compile(r'\{\{([^{}]+)\}\}')

    def analyze(self, workflow_def: Dict[str, Any]) -> List[OptimizationSuggestion]:
        """
        Analyze a workflow definition for optimization opportunities.
        """
        suggestions = []
        
        # 1. Build Dependency Graph
        # Map of StepID -> Set of StepIDs that this step depends on (Data Dependency)
        dependencies: Dict[str, Set[str]] = {}
        
        # Map of StepID -> Step Definition
        steps_map = {s['step_id']: s for s in workflow_def.get('steps', [])}
        
        if not steps_map:
            return []

        # Extract Dependencies
        for step in workflow_def.get('steps', []):
            step_id = step['step_id']
            deps = self._extract_dependencies(step)
            dependencies[step_id] = deps

        # 2. Key Analysis: Sequential vs Parallel
        # We need to look at the flow. This is tricky for a generic graph, 
        # but we can look for "Chains" of steps that are purely sequential but have no data dependency.
        
        # Simplification: Look for patterns of A -> B where B does NOT depend on A
        # and A does NOT determine B's execution (not conditional).
        
        # We iterate through the steps to find sequential connections
        for step_id, step in steps_map.items():
            # Check 'next_steps'
            next_steps = step.get('next_steps', [])
            
            # We are looking for a sequential chain: Step A -> [Step B]
            if len(next_steps) == 1:
                next_step_id = next_steps[0]
                next_step = steps_map.get(next_step_id)
                
                if not next_step:
                    continue
                    
                # Requirement 1: Step B must NOT have a data dependency on Step A
                # "Does B need data from A?"
                b_deps = dependencies.get(next_step_id, set())
                is_dependent = step_id in b_deps
                
                # Requirement 2: Step A must NOT be a Conditional Logic step
                # (If A decides whether B runs, they arguably cannot be parallelized easily 
                # without hoisting the condition, which is complex)
                is_conditional = step.get('step_type') == 'conditional_logic'
                
                # Requirement 3: Step B should not have side-effects that A relies on (Hard to know statically)
                # We assume "read-only" safety or distinct systems for now.
                
                if not is_dependent and not is_conditional:
                    # Potential Parallelization!
                    # Suggestion: Merge A and B into a parallel block?
                    # Or just general advice.
                    
                    suggestions.append(OptimizationSuggestion(
                        type="parallelization",
                        description=f"Step '{next_step.get('description', next_step_id)}' follows '{step.get('description', step_id)}' but does not use its data. They could run in parallel.",
                        affected_nodes=[step_id, next_step_id],
                        savings_estimate_ms=1000, # Placeholder average
                        action="reconfigure_parallel"
                    ))

        return suggestions

    def _extract_dependencies(self, step: Dict[str, Any]) -> Set[str]:
        """
        Parse a step definition to find all {{ step_id.key }} references.
        Returns a set of step_ids that this step depends on.
        """
        deps = set()
        
        # Recursively search parameters and conditions
        to_scan = [step.get('parameters', {}), step.get('conditions', {})]
        
        while to_scan:
            current = to_scan.pop()
            
            if isinstance(current, dict):
                for v in current.values():
                    to_scan.append(v)
            elif isinstance(current, list):
                for v in current:
                    to_scan.append(v)
            elif isinstance(current, str):
                # Search for {{ var }}
                matches = self.var_pattern.findall(current)
                for var_path in matches:
                    var_path = var_path.strip()
                    # Assumption: variables are formatted as step_id.key or just keys
                    # If it has a dot, the first part is likely a step_id
                    if '.' in var_path:
                        potential_step_id = var_path.split('.')[0]
                        # We don't validte if it's a real step here, just record the ref
                        deps.add(potential_step_id)
                        
        return deps
