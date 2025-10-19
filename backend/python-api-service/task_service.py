"""
Task Service for Atom Personal Assistant

This service provides unified task management across multiple platforms:
- Local task management
- Integration with Notion, Trello, Asana, Jira
- Task synchronization and conflict resolution
"""

import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from enum import Enum

logger = logging.getLogger(__name__)


class TaskStatus(Enum):
    """Task status enumeration"""

    TODO = "todo"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class TaskPriority(Enum):
    """Task priority enumeration"""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class TaskService:
    """Service for task management operations"""

    def __init__(self, db_pool=None):
        self.db_pool = db_pool
        self.integrations = {}  # Will hold task integration instances

    async def create_task(
        self, user_id: str, task_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Create a new task"""
        try:
            task = {
                "id": f"task_{datetime.now().timestamp()}",
                "user_id": user_id,
                "title": task_data.get("title", "Untitled Task"),
                "description": task_data.get("description", ""),
                "status": task_data.get("status", TaskStatus.TODO.value),
                "priority": task_data.get("priority", TaskPriority.MEDIUM.value),
                "due_date": task_data.get("due_date"),
                "project_id": task_data.get("project_id"),
                "tags": task_data.get("tags", []),
                "assignee": task_data.get("assignee"),
                "estimated_hours": task_data.get("estimated_hours"),
                "actual_hours": task_data.get("actual_hours", 0),
                "dependencies": task_data.get("dependencies", []),
                "external_id": task_data.get("external_id"),  # For integrated tasks
                "external_platform": task_data.get(
                    "external_platform"
                ),  # e.g., "notion", "trello"
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
            }

            # Validate required fields
            if not task["title"]:
                raise ValueError("Task title is required")

            # Validate status and priority
            if task["status"] not in [s.value for s in TaskStatus]:
                raise ValueError(f"Invalid task status: {task['status']}")
            if task["priority"] not in [p.value for p in TaskPriority]:
                raise ValueError(f"Invalid task priority: {task['priority']}")

            # Save to database if available
            if self.db_pool:
                await self._save_task_to_db(task)

            # Sync to external platforms if specified
            if task["external_platform"]:
                await self._sync_task_to_external_platform(task)

            logger.info(f"Created task '{task['title']}' for user {user_id}")
            return task

        except Exception as e:
            logger.error(f"Failed to create task: {e}")
            raise

    async def get_tasks(
        self,
        user_id: str,
        status: Optional[str] = None,
        priority: Optional[str] = None,
        project_id: Optional[str] = None,
        due_date_range: Optional[Dict[str, str]] = None,
        tags: Optional[List[str]] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """Get tasks with filtering options"""
        try:
            tasks = []

            # Get tasks from database
            if self.db_pool:
                tasks = await self._get_tasks_from_db(
                    user_id,
                    status,
                    priority,
                    project_id,
                    due_date_range,
                    tags,
                    limit,
                    offset,
                )
            else:
                # Mock data for demonstration
                tasks = self._generate_mock_tasks(user_id)

            # Apply filters
            filtered_tasks = self._apply_task_filters(
                tasks, status, priority, project_id, due_date_range, tags
            )

            # Get tasks from integrated platforms
            integrated_tasks = await self._get_integrated_tasks(
                user_id, status, priority, project_id, due_date_range, tags
            )
            filtered_tasks.extend(integrated_tasks)

            # Sort by priority and due date
            filtered_tasks.sort(
                key=lambda x: (
                    self._get_priority_score(
                        x.get("priority", TaskPriority.MEDIUM.value)
                    ),
                    x.get("due_date", "9999-12-31"),
                )
            )

            return filtered_tasks[:limit]

        except Exception as e:
            logger.error(f"Failed to get tasks: {e}")
            return []

    async def update_task(
        self, user_id: str, task_id: str, updates: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Update an existing task"""
        try:
            # Get existing task
            task = await self._get_task_by_id(user_id, task_id)
            if not task:
                raise ValueError(f"Task {task_id} not found")

            # Apply updates
            for key, value in updates.items():
                if key in [
                    "title",
                    "description",
                    "status",
                    "priority",
                    "due_date",
                    "project_id",
                    "tags",
                    "assignee",
                    "estimated_hours",
                    "actual_hours",
                    "dependencies",
                ]:
                    task[key] = value

            task["updated_at"] = datetime.now().isoformat()

            # Validate updates
            if "status" in updates and updates["status"] not in [
                s.value for s in TaskStatus
            ]:
                raise ValueError(f"Invalid task status: {updates['status']}")
            if "priority" in updates and updates["priority"] not in [
                p.value for p in TaskPriority
            ]:
                raise ValueError(f"Invalid task priority: {updates['priority']}")

            # Save updates
            if self.db_pool:
                await self._update_task_in_db(task)

            # Sync to external platforms if this is an integrated task
            if task.get("external_platform"):
                await self._sync_task_to_external_platform(task)

            logger.info(f"Updated task '{task['title']}' for user {user_id}")
            return task

        except Exception as e:
            logger.error(f"Failed to update task: {e}")
            raise

    async def delete_task(self, user_id: str, task_id: str) -> bool:
        """Delete a task"""
        try:
            task = await self._get_task_by_id(user_id, task_id)
            if not task:
                return False

            # Delete from external platform first if integrated
            if task.get("external_platform"):
                await self._delete_task_from_external_platform(task)

            if self.db_pool:
                await self._delete_task_from_db(user_id, task_id)

            logger.info(f"Deleted task '{task['title']}' for user {user_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to delete task: {e}")
            return False

    async def complete_task(self, user_id: str, task_id: str) -> Dict[str, Any]:
        """Mark a task as completed"""
        try:
            task = await self._get_task_by_id(user_id, task_id)
            if not task:
                raise ValueError(f"Task {task_id} not found")

            # Update task status
            task["status"] = TaskStatus.COMPLETED.value
            task["completed_at"] = datetime.now().isoformat()
            task["updated_at"] = datetime.now().isoformat()

            # Save updates
            if self.db_pool:
                await self._update_task_in_db(task)

            # Sync to external platforms
            if task.get("external_platform"):
                await self._sync_task_to_external_platform(task)

            # Check if this completes any dependent tasks
            await self._check_dependent_tasks(user_id, task_id)

            logger.info(f"Completed task '{task['title']}' for user {user_id}")
            return task

        except Exception as e:
            logger.error(f"Failed to complete task: {e}")
            raise

    async def get_task_statistics(self, user_id: str) -> Dict[str, Any]:
        """Get task statistics for a user"""
        try:
            tasks = await self.get_tasks(user_id, limit=1000)  # Get all tasks

            stats = {
                "total_tasks": len(tasks),
                "completed_tasks": len(
                    [t for t in tasks if t.get("status") == TaskStatus.COMPLETED.value]
                ),
                "in_progress_tasks": len(
                    [
                        t
                        for t in tasks
                        if t.get("status") == TaskStatus.IN_PROGRESS.value
                    ]
                ),
                "todo_tasks": len(
                    [t for t in tasks if t.get("status") == TaskStatus.TODO.value]
                ),
                "overdue_tasks": len([t for t in tasks if self._is_task_overdue(t)]),
                "high_priority_tasks": len(
                    [t for t in tasks if t.get("priority") == TaskPriority.HIGH.value]
                ),
                "urgent_tasks": len(
                    [t for t in tasks if t.get("priority") == TaskPriority.URGENT.value]
                ),
                "total_estimated_hours": sum(
                    t.get("estimated_hours", 0) for t in tasks
                ),
                "total_actual_hours": sum(t.get("actual_hours", 0) for t in tasks),
            }

            # Calculate completion rate
            if stats["total_tasks"] > 0:
                stats["completion_rate"] = round(
                    (stats["completed_tasks"] / stats["total_tasks"]) * 100, 2
                )
            else:
                stats["completion_rate"] = 0

            return stats

        except Exception as e:
            logger.error(f"Failed to get task statistics: {e}")
            return {}

    async def sync_external_tasks(self, user_id: str, platform: str) -> Dict[str, Any]:
        """Sync tasks from external platform"""
        try:
            if platform not in self.integrations:
                raise ValueError(f"Platform {platform} not integrated")

            integration = self.integrations[platform]
            external_tasks = await integration.get_tasks(user_id)

            synced_count = 0
            for external_task in external_tasks:
                # Check if task already exists
                existing_task = await self._find_task_by_external_id(
                    user_id, platform, external_task["external_id"]
                )

                if existing_task:
                    # Update existing task
                    await self.update_task(user_id, existing_task["id"], external_task)
                else:
                    # Create new task
                    external_task["external_platform"] = platform
                    await self.create_task(user_id, external_task)

                synced_count += 1

            return {
                "success": True,
                "platform": platform,
                "tasks_synced": synced_count,
                "timestamp": datetime.now().isoformat(),
            }

        except Exception as e:
            logger.error(f"Failed to sync tasks from {platform}: {e}")
            return {
                "success": False,
                "platform": platform,
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
            }

    def _apply_task_filters(
        self,
        tasks: List[Dict[str, Any]],
        status: Optional[str],
        priority: Optional[str],
        project_id: Optional[str],
        due_date_range: Optional[Dict[str, str]],
        tags: Optional[List[str]],
    ) -> List[Dict[str, Any]]:
        """Apply filters to task list"""
        filtered_tasks = tasks

        if status:
            filtered_tasks = [t for t in filtered_tasks if t.get("status") == status]

        if priority:
            filtered_tasks = [
                t for t in filtered_tasks if t.get("priority") == priority
            ]

        if project_id:
            filtered_tasks = [
                t for t in filtered_tasks if t.get("project_id") == project_id
            ]

        if due_date_range:
            start_date = due_date_range.get("start")
            end_date = due_date_range.get("end")
            filtered_tasks = [
                t
                for t in filtered_tasks
                if self._is_date_in_range(t.get("due_date"), start_date, end_date)
            ]

        if tags:
            filtered_tasks = [
                t
                for t in filtered_tasks
                if any(tag in t.get("tags", []) for tag in tags)
            ]

        return filtered_tasks

    def _is_date_in_range(
        self, date_str: Optional[str], start: Optional[str], end: Optional[str]
    ) -> bool:
        """Check if a date is within a range"""
        if not date_str:
            return False

        try:
            date = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            if start:
                start_date = datetime.fromisoformat(start.replace("Z", "+00:00"))
                if date < start_date:
                    return False
            if end:
                end_date = datetime.fromisoformat(end.replace("Z", "+00:00"))
                if date > end_date:
                    return False
            return True
        except Exception:
            return False

    def _is_task_overdue(self, task: Dict[str, Any]) -> bool:
        """Check if a task is overdue"""
        if task.get("status") == TaskStatus.COMPLETED.value:
            return False

        due_date = task.get("due_date")
        if not due_date:
            return False

        try:
            due = datetime.fromisoformat(due_date.replace("Z", "+00:00"))
            return due < datetime.now()
        except Exception:
            return False

    def _get_priority_score(self, priority: str) -> int:
        """Get numerical score for priority sorting"""
        priority_scores = {
            TaskPriority.URGENT.value: 0,
            TaskPriority.HIGH.value: 1,
            TaskPriority.MEDIUM.value: 2,
            TaskPriority.LOW.value: 3,
        }
        return priority_scores.get(priority, 2)

    def _generate_mock_tasks(self, user_id: str) -> List[Dict[str, Any]]:
        """Generate mock tasks for testing"""
        sample_tasks = [
            {
                "id": f"task_{i}",
                "user_id": user_id,
                "title": f"Sample Task {i}",
                "description": f"This is sample task {i}",
                "status": TaskStatus.TODO.value
                if i % 3 == 0
                else TaskStatus.IN_PROGRESS.value
                if i % 3 == 1
                else TaskStatus.COMPLETED.value,
                "priority": TaskPriority.HIGH.value
                if i % 4 == 0
                else TaskPriority.MEDIUM.value
                if i % 4 == 1
                else TaskPriority.LOW.value,
                "due_date": (datetime.now() + timedelta(days=i)).isoformat(),
                "project_id": f"project_{i % 3}",
                "tags": [f"tag_{j}" for j in range(i % 3)],
                "estimated_hours": i + 1,
                "actual_hours": i if i % 3 == 2 else 0,
                "created_at": (datetime.now() - timedelta(days=i)).isoformat(),
                "updated_at": datetime.now().isoformat(),
            }
            for i in range(10)
        ]
        return sample_tasks

    async def _save_task_to_db(self, task: Dict[str, Any]):
        """Save task to database"""
        # Implementation would depend on database schema
        pass

    async def _get_tasks_from_db(
        self,
        user_id: str,
        status: Optional[str],
        priority: Optional[str],
        project_id: Optional[str],
        due_date_range: Optional[Dict[str, str]],
        tags: Optional[List[str]],
        limit: int,
        offset: int,
    ) -> List[Dict[str, Any]]:
        """Get tasks from database"""
        # Implementation would depend on database schema
        return []

    async def _update_task_in_db(self, task: Dict[str, Any]):
        """Update task in database"""
        # Implementation would depend on database schema
        pass

    async def _delete_task_from_db(self, user_id: str, task_id: str):
        """Delete task from database"""
        # Implementation would depend on database schema
        pass

    async def _get_task_by_id(
        self, user_id: str, task_id: str
    ) -> Optional[Dict[str, Any]]:
        """Get task by ID"""
        # Implementation would depend on database schema
        return None

    async def _find_task_by_external_id(
        self, user_id: str, platform: str, external_id: str
    ) -> Optional[Dict[str, Any]]:
        """Find task by external platform ID"""
        # Implementation would depend on database schema
        return None

    async def _sync_task_to_external_platform(self, task: Dict[str, Any]):
        """Sync task to external platform"""
        platform = task.get("external_platform")
        if platform in self.integrations:
            try:
                await self.integrations[platform].sync_task(task)
            except Exception as e:
                logger.error(f"Failed to sync task to {platform}: {e}")

    async def _delete_task_from_external_platform(self, task: Dict[str, Any]):
        """Delete task from external platform"""
        platform = task.get("external_platform")
        if platform in self.integrations:
            try:
                await self.integrations[platform].delete_task(task)
            except Exception as e:
                logger.error(f"Failed to delete task from {platform}: {e}")

    async def _check_dependent_tasks(self, user_id: str, completed_task_id: str):
        """Check if completing this task unlocks any dependent tasks"""
        # Implementation would check task dependencies and update status
        pass

    async def _get_integrated_tasks(
        self,
        user_id: str,
        status: Optional[str],
        priority: Optional[str],
        project_id: Optional[str],
        due_date_range: Optional[Dict[str, str]],
        tags: Optional[List[str]],
    ) -> List[Dict[str, Any]]:
        """Get tasks from integrated platforms"""
        # This would integrate with external task management services
        return []
