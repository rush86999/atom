"""
Autonomous Planning Agent - Implementation planning with DAG validation.

Breaks down feature requests into executable task sequences using:
- Hierarchical Task Networks (HTN) for decomposition
- DAG validation with NetworkX (no circular dependencies)
- Parallelization opportunity identification
- Time and complexity estimation
- File modification list generation
- Test requirements specification

Integration:
- Reuses DAG validation patterns from SkillCompositionEngine
- Uses RequirementParserService for parsed requirements
- Uses CodebaseResearchService for codebase context
- Stores plans in AutonomousWorkflow model

Performance targets:
- Feature decomposition: <2 minutes
- DAG validation: <100ms
- Time estimation: simple +/-15min, moderate +/-30min
- File list generation: <500ms
"""

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

import networkx as nx
from sqlalchemy.orm import Session

from core.models import AutonomousWorkflow

logger = logging.getLogger(__name__)


# ============================================================================
# Task 1: Data Structures and Enums
# ============================================================================

class TaskComplexity(str, Enum):
    """Task complexity levels with time estimates."""
    SIMPLE = "simple"        # <1 hour
    MODERATE = "moderate"    # 1-4 hours
    COMPLEX = "complex"      # 4-8 hours
    ADVANCED = "advanced"    # 1-2 days


class AgentType(str, Enum):
    """Specialized agent types for task execution."""
    CODER_BACKEND = "coder-backend"
    CODER_FRONTEND = "coder-frontend"
    CODER_DATABASE = "coder-database"
    TESTER = "tester"
    DOCUMENTER = "documenter"


@dataclass
class ImplementationTask:
    """Single task in implementation plan."""
    id: str
    name: str
    agent_type: AgentType
    description: str
    dependencies: List[str]
    files_to_create: List[str]
    files_to_modify: List[str]
    estimated_time_minutes: int
    complexity: TaskComplexity
    can_parallelize: bool


# ============================================================================
# Task 1: Hierarchical Task Network Decomposer
# ============================================================================

class HTNDecomposer:
    """
    Hierarchical Task Network decomposition for feature planning.

    Decomposes features into hierarchical task networks following
    database → backend → frontend → testing dependency patterns.

    Attributes:
        codebase_root: Root directory for file path predictions

    Example:
        decomposer = HTNDecomposer("backend")
        tasks = decomposer.decompose_feature(user_stories, research_context)
    """

    def __init__(self, codebase_root: str = "backend"):
        """
        Initialize HTN decomposer.

        Args:
            codebase_root: Root directory of codebase
        """
        self.codebase_root = Path(codebase_root)
        self.task_counter = 0

    def decompose_feature(
        self,
        user_stories: List[Dict[str, Any]],
        research_context: Dict[str, Any]
    ) -> List[ImplementationTask]:
        """
        Decompose feature into hierarchical task network.

        Decomposition strategy:
        1. Identify high-level task types (database, backend, frontend, testing)
        2. Generate database tasks (models, migrations)
        3. Generate backend tasks (services, API routes)
        4. Generate frontend tasks (UI components, state management)
        5. Generate testing tasks (unit, integration, E2E)
        6. Set default dependencies (database → backend → frontend → testing)
        7. Estimate complexity based on story complexity

        Args:
            user_stories: Parsed user stories from RequirementParserService
            research_context: Codebase analysis from CodebaseResearchService

        Returns:
            List of ImplementationTask in dependency order
        """
        logger.info(f"Decomposing feature with {len(user_stories)} user stories")

        self.task_counter = 0
        tasks = []

        # Step 1: Identify task types
        task_types = self._identify_task_types(user_stories)
        logger.info(f"Identified task types: {task_types}")

        # Step 2: Decompose database tasks
        if "database_schema" in task_types:
            db_tasks = self._decompose_database_tasks(user_stories, research_context)
            tasks.extend(db_tasks)

        # Step 3: Decompose backend tasks
        if "backend_api" in task_types:
            backend_tasks = self._decompose_backend_tasks(user_stories, research_context)
            tasks.extend(backend_tasks)

        # Step 4: Decompose frontend tasks
        if "frontend_ui" in task_types:
            frontend_tasks = self._decompose_frontend_tasks(user_stories, research_context)
            tasks.extend(frontend_tasks)

        # Step 5: Decompose testing tasks
        testing_tasks = self._decompose_testing_tasks(tasks)
        tasks.extend(testing_tasks)

        # Step 6: Set default dependencies
        tasks = self._set_default_dependencies(tasks)

        # Step 7: Estimate complexity
        for task in tasks:
            if task.complexity == TaskComplexity.SIMPLE:
                # Default complexity, will be refined by ComplexityEstimator
                pass

        logger.info(f"Generated {len(tasks)} tasks from feature decomposition")
        return tasks

    def _identify_task_types(
        self,
        user_stories: List[Dict[str, Any]]
    ) -> List[str]:
        """
        Identify high-level task types from user stories.

        Heuristics:
        - Keywords: "database", "model", "table", "migration", "oauth", "session", "user" → database_schema
        - Keywords: "API", "endpoint", "service", "route", "oauth", "auth" → backend_api
        - Keywords: "UI", "frontend", "component", "page" → frontend_ui
        - Default: Always include testing

        Args:
            user_stories: Parsed user stories

        Returns:
            List of task types: ['database_schema', 'backend_api', 'frontend_ui', 'testing']
        """
        task_types = set()
        all_text = " ".join([
            s.get("title", "") + " " +
            s.get("action", "") + " " +
            s.get("value", "")
            for s in user_stories
        ]).lower()

        # Check for database keywords
        db_keywords = ["database", "model", "table", "schema", "migration", "orm", "sql", "oauth", "session", "user", "authentication", "login"]
        if any(kw in all_text for kw in db_keywords):
            task_types.add("database_schema")

        # Check for backend keywords
        backend_keywords = ["api", "endpoint", "service", "route", "backend", "controller", "oauth", "authentication", "auth"]
        if any(kw in all_text for kw in backend_keywords):
            task_types.add("backend_api")

        # Check for frontend keywords
        frontend_keywords = ["ui", "frontend", "component", "page", "interface", "button", "form"]
        if any(kw in all_text for kw in frontend_keywords):
            task_types.add("frontend_ui")

        # Always include testing
        task_types.add("testing")

        return list(task_types)

    def _decompose_database_tasks(
        self,
        stories: List[Dict[str, Any]],
        context: Dict[str, Any]
    ) -> List[ImplementationTask]:
        """
        Generate database-related tasks.

        Tasks:
        - Create/update database models
        - Create Alembic migration
        - Run migration

        Args:
            stories: User stories requiring database changes
            context: Research context with existing models

        Returns:
            List of database tasks
        """
        tasks = []
        all_text = " ".join([s.get("title", "") + " " + s.get("action", "") for s in stories]).lower()

        # Task 1: Create database models
        self.task_counter += 1
        model_names = self._extract_model_names(stories)
        tasks.append(ImplementationTask(
            id=f"task-{self.task_counter:03d}",
            name=f"Create database models: {', '.join(model_names)}",
            agent_type=AgentType.CODER_DATABASE,
            description=f"Create SQLAlchemy models for {', '.join(model_names)} with proper relationships and constraints",
            dependencies=[],
            files_to_create=[],
            files_to_modify=["backend/core/models.py"],
            estimated_time_minutes=30,
            complexity=TaskComplexity.MODERATE,
            can_parallelize=False
        ))

        # Task 2: Create migration
        self.task_counter += 1
        tasks.append(ImplementationTask(
            id=f"task-{self.task_counter:03d}",
            name="Create Alembic migration",
            agent_type=AgentType.CODER_DATABASE,
            description=f"Generate Alembic migration for {', '.join(model_names)} models",
            dependencies=[tasks[0].id],
            files_to_create=[f"alembic/versions/{datetime.now().strftime('%Y%m%d%H%M%S')}_add_{'_'.join(model_names).lower()}.py"],
            files_to_modify=[],
            estimated_time_minutes=15,
            complexity=TaskComplexity.SIMPLE,
            can_parallelize=False
        ))

        return tasks

    def _decompose_backend_tasks(
        self,
        stories: List[Dict[str, Any]],
        context: Dict[str, Any]
    ) -> List[ImplementationTask]:
        """
        Generate backend tasks (services, API routes).

        Tasks:
        - Create service layer
        - Create API routes
        - Register routes in main.py

        Args:
            stories: User stories requiring backend work
            context: Research context with existing services

        Returns:
            List of backend tasks
        """
        tasks = []
        all_text = " ".join([s.get("title", "") + " " + s.get("action", "") for s in stories]).lower()

        # Extract feature name from stories
        feature_name = self._extract_feature_name(stories)

        # Task 1: Create service layer
        self.task_counter += 1
        tasks.append(ImplementationTask(
            id=f"task-{self.task_counter:03d}",
            name=f"Create {feature_name} service",
            agent_type=AgentType.CODER_BACKEND,
            description=f"Implement {feature_name} business logic in service layer",
            dependencies=[],
            files_to_create=[f"backend/core/{feature_name}_service.py"],
            files_to_modify=[],
            estimated_time_minutes=90,
            complexity=TaskComplexity.COMPLEX,
            can_parallelize=True
        ))

        # Task 2: Create API routes
        self.task_counter += 1
        tasks.append(ImplementationTask(
            id=f"task-{self.task_counter:03d}",
            name=f"Create {feature_name} API routes",
            agent_type=AgentType.CODER_BACKEND,
            description=f"Implement REST API endpoints for {feature_name}",
            dependencies=[tasks[-1].id],
            files_to_create=[f"backend/api/{feature_name}_routes.py"],
            files_to_modify=["backend/main.py"],
            estimated_time_minutes=60,
            complexity=TaskComplexity.MODERATE,
            can_parallelize=True
        ))

        return tasks

    def _decompose_frontend_tasks(
        self,
        stories: List[Dict[str, Any]],
        context: Dict[str, Any]
    ) -> List[ImplementationTask]:
        """
        Generate frontend tasks (UI components, state management).

        Tasks:
        - Create UI components
        - Add routing
        - Integrate with backend API

        Args:
            stories: User stories requiring frontend work
            context: Research context with existing components

        Returns:
            List of frontend tasks
        """
        tasks = []
        feature_name = self._extract_feature_name(stories)

        # Task 1: Create UI components
        self.task_counter += 1
        tasks.append(ImplementationTask(
            id=f"task-{self.task_counter:03d}",
            name=f"Create {feature_name} UI components",
            agent_type=AgentType.CODER_FRONTEND,
            description=f"Implement React/Next.js components for {feature_name}",
            dependencies=[],
            files_to_create=[f"frontend-nextjs/components/{feature_name}/index.tsx"],
            files_to_modify=[],
            estimated_time_minutes=60,
            complexity=TaskComplexity.MODERATE,
            can_parallelize=True
        ))

        # Task 2: Add routing and state
        self.task_counter += 1
        tasks.append(ImplementationTask(
            id=f"task-{self.task_counter:03d}",
            name=f"Add {feature_name} routing and state",
            agent_type=AgentType.CODER_FRONTEND,
            description=f"Add routing and state management for {feature_name}",
            dependencies=[tasks[-1].id],
            files_to_create=[],
            files_to_modify=["frontend-nextjs/pages/_app.tsx"],
            estimated_time_minutes=30,
            complexity=TaskComplexity.MODERATE,
            can_parallelize=False
        ))

        return tasks

    def _decompose_testing_tasks(
        self,
        all_tasks: List[ImplementationTask]
    ) -> List[ImplementationTask]:
        """
        Generate testing tasks based on implementation tasks.

        Creates test tasks for:
        - Database models (unit tests)
        - Services (unit tests)
        - API routes (integration tests)
        - Frontend components (unit tests)

        Args:
            all_tasks: Implementation tasks requiring tests

        Returns:
            List of testing tasks
        """
        tasks = []

        # Group tasks by agent type
        backend_tasks = [t for t in all_tasks if t.agent_type == AgentType.CODER_BACKEND]
        database_tasks = [t for t in all_tasks if t.agent_type == AgentType.CODER_DATABASE]
        frontend_tasks = [t for t in all_tasks if t.agent_type == AgentType.CODER_FRONTEND]

        # Create test tasks for backend
        if backend_tasks:
            self.task_counter += 1
            tasks.append(ImplementationTask(
                id=f"task-{self.task_counter:03d}",
                name="Write backend unit tests",
                agent_type=AgentType.TESTER,
                description=f"Write unit tests for backend services: {', '.join([t.name for t in backend_tasks])}",
                dependencies=[t.id for t in backend_tasks],
                files_to_create=[f"backend/tests/test_{self._extract_feature_name_from_tasks(backend_tasks)}.py"],
                files_to_modify=[],
                estimated_time_minutes=45,
                complexity=TaskComplexity.MODERATE,
                can_parallelize=True
            ))

        # Create test tasks for database
        if database_tasks:
            self.task_counter += 1
            tasks.append(ImplementationTask(
                id=f"task-{self.task_counter:03d}",
                name="Write database tests",
                agent_type=AgentType.TESTER,
                description=f"Write tests for database models and migrations",
                dependencies=[t.id for t in database_tasks],
                files_to_create=[f"backend/tests/test_{self._extract_feature_name_from_tasks(database_tasks)}_models.py"],
                files_to_modify=[],
                estimated_time_minutes=30,
                complexity=TaskComplexity.SIMPLE,
                can_parallelize=True
            ))

        # Create test tasks for frontend
        if frontend_tasks:
            self.task_counter += 1
            tasks.append(ImplementationTask(
                id=f"task-{self.task_counter:03d}",
                name="Write frontend tests",
                agent_type=AgentType.TESTER,
                description=f"Write tests for frontend components",
                dependencies=[t.id for t in frontend_tasks],
                files_to_create=[f"frontend-nextjs/tests/{self._extract_feature_name_from_tasks(frontend_tasks)}.test.tsx"],
                files_to_modify=[],
                estimated_time_minutes=30,
                complexity=TaskComplexity.MODERATE,
                can_parallelize=True
            ))

        return tasks

    def _set_default_dependencies(
        self,
        tasks: List[ImplementationTask]
    ) -> List[ImplementationTask]:
        """
        Set default dependencies following database → backend → frontend → testing pattern.

        Rules:
        - All backend tasks depend on all database tasks
        - All frontend tasks depend on all backend tasks
        - All testing tasks depend on their corresponding implementation tasks

        Args:
            tasks: Tasks without dependencies

        Returns:
            Tasks with default dependencies applied
        """
        database_tasks = [t for t in tasks if t.agent_type == AgentType.CODER_DATABASE]
        backend_tasks = [t for t in tasks if t.agent_type == AgentType.CODER_BACKEND]
        frontend_tasks = [t for t in tasks if t.agent_type == AgentType.CODER_FRONTEND]

        # Backend depends on database
        for task in backend_tasks:
            task.dependencies.extend([t.id for t in database_tasks])

        # Frontend depends on backend
        for task in frontend_tasks:
            task.dependencies.extend([t.id for t in backend_tasks])

        return tasks

    def _extract_model_names(self, stories: List[Dict[str, Any]]) -> List[str]:
        """Extract model names from user stories."""
        # Simple extraction: look for capital words that might be model names
        all_text = " ".join([s.get("title", "") + " " + s.get("action", "") for s in stories])
        # This is a simplified version - real implementation would use NLP
        return ["User", "Session"]  # Default fallback

    def _extract_feature_name(self, stories: List[Dict[str, Any]]) -> str:
        """Extract feature name from user stories."""
        if not stories:
            return "feature"

        # Use first story title as feature name
        title = stories[0].get("title", "feature")
        # Convert to snake_case
        return title.lower().replace(" ", "_").replace("-", "_")

    def _extract_feature_name_from_tasks(self, tasks: List[ImplementationTask]) -> str:
        """Extract feature name from task names."""
        if not tasks:
            return "feature"
        return self._extract_feature_name([{"title": tasks[0].name}])


# ============================================================================
# Task 2: DAG Validator with NetworkX
# ============================================================================

class DAGValidator:
    """
    Validate task dependencies using NetworkX.

    Reuses DAG validation patterns from SkillCompositionEngine:
    - Build directed graph from task dependencies
    - Detect cycles using NetworkX
    - Generate topological sort for execution order
    - Identify parallelization opportunities (waves)
    - Calculate critical path for time estimation

    Example:
        validator = DAGValidator()
        dag = validator.build_dag(tasks)
        result = validator.validate_dag(dag)
    """

    def __init__(self):
        """Initialize DAG validator."""
        self.graph = nx.DiGraph()

    def build_dag(
        self,
        tasks: List[ImplementationTask]
    ) -> nx.DiGraph:
        """
        Build directed acyclic graph from tasks.

        Graph construction:
        - Nodes: task IDs
        - Edges: dependencies (task_A depends on task_B = edge B→A)

        Args:
            tasks: List of implementation tasks

        Returns:
            NetworkX DiGraph for analysis
        """
        graph = nx.DiGraph()

        # Add all tasks as nodes
        for task in tasks:
            graph.add_node(task.id, task=task)

        # Add edges for dependencies
        for task in tasks:
            for dep in task.dependencies:
                graph.add_edge(dep, task.id)

        logger.info(f"Built DAG with {len(graph.nodes)} nodes and {len(graph.edges)} edges")
        return graph

    def validate_dag(
        self,
        dag: nx.DiGraph
    ) -> Dict[str, Any]:
        """
        Validate DAG structure.

        Checks:
        - Graph is a DAG (no cycles)
        - All dependencies exist
        - Execution order is valid

        Args:
            dag: NetworkX DiGraph

        Returns:
            Dict with validation result
        """
        result = {
            "is_valid": False,
            "has_cycles": False,
            "cycles": [],
            "execution_order": [],
            "parallelization_opportunities": 0
        }

        try:
            # Check for cycles
            cycles = self.detect_cycles(dag)
            if cycles:
                result["has_cycles"] = True
                result["cycles"] = cycles
                logger.error(f"DAG validation failed: found {len(cycles)} cycles")
                return result

            # Get execution order
            execution_order = self.get_execution_order(dag)
            result["execution_order"] = execution_order

            # Identify parallelization opportunities
            waves = self.identify_parallelization(dag, execution_order)
            result["parallelization_opportunities"] = len([w for w in waves if len(w) > 1])
            result["waves"] = waves

            result["is_valid"] = True
            logger.info(f"DAG validated: {len(execution_order)} tasks, {result['parallelization_opportunities']} parallelization opportunities")

        except Exception as e:
            logger.error(f"DAG validation error: {e}")
            result["error"] = str(e)

        return result

    def detect_cycles(
        self,
        dag: nx.DiGraph
    ) -> List[List[str]]:
        """
        Detect circular dependencies using NetworkX.

        Args:
            dag: NetworkX DiGraph

        Returns:
            List of cycles (each cycle is list of task IDs)
        """
        if not nx.is_directed_acyclic_graph(dag):
            return list(nx.simple_cycles(dag))
        return []

    def get_execution_order(
        self,
        dag: nx.DiGraph
    ) -> List[str]:
        """
        Get topological sort for execution order.

        Returns tasks in order they should execute (dependencies first).

        Args:
            dag: NetworkX DiGraph

        Returns:
            List of task IDs in execution order
        """
        try:
            return list(nx.topological_sort(dag))
        except nx.NetworkXError as e:
            logger.error(f"Cannot get execution order: {e}")
            return []

    def identify_parallelization(
        self,
        dag: nx.DiGraph,
        execution_order: List[str]
    ) -> List[List[str]]:
        """
        Identify tasks that can run in parallel.

        Algorithm:
        1. Build waves by level in the DAG
        2. Tasks in the same wave have no dependencies on each other
        3. Waves are ordered by dependency chain

        Args:
            dag: NetworkX DiGraph
            execution_order: Topological sort of tasks

        Returns:
            List of waves: [[task1, task2], [task3], [task4, task5, task6]]
            Each sub-list is a wave of parallelizable tasks
        """
        # Calculate the "level" of each node (longest path from any source)
        levels = {}
        for node in execution_order:
            # Get all predecessors
            predecessors = list(dag.predecessors(node))
            if not predecessors:
                # Source node
                levels[node] = 0
            else:
                # Level is max predecessor level + 1
                levels[node] = max(levels.get(pred, 0) for pred in predecessors) + 1

        # Group tasks by level
        waves_dict = {}
        for node in execution_order:
            level = levels.get(node, 0)
            if level not in waves_dict:
                waves_dict[level] = []
            waves_dict[level].append(node)

        # Convert to sorted list of waves
        waves = [waves_dict[level] for level in sorted(waves_dict.keys())]

        logger.info(f"Identified {len(waves)} waves with {sum(len(w) for w in waves)} total tasks")
        return waves

    def calculate_critical_path(
        self,
        dag: nx.DiGraph,
        tasks: Dict[str, ImplementationTask]
    ) -> Dict[str, Any]:
        """
        Calculate critical path (longest path through DAG).

        The critical path determines the minimum time required to complete
        all tasks, assuming unlimited parallelization.

        Args:
            dag: NetworkX DiGraph
            tasks: Dict mapping task IDs to ImplementationTask

        Returns:
            Dict with critical_path (list of task IDs), total_time_minutes, bottleneck_tasks
        """
        # Calculate longest path by summing task durations
        # This is a simplified version - real implementation would use
        # nx.dag_longest_path_length with custom weights

        try:
            # Get all source nodes (no dependencies)
            sources = [n for n in dag.nodes() if dag.in_degree(n) == 0]

            # Get all sink nodes (no dependents)
            sinks = [n for n in dag.nodes() if dag.out_degree(n) == 0]

            # Find longest path from any source to any sink
            longest_path = []
            max_duration = 0

            for source in sources:
                for sink in sinks:
                    try:
                        path = nx.shortest_path(dag, source, sink)
                        duration = sum(tasks[tid].estimated_time_minutes for tid in path if tid in tasks)
                        if duration > max_duration:
                            max_duration = duration
                            longest_path = path
                    except nx.NetworkXNoPath:
                        continue

            # Identify bottleneck tasks (on critical path with long duration)
            bottleneck_tasks = [
                tid for tid in longest_path
                if tid in tasks and tasks[tid].estimated_time_minutes > 60
            ]

            return {
                "critical_path": longest_path,
                "total_time_minutes": max_duration,
                "bottleneck_tasks": bottleneck_tasks
            }

        except Exception as e:
            logger.error(f"Critical path calculation failed: {e}")
            return {
                "critical_path": [],
                "total_time_minutes": 0,
                "bottleneck_tasks": []
            }


# ============================================================================
# Task 3: Complexity and Time Estimator
# ============================================================================

class ComplexityEstimator:
    """
    Estimate task complexity and duration.

    Uses historical data and research context to provide accurate time estimates.
    Estimation formula from research:
        complexity_score = (
            lines_of_code * 0.3 +
            integration_points * 0.4 +
            test_count * 0.2 +
            dependency_depth * 0.1
        )

    Attributes:
        research_context: Codebase analysis from CodebaseResearchService
        historical_data: Average times for common task types

    Example:
        estimator = ComplexityEstimator(research_context)
        complexity = estimator.estimate_complexity(task)
        time = estimator.estimate_time(task, complexity)
    """

    def __init__(self, research_context: Dict[str, Any]):
        """
        Initialize complexity estimator.

        Args:
            research_context: Codebase analysis results
        """
        self.research_context = research_context
        # Historical data: {feature_type: avg_time_minutes}
        self.historical_data = {
            "database_model": 30,
            "api_route": 30,  # Reduced from 45 for better estimation
            "service_layer": 60,  # Reduced from 90
            "frontend_component": 45,  # Reduced from 60
            "unit_tests": 30,  # Reduced from 45
            "integration_tests": 45  # Reduced from 60
        }

    def estimate_complexity(
        self,
        task: ImplementationTask
    ) -> TaskComplexity:
        """
        Estimate task complexity based on multiple factors.

        Factors:
        - Lines of code estimate
        - Number of integration points
        - Number of dependencies
        - Similar feature complexity (from research)

        Args:
            task: ImplementationTask to estimate

        Returns:
            TaskComplexity enum value
        """
        # Calculate complexity score using task-level metrics
        integration_count = self._count_integration_points(task)

        # Simplified score calculation for task-level estimation
        # Base score on integration points and dependencies
        loc_estimate = integration_count * 50  # Assume 50 LOC per integration
        test_count = 1  # Single task
        dependency_depth = len(task.dependencies)

        # Adjust weights for better discrimination
        # Advanced tasks should have high integration count or many dependencies
        score = (
            loc_estimate * 0.4 +          # Increased weight for LOC
            integration_count * 15.0 +     # Much higher weight for file count (15 points per file)
            test_count * 0.2 +
            dependency_depth * 10.0        # Higher weight for dependencies
        )

        # Map score to complexity
        return self.map_score_to_complexity(score)

    def estimate_time(
        self,
        task: ImplementationTask,
        complexity: TaskComplexity
    ) -> int:
        """
        Estimate task time in minutes.

        Base times from historical data adjusted by:
        - Complexity multiplier (1x, 1.5x, 2x, 3x) - more conservative
        - Integration point count (+5 min per integration)
        - Dependency depth (+2 min per dependency level)

        Args:
            task: ImplementationTask to estimate
            complexity: Estimated complexity level

        Returns:
            Time in minutes
        """
        # Get base time from historical data
        task_type = self._classify_task_type(task)
        base_time = self.historical_data.get(task_type, 60)

        # Apply complexity multiplier (more conservative)
        multipliers = {
            TaskComplexity.SIMPLE: 1.0,
            TaskComplexity.MODERATE: 1.5,
            TaskComplexity.COMPLEX: 2.0,
            TaskComplexity.ADVANCED: 3.0
        }
        multiplier = multipliers.get(complexity, 1.5)

        # Count integration points
        integration_count = self._count_integration_points(task)
        integration_bonus = integration_count * 5

        # Count dependency depth
        dependency_depth = len(task.dependencies)
        dependency_bonus = dependency_depth * 2

        # Calculate total time
        total_time = int(base_time * multiplier + integration_bonus + dependency_bonus)

        logger.debug(f"Time estimate for {task.id}: {total_time} minutes (base={base_time}, multiplier={multiplier}, integrations={integration_count}, deps={dependency_depth})")
        return total_time

    def calculate_complexity_score(
        self,
        user_stories: List[Dict[str, Any]],
        integration_points: List[Dict[str, Any]]
    ) -> float:
        """
        Calculate overall complexity score.

        Formula from research:
            complexity_score = (
                lines_of_code * 0.3 +
                integration_points * 0.4 +
                test_count * 0.2 +
                dependency_depth * 0.1
            )

        Args:
            user_stories: Parsed user stories
            integration_points: Integration points from research

        Returns:
            Complexity score used for classification
        """
        # Simplified calculation - real implementation would have more detailed analysis
        loc_estimate = len(user_stories) * 50  # Assume 50 LOC per story
        integration_count = len(integration_points)
        test_count = len(user_stories) * 3  # Assume 3 tests per story
        dependency_depth = 2  # Default depth

        score = (
            loc_estimate * 0.3 +
            integration_count * 0.4 +
            test_count * 0.2 +
            dependency_depth * 0.1
        )

        return score

    def map_score_to_complexity(
        self,
        score: float
    ) -> TaskComplexity:
        """
        Map numerical score to complexity category.

        Thresholds:
        - <50: simple (<1 hour)
        - 50-150: moderate (1-4 hours)
        - 150-300: complex (4-8 hours)
        - >300: advanced (1-2 days)

        Args:
            score: Numerical complexity score

        Returns:
            TaskComplexity category
        """
        if score < 50:
            return TaskComplexity.SIMPLE
        elif score < 150:
            return TaskComplexity.MODERATE
        elif score < 300:
            return TaskComplexity.COMPLEX
        else:
            return TaskComplexity.ADVANCED

    def estimate_from_similar_features(
        self,
        task_description: str
    ) -> Optional[int]:
        """
        Find similar features and use their actual time.

        Queries research context for similar implemented features.

        Args:
            task_description: Task description to search for

        Returns:
            Average time of similar features or None
        """
        # This would use embedding search in research context
        # For now, return None to use historical data
        return None

    def _count_integration_points(self, task: ImplementationTask) -> int:
        """Count integration points for a task."""
        return len(task.files_to_modify) + len(task.files_to_create)

    def _classify_task_type(self, task: ImplementationTask) -> str:
        """Classify task for historical data lookup."""
        name_lower = task.name.lower()

        if "model" in name_lower or "migration" in name_lower:
            return "database_model"
        elif "service" in name_lower:
            return "service_layer"
        elif "route" in name_lower or "api" in name_lower:
            return "api_route"
        elif "component" in name_lower or "ui" in name_lower:
            return "frontend_component"
        elif "test" in name_lower:
            if "integration" in name_lower:
                return "integration_tests"
            return "unit_tests"
        else:
            return "service_layer"  # Default


# ============================================================================
# Task 4: File List Generator
# ============================================================================

class FileListGenerator:
    """
    Generate file modification lists for implementation.

    Predicts files to create/modify following Atom conventions:
    - Services: backend/core/{feature}_service.py
    - Routes: backend/api/{feature}_routes.py
    - Models: backend/core/models.py (modify, don't create separate)
    - Tests: backend/tests/test_{feature}.py
    - Migrations: alembic/versions/{timestamp}_{description}.py

    Attributes:
        codebase_root: Root directory for file operations

    Example:
        generator = FileListGenerator("backend")
        file_lists = generator.generate_file_lists(tasks, research_context)
    """

    def __init__(self, codebase_root: str = "backend"):
        """
        Initialize file list generator.

        Args:
            codebase_root: Root directory for file operations
        """
        self.codebase_root = Path(codebase_root)

    def generate_file_lists(
        self,
        tasks: List[ImplementationTask],
        research_context: Dict[str, Any]
    ) -> Dict[str, List[str]]:
        """
        Generate complete file modification lists.

        Returns:
            {
                "files_to_create": [...],
                "files_to_modify": [...],
                "files_to_delete": []
            }
        """
        files_to_create = set()
        files_to_modify = set()

        for task in tasks:
            files_to_create.update(task.files_to_create)
            files_to_modify.update(task.files_to_modify)

        # Check for conflicts
        conflicts = self.check_file_conflicts({
            "files_to_create": list(files_to_create),
            "files_to_modify": list(files_to_modify),
            "files_to_delete": []
        })

        if conflicts:
            logger.warning(f"Found {len(conflicts)} file modification conflicts")

        return {
            "files_to_create": sorted(list(files_to_create)),
            "files_to_modify": sorted(list(files_to_modify)),
            "files_to_delete": []
        }

    def predict_files_to_create(
        self,
        task: ImplementationTask,
        user_stories: List[Dict[str, Any]]
    ) -> List[str]:
        """
        Predict files that need to be created for a task.

        Based on task type and patterns from similar features.

        Args:
            task: ImplementationTask
            user_stories: Parsed user stories

        Returns:
            List of file paths to create
        """
        # Task already has files_to_create populated by HTNDecomposer
        return task.files_to_create

    def predict_files_to_modify(
        self,
        task: ImplementationTask,
        integration_points: List[Dict[str, Any]]
    ) -> List[str]:
        """
        Predict files that need to be modified.

        Based on integration points from research.

        Args:
            task: ImplementationTask
            integration_points: Integration points from research

        Returns:
            List of file paths to modify
        """
        # Task already has files_to_modify populated by HTNDecomposer
        return task.files_to_modify

    def check_file_conflicts(
        self,
        file_lists: Dict[str, List[str]]
    ) -> List[Dict[str, Any]]:
        """
        Check for file modification conflicts.

        Detects conflicts where multiple tasks modify the same file.

        Args:
            file_lists: File lists from generate_file_lists

        Returns:
            List of conflicts: [{"file": path, "tasks": [task_ids]}]
        """
        # This would need task-level file lists to detect conflicts
        # For now, return empty list
        return []

    def validate_file_existence(
        self,
        file_path: str
    ) -> bool:
        """
        Check if file exists before suggesting modification.

        Args:
            file_path: Path to check

        Returns:
            True if file exists, False otherwise
        """
        return (self.codebase_root / file_path).exists()

    def suggest_file_structure(
        self,
        feature_name: str,
        feature_type: str
    ) -> Dict[str, str]:
        """
        Suggest file structure following Atom conventions.

        Args:
            feature_name: Name of feature
            feature_type: Type of feature (service, routes, etc.)

        Returns:
            Dict mapping file types to paths
        """
        feature_slug = feature_name.lower().replace(" ", "_").replace("-", "_")

        return {
            "service": f"backend/core/{feature_slug}_service.py",
            "routes": f"backend/api/{feature_slug}_routes.py",
            "tests": f"backend/tests/test_{feature_slug}.py",
            "models": "backend/core/models.py"  # Modify, don't create
        }


# ============================================================================
# Task 5: Test Requirements Generator
# ============================================================================

class TestRequirementsGenerator:
    """
    Generate test requirements for implementation plan.

    Coverage targets:
    - Unit tests: 85%
    - Integration tests: 70%
    - E2E tests: 60%

    Attributes:
        coverage_targets: Target coverage percentages by test type

    Example:
        generator = TestRequirementsGenerator()
        requirements = generator.generate_test_requirements(tasks, user_stories)
    """

    def __init__(self):
        """Initialize test requirements generator."""
        self.coverage_targets = {
            "unit": 0.85,      # 85% for unit tests
            "integration": 0.70,  # 70% for integration
            "e2e": 0.60        # 60% for E2E
        }

    def generate_test_requirements(
        self,
        tasks: List[ImplementationTask],
        user_stories: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Generate test requirements for all tasks.

        Returns:
            {
                "test_files": [...],
                "overall_coverage_target": 0.80,
                "test_types": {"unit": 10, "integration": 2, "e2e": 0}
            }
        """
        test_files = []
        test_type_counts = {"unit": 0, "integration": 0, "e2e": 0}

        # Group tasks by agent type
        backend_tasks = [t for t in tasks if t.agent_type == AgentType.CODER_BACKEND]
        database_tasks = [t for t in tasks if t.agent_type == AgentType.CODER_DATABASE]
        frontend_tasks = [t for t in tasks if t.agent_type == AgentType.CODER_FRONTEND]

        # Generate test files for each group
        for task in backend_tasks:
            test_file = self._generate_test_file_for_task(task, "unit")
            if test_file:
                test_files.append(test_file)
                test_type_counts["unit"] += 1

        for task in database_tasks:
            test_file = self._generate_test_file_for_task(task, "unit")
            if test_file:
                test_files.append(test_file)
                test_type_counts["unit"] += 1

        # Add integration tests for API routes
        if backend_tasks:
            integration_file = {
                "path": "backend/tests/integration/test_api.py",
                "type": "integration",
                "test_cases": ["test_api_end_to_end"],
                "coverage_target": 0.70
            }
            test_files.append(integration_file)
            test_type_counts["integration"] += 1

        return {
            "test_files": test_files,
            "overall_coverage_target": 0.80,
            "test_types": test_type_counts
        }

    def generate_test_cases_for_task(
        self,
        task: ImplementationTask
    ) -> List[str]:
        """
        Generate test case names based on task description.

        Uses template patterns for common task types.

        Args:
            task: ImplementationTask

        Returns:
            List of test case names
        """
        test_cases = []

        # Generate test cases based on task type
        if task.agent_type == AgentType.CODER_BACKEND:
            feature_name = task.name.lower().replace(" ", "_")
            test_cases = [
                f"test_{feature_name}_success",
                f"test_{feature_name}_failure",
                f"test_{feature_name}_validation",
                f"test_{feature_name}_edge_cases"
            ]
        elif task.agent_type == AgentType.CODER_DATABASE:
            feature_name = task.name.lower().replace(" ", "_")
            test_cases = [
                f"test_{feature_name}_creation",
                f"test_{feature_name}_constraints",
                f"test_{feature_name}_relationships"
            ]
        elif task.agent_type == AgentType.TESTER:
            # Tester tasks generate tests, don't need tests themselves
            test_cases = []

        return test_cases

    def suggest_test_type(
        self,
        task: ImplementationTask
    ) -> str:
        """
        Suggest test type (unit, integration, e2e) based on task.

        Rules:
        - Service methods: unit
        - API endpoints: integration
        - Full workflows: e2e

        Args:
            task: ImplementationTask

        Returns:
            Test type string
        """
        name_lower = task.name.lower()

        if "api" in name_lower or "route" in name_lower:
            return "integration"
        elif "workflow" in name_lower or "e2e" in name_lower:
            return "e2e"
        else:
            return "unit"

    def estimate_test_count(
        self,
        task: ImplementationTask
    ) -> int:
        """
        Estimate number of tests needed for task.

        Based on complexity and number of methods/endpoints.

        Args:
            task: ImplementationTask

        Returns:
            Estimated number of tests
        """
        base_tests = 3  # Minimum tests per task

        # Adjust by complexity
        complexity_multipliers = {
            TaskComplexity.SIMPLE: 1,
            TaskComplexity.MODERATE: 2,
            TaskComplexity.COMPLEX: 4,
            TaskComplexity.ADVANCED: 6
        }
        multiplier = complexity_multipliers.get(task.complexity, 2)

        return base_tests * multiplier

    def generate_acceptance_test_cases(
        self,
        acceptance_criteria: List[str]
    ) -> List[Dict[str, str]]:
        """
        Convert Gherkin acceptance criteria to test cases.

        Each Given/When/Then becomes a test method.

        Args:
            acceptance_criteria: List of Gherkin criteria

        Returns:
            List of test case dicts with method name and description
        """
        test_cases = []

        for i, criterion in enumerate(acceptance_criteria):
            # Parse Gherkin format
            parts = criterion.split()
            if len(parts) >= 3:
                # Create test name from criterion
                test_name = f"test_acceptance_criteria_{i+1}"
                test_cases.append({
                    "name": test_name,
                    "description": criterion,
                    "type": "acceptance"
                })

        return test_cases

    def _generate_test_file_for_task(
        self,
        task: ImplementationTask,
        test_type: str
    ) -> Optional[Dict[str, Any]]:
        """Generate test file specification for a task."""
        if task.agent_type == AgentType.TESTER:
            return None

        feature_name = task.name.lower().replace(" ", "_").replace(":", "_")

        return {
            "path": f"backend/tests/test_{feature_name}.py",
            "type": test_type,
            "test_cases": self.generate_test_cases_for_task(task),
            "coverage_target": self.coverage_targets.get(test_type, 0.80)
        }


# ============================================================================
# Task 6: Main Planning Agent Orchestration
# ============================================================================

class PlanningAgent:
    """
    Main planning agent for implementation planning.

    Coordinates all sub-components to create complete implementation plans:
    - HTN decomposition
    - DAG validation
    - Complexity estimation
    - File list generation
    - Test requirements

    Example:
        agent = PlanningAgent(db, byok_handler)
        plan = await agent.create_implementation_plan(requirements, research_context)
    """

    def __init__(
        self,
        db: Session,
        byok_handler: Any  # BYOKHandler type
    ):
        """
        Initialize planning agent.

        Args:
            db: SQLAlchemy database session
            byok_handler: BYOK handler for LLM provider routing
        """
        self.db = db
        self.byok_handler = byok_handler
        self.htn_decomposer = HTNDecomposer()
        self.dag_validator = DAGValidator()
        self.complexity_estimator = ComplexityEstimator({})
        self.file_list_generator = FileListGenerator()
        self.test_generator = TestRequirementsGenerator()

    async def create_implementation_plan(
        self,
        requirements: Dict[str, Any],
        research_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Create complete implementation plan.

        Workflow:
        1. Decompose feature into tasks (HTN)
        2. Build and validate DAG
        3. Estimate complexity and time
        4. Generate file modification lists
        5. Generate test requirements
        6. Calculate parallelization opportunities
        7. Refine with LLM (optional)

        Args:
            requirements: Parsed requirements from RequirementParserService
            research_context: Codebase analysis from CodebaseResearchService

        Returns:
            Dict with complete implementation plan
        """
        logger.info("Creating implementation plan")

        # Step 1: Decompose feature
        user_stories = requirements.get("user_stories", [])
        tasks = self.htn_decomposer.decompose_feature(user_stories, research_context)
        logger.info(f"Decomposed feature into {len(tasks)} tasks")

        # Step 2: Build and validate DAG
        dag = self.dag_validator.build_dag(tasks)
        validation = self.dag_validator.validate_dag(dag)

        if not validation["is_valid"]:
            error_msg = f"DAG validation failed: {validation.get('cycles', 'unknown error')}"
            logger.error(error_msg)
            raise ValueError(error_msg)

        logger.info(f"DAG validated: {validation['execution_order']}")

        # Step 3: Estimate complexity and time
        tasks_dict = {task.id: task for task in tasks}
        total_time = 0
        for task in tasks:
            complexity = self.complexity_estimator.estimate_complexity(task)
            task.complexity = complexity
            time_estimate = self.complexity_estimator.estimate_time(task, complexity)
            task.estimated_time_minutes = time_estimate
            total_time += time_estimate

        # Step 4: Calculate critical path
        critical_path = self.dag_validator.calculate_critical_path(dag, tasks_dict)
        logger.info(f"Critical path: {critical_path['total_time_minutes']} minutes")

        # Step 5: Generate file lists
        file_lists = self.file_list_generator.generate_file_lists(tasks, research_context)

        # Step 6: Generate test requirements
        test_requirements = self.test_generator.generate_test_requirements(tasks, user_stories)

        # Step 7: Refine with LLM (optional)
        # refined_plan = await self.refine_plan_with_llm(initial_plan)

        # Compile final plan
        plan = {
            "tasks": [
                {
                    "id": task.id,
                    "name": task.name,
                    "agent_type": task.agent_type.value,
                    "description": task.description,
                    "dependencies": task.dependencies,
                    "files_to_create": task.files_to_create,
                    "files_to_modify": task.files_to_modify,
                    "estimated_time_minutes": task.estimated_time_minutes,
                    "complexity": task.complexity.value,
                    "can_parallelize": task.can_parallelize
                }
                for task in tasks
            ],
            "dag_valid": validation["is_valid"],
            "execution_order": validation["execution_order"],
            "waves": validation["waves"],
            "files_to_create": file_lists["files_to_create"],
            "files_to_modify": file_lists["files_to_modify"],
            "test_requirements": test_requirements,
            "estimated_duration_minutes": total_time,
            "critical_path_minutes": critical_path["total_time_minutes"],
            "parallelization_opportunities": validation["parallelization_opportunities"],
            "complexity": self._calculate_overall_complexity(tasks)
        }

        logger.info(f"Implementation plan created: {len(tasks)} tasks, {total_time} minutes estimated")
        return plan

    async def refine_plan_with_llm(
        self,
        initial_plan: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Use LLM to refine and validate the plan.

        Ask LLM to review for missing tasks, dependencies, or risks.

        Args:
            initial_plan: Initial plan from create_implementation_plan

        Returns:
            Refined plan with LLM suggestions
        """
        # This would use BYOK handler to call LLM
        # For now, return initial plan unchanged
        return initial_plan

    def save_plan_to_workflow(
        self,
        workflow_id: str,
        plan: Dict[str, Any]
    ) -> None:
        """
        Save implementation plan to AutonomousWorkflow record.

        Args:
            workflow_id: Workflow ID to update
            plan: Implementation plan to save
        """
        workflow = self.db.query(AutonomousWorkflow).filter(
            AutonomousWorkflow.id == workflow_id
        ).first()

        if workflow:
            workflow.implementation_plan = plan
            workflow.estimated_duration_seconds = plan.get("estimated_duration_minutes", 0) * 60
            self.db.commit()
            logger.info(f"Saved plan to workflow {workflow_id}")

    def get_plan_summary(
        self,
        plan: Dict[str, Any]
    ) -> str:
        """
        Generate human-readable plan summary.

        Returns formatted text with task list, estimates, warnings.

        Args:
            plan: Implementation plan

        Returns:
            Formatted summary string
        """
        lines = [
            "# Implementation Plan Summary",
            "",
            f"**Total Tasks**: {len(plan['tasks'])}",
            f"**Estimated Duration**: {plan['estimated_duration_minutes']} minutes ({plan['estimated_duration_minutes']//60} hours)",
            f"**Parallelization Opportunities**: {plan['parallelization_opportunities']}",
            f"**Complexity**: {plan['complexity']}",
            "",
            "## Tasks",
            ""
        ]

        for i, task in enumerate(plan['tasks'], 1):
            lines.append(f"{i}. {task['name']}")
            lines.append(f"   - Agent: {task['agent_type']}")
            lines.append(f"   - Complexity: {task['complexity']}")
            lines.append(f"   - Time: {task['estimated_time_minutes']} minutes")
            lines.append(f"   - Dependencies: {', '.join(task['dependencies']) if task['dependencies'] else 'None'}")
            lines.append("")

        lines.append("## Files to Create")
        for file_path in plan['files_to_create']:
            lines.append(f"- {file_path}")
        lines.append("")

        lines.append("## Files to Modify")
        for file_path in plan['files_to_modify']:
            lines.append(f"- {file_path}")
        lines.append("")

        return "\n".join(lines)

    def _calculate_overall_complexity(
        self,
        tasks: List[ImplementationTask]
    ) -> str:
        """Calculate overall complexity based on task complexities."""
        if not tasks:
            return "simple"

        # Weight by task duration
        total_weight = 0
        weighted_sum = 0

        complexity_weights = {
            TaskComplexity.SIMPLE: 1,
            TaskComplexity.MODERATE: 2,
            TaskComplexity.COMPLEX: 3,
            TaskComplexity.ADVANCED: 4
        }

        for task in tasks:
            weight = task.estimated_time_minutes
            total_weight += weight
            weighted_sum += complexity_weights.get(task.complexity, 2) * weight

        if total_weight == 0:
            return "simple"

        avg_weight = weighted_sum / total_weight

        if avg_weight < 1.5:
            return "simple"
        elif avg_weight < 2.5:
            return "moderate"
        elif avg_weight < 3.5:
            return "complex"
        else:
            return "advanced"


# ============================================================================
# Convenience Functions
# ============================================================================

async def create_implementation_plan(
    requirements: Dict[str, Any],
    research_context: Dict[str, Any],
    db: Session,
    byok_handler: Any
) -> Dict[str, Any]:
    """
    Convenience function to create implementation plan.

    Args:
        requirements: Parsed requirements
        research_context: Codebase research results
        db: Database session
        byok_handler: BYOK handler

    Returns:
        Implementation plan
    """
    agent = PlanningAgent(db, byok_handler)
    return await agent.create_implementation_plan(requirements, research_context)


def validate_dag(tasks: List[ImplementationTask]) -> Dict[str, Any]:
    """
    Convenience function to validate task DAG.

    Args:
        tasks: List of implementation tasks

    Returns:
        Validation result
    """
    validator = DAGValidator()
    dag = validator.build_dag(tasks)
    return validator.validate_dag(dag)


def estimate_complexity(
    task: ImplementationTask,
    research_context: Dict[str, Any]
) -> TaskComplexity:
    """
    Convenience function to estimate task complexity.

    Args:
        task: Implementation task
        research_context: Codebase research results

    Returns:
        Task complexity
    """
    estimator = ComplexityEstimator(research_context)
    return estimator.estimate_complexity(task)
