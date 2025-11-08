import os
import json
import logging
import httpx
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
from asyncpg import Pool

logger = logging.getLogger(__name__)

# Google Tasks API configuration
GOOGLE_TASKS_API_BASE = "https://tasks.googleapis.com/v1"

class GoogleTasksService:
    """Comprehensive Google Tasks API Service"""
    
    def __init__(self, user_id: str):
        self.user_id = user_id
        self.access_token = None
        self.db_pool = None
        self._initialized = False
    
    async def initialize(self, db_pool: Pool):
        """Initialize Google Tasks service with database pool"""
        try:
            from db_oauth_google_drive import get_user_google_drive_tokens
            from main_api_app import get_db_pool
            
            self.db_pool = db_pool
            tokens = await get_user_google_drive_tokens(db_pool, self.user_id)
            
            if tokens and tokens.get("access_token"):
                self.access_token = tokens["access_token"]
                self._initialized = True
                logger.info(f"Google Tasks service initialized for user {self.user_id}")
                return True
            else:
                logger.warning(f"No Google tokens found for user {self.user_id}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to initialize Google Tasks service: {e}")
            return False
    
    async def _ensure_initialized(self):
        """Ensure service is initialized"""
        if not self._initialized:
            raise Exception("Google Tasks service not initialized. Call initialize() first.")
    
    async def get_task_lists(self, page_size: int = 50) -> Dict[str, Any]:
        """Get all task lists"""
        try:
            await self._ensure_initialized()
            
            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json"
            }
            
            params = {
                "maxResults": page_size,
                "fields": "items(id,title,updated,kind,etag)"
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{GOOGLE_TASKS_API_BASE}/users/@me/lists",
                    headers=headers,
                    params=params
                )
                response.raise_for_status()
                
                data = response.json()
                task_lists = []
                
                for item in data.get("items", []):
                    task_lists.append({
                        "id": item.get("id"),
                        "title": item.get("title"),
                        "updated": item.get("updated"),
                        "kind": item.get("kind"),
                        "etag": item.get("etag"),
                        "taskCount": await self.get_task_count(item.get("id"))
                    })
                
                # Cache task lists
                await self.cache_task_lists(task_lists)
                
                return {
                    "success": True,
                    "data": task_lists,
                    "total": len(task_lists)
                }
                
        except Exception as e:
            logger.error(f"Failed to get task lists: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def get_task_count(self, task_list_id: str) -> int:
        """Get count of tasks in a list"""
        try:
            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json"
            }
            
            params = {
                "maxResults": 100,
                "fields": "items(id,status)"
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{GOOGLE_TASKS_API_BASE}/lists/{task_list_id}/tasks",
                    headers=headers,
                    params=params
                )
                response.raise_for_status()
                
                data = response.json()
                tasks = data.get("items", [])
                
                return len(tasks)
                
        except Exception as e:
            logger.error(f"Failed to get task count: {e}")
            return 0
    
    async def create_task_list(self, title: str) -> Dict[str, Any]:
        """Create a new task list"""
        try:
            await self._ensure_initialized()
            
            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json"
            }
            
            task_list_data = {
                "title": title
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{GOOGLE_TASKS_API_BASE}/users/@me/lists",
                    headers=headers,
                    json=task_list_data
                )
                response.raise_for_status()
                
                data = response.json()
                
                # Log activity
                await self.log_activity("create_task_list", {
                    "task_list_id": data.get("id"),
                    "title": title
                })
                
                return {
                    "success": True,
                    "data": {
                        "id": data.get("id"),
                        "title": data.get("title"),
                        "updated": data.get("updated")
                    }
                }
                
        except Exception as e:
            logger.error(f"Failed to create task list: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def get_tasks(self, task_list_id: str = None, show_completed: bool = True, 
                       show_hidden: bool = False, max_results: int = 100) -> Dict[str, Any]:
        """Get tasks from task list"""
        try:
            await self._ensure_initialized()
            
            # If no task list specified, get all tasks from all lists
            if not task_list_id:
                task_lists_result = await self.get_task_lists()
                if not task_lists_result["success"]:
                    return task_lists_result
                
                all_tasks = []
                for task_list in task_lists_result["data"]:
                    tasks_result = await self.get_tasks_from_list(
                        task_list["id"], show_completed, show_hidden, max_results
                    )
                    if tasks_result["success"]:
                        for task in tasks_result["data"]:
                            task["taskListId"] = task_list["id"]
                            task["taskListTitle"] = task_list["title"]
                        all_tasks.extend(tasks_result["data"])
                
                # Sort by due date and priority
                all_tasks.sort(key=lambda x: (x.get("due", ""), x.get("position", "")))
                
                return {
                    "success": True,
                    "data": all_tasks,
                    "total": len(all_tasks)
                }
            else:
                return await self.get_tasks_from_list(
                    task_list_id, show_completed, show_hidden, max_results
                )
                
        except Exception as e:
            logger.error(f"Failed to get tasks: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def get_tasks_from_list(self, task_list_id: str, show_completed: bool = True, 
                                 show_hidden: bool = False, max_results: int = 100) -> Dict[str, Any]:
        """Get tasks from a specific task list"""
        try:
            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json"
            }
            
            params = {
                "maxResults": max_results,
                "showCompleted": str(show_completed).lower(),
                "showHidden": str(show_hidden).lower(),
                "fields": "items(id,title,notes,status,updated,due,position,parent,kind,etag)"
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{GOOGLE_TASKS_API_BASE}/lists/{task_list_id}/tasks",
                    headers=headers,
                    params=params
                )
                response.raise_for_status()
                
                data = response.json()
                tasks = []
                
                for item in data.get("items", []):
                    tasks.append({
                        "id": item.get("id"),
                        "title": item.get("title"),
                        "notes": item.get("notes"),
                        "status": item.get("status"),
                        "updated": item.get("updated"),
                        "due": item.get("due"),
                        "position": item.get("position"),
                        "parent": item.get("parent"),
                        "kind": item.get("kind"),
                        "etag": item.get("etag"),
                        "isCompleted": item.get("status") == "completed",
                        "hasNotes": bool(item.get("notes")),
                        "hasDueDate": bool(item.get("due")),
                        "isOverdue": self.is_task_overdue(item.get("due"), item.get("status"))
                    })
                
                # Sort by position
                tasks.sort(key=lambda x: x.get("position", ""))
                
                return {
                    "success": True,
                    "data": tasks,
                    "total": len(tasks)
                }
                
        except Exception as e:
            logger.error(f"Failed to get tasks from list: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def create_task(self, task_list_id: str, title: str, notes: str = None, 
                         due: str = None, parent: str = None) -> Dict[str, Any]:
        """Create a new task"""
        try:
            await self._ensure_initialized()
            
            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json"
            }
            
            task_data = {
                "title": title
            }
            
            if notes:
                task_data["notes"] = notes
            if due:
                task_data["due"] = due
            if parent:
                task_data["parent"] = parent
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{GOOGLE_TASKS_API_BASE}/lists/{task_list_id}/tasks",
                    headers=headers,
                    json=task_data
                )
                response.raise_for_status()
                
                data = response.json()
                
                # Log activity
                await self.log_activity("create_task", {
                    "task_id": data.get("id"),
                    "task_list_id": task_list_id,
                    "title": title,
                    "has_notes": bool(notes),
                    "has_due": bool(due),
                    "has_parent": bool(parent)
                })
                
                return {
                    "success": True,
                    "data": {
                        "id": data.get("id"),
                        "title": data.get("title"),
                        "notes": data.get("notes"),
                        "status": data.get("status"),
                        "due": data.get("due"),
                        "position": data.get("position")
                    }
                }
                
        except Exception as e:
            logger.error(f"Failed to create task: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def update_task(self, task_list_id: str, task_id: str, title: str = None, 
                         notes: str = None, status: str = None, due: str = None) -> Dict[str, Any]:
        """Update an existing task"""
        try:
            await self._ensure_initialized()
            
            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json"
            }
            
            task_data = {}
            
            if title is not None:
                task_data["title"] = title
            if notes is not None:
                task_data["notes"] = notes
            if status is not None:
                task_data["status"] = status
            if due is not None:
                task_data["due"] = due
            
            async with httpx.AsyncClient() as client:
                response = await client.patch(
                    f"{GOOGLE_TASKS_API_BASE}/lists/{task_list_id}/tasks/{task_id}",
                    headers=headers,
                    json=task_data
                )
                response.raise_for_status()
                
                data = response.json()
                
                # Log activity
                await self.log_activity("update_task", {
                    "task_id": task_id,
                    "task_list_id": task_list_id,
                    "updated_fields": list(task_data.keys()),
                    "status": status
                })
                
                return {
                    "success": True,
                    "data": {
                        "id": data.get("id"),
                        "title": data.get("title"),
                        "notes": data.get("notes"),
                        "status": data.get("status"),
                        "due": data.get("due"),
                        "updated": data.get("updated")
                    }
                }
                
        except Exception as e:
            logger.error(f"Failed to update task: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def complete_task(self, task_list_id: str, task_id: str) -> Dict[str, Any]:
        """Mark a task as completed"""
        try:
            await self._ensure_initialized()
            
            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json"
            }
            
            task_data = {
                "status": "completed",
                "completed": datetime.now(timezone.utc).isoformat()
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.patch(
                    f"{GOOGLE_TASKS_API_BASE}/lists/{task_list_id}/tasks/{task_id}",
                    headers=headers,
                    json=task_data
                )
                response.raise_for_status()
                
                data = response.json()
                
                # Log activity
                await self.log_activity("complete_task", {
                    "task_id": task_id,
                    "task_list_id": task_list_id
                })
                
                return {
                    "success": True,
                    "data": {
                        "id": data.get("id"),
                        "status": data.get("status"),
                        "completed": data.get("completed")
                    }
                }
                
        except Exception as e:
            logger.error(f"Failed to complete task: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def delete_task(self, task_list_id: str, task_id: str) -> Dict[str, Any]:
        """Delete a task"""
        try:
            await self._ensure_initialized()
            
            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json"
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.delete(
                    f"{GOOGLE_TASKS_API_BASE}/lists/{task_list_id}/tasks/{task_id}",
                    headers=headers
                )
                response.raise_for_status()
                
                # Log activity
                await self.log_activity("delete_task", {
                    "task_id": task_id,
                    "task_list_id": task_list_id
                })
                
                return {
                    "success": True,
                    "message": "Task deleted successfully"
                }
                
        except Exception as e:
            logger.error(f"Failed to delete task: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def delete_task_list(self, task_list_id: str) -> Dict[str, Any]:
        """Delete a task list"""
        try:
            await self._ensure_initialized()
            
            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json"
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.delete(
                    f"{GOOGLE_TASKS_API_BASE}/users/@me/lists/{task_list_id}",
                    headers=headers
                )
                response.raise_for_status()
                
                # Log activity
                await self.log_activity("delete_task_list", {
                    "task_list_id": task_list_id
                })
                
                return {
                    "success": True,
                    "message": "Task list deleted successfully"
                }
                
        except Exception as e:
            logger.error(f"Failed to delete task list: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def search_tasks(self, query: str, task_list_id: str = None) -> Dict[str, Any]:
        """Search tasks"""
        try:
            await self._ensure_initialized()
            
            # Get all tasks
            tasks_result = await self.get_tasks(task_list_id)
            if not tasks_result["success"]:
                return tasks_result
            
            # Filter tasks based on query
            all_tasks = tasks_result["data"]
            filtered_tasks = []
            
            for task in all_tasks:
                search_text = f"{task.get('title', '')} {task.get('notes', '')}".lower()
                if query.lower() in search_text:
                    filtered_tasks.append(task)
            
            # Log search activity
            await self.log_activity("search_tasks", {
                "query": query,
                "task_list_id": task_list_id,
                "results_count": len(filtered_tasks)
            })
            
            return {
                "success": True,
                "data": filtered_tasks,
                "total": len(filtered_tasks)
            }
            
        except Exception as e:
            logger.error(f"Failed to search tasks: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def get_today_tasks(self) -> Dict[str, Any]:
        """Get tasks due today"""
        try:
            await self._ensure_initialized()
            
            # Get all tasks
            tasks_result = await self.get_tasks()
            if not tasks_result["success"]:
                return tasks_result
            
            # Filter tasks due today
            today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            today_tasks = []
            
            for task in tasks_result["data"]:
                due_date = task.get("due")
                if due_date and due_date.startswith(today):
                    today_tasks.append(task)
            
            return {
                "success": True,
                "data": today_tasks,
                "total": len(today_tasks)
            }
            
        except Exception as e:
            logger.error(f"Failed to get today tasks: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def get_overdue_tasks(self) -> Dict[str, Any]:
        """Get overdue tasks"""
        try:
            await self._ensure_initialized()
            
            # Get all tasks
            tasks_result = await self.get_tasks()
            if not tasks_result["success"]:
                return tasks_result
            
            # Filter overdue tasks
            overdue_tasks = []
            
            for task in tasks_result["data"]:
                if task.get("isOverdue", False):
                    overdue_tasks.append(task)
            
            return {
                "success": True,
                "data": overdue_tasks,
                "total": len(overdue_tasks)
            }
            
        except Exception as e:
            logger.error(f"Failed to get overdue tasks: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def get_completed_tasks(self, days: int = 7) -> Dict[str, Any]:
        """Get recently completed tasks"""
        try:
            await self._ensure_initialized()
            
            # Get all tasks including completed
            tasks_result = await self.get_tasks(show_completed=True)
            if not tasks_result["success"]:
                return tasks_result
            
            # Filter recently completed tasks
            cutoff_date = datetime.now(timezone.utc) - timezone.timedelta(days=days)
            completed_tasks = []
            
            for task in tasks_result["data"]:
                if task.get("status") == "completed":
                    # Parse completed date if available
                    completed_date = task.get("completed")
                    if completed_date:
                        try:
                            completed_dt = datetime.fromisoformat(completed_date.replace('Z', '+00:00'))
                            if completed_dt > cutoff_date:
                                completed_tasks.append(task)
                        except:
                            pass
            
            # Sort by completed date
            completed_tasks.sort(key=lambda x: x.get("completed", ""), reverse=True)
            
            return {
                "success": True,
                "data": completed_tasks,
                "total": len(completed_tasks)
            }
            
        except Exception as e:
            logger.error(f"Failed to get completed tasks: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def move_task(self, task_list_id: str, task_id: str, 
                      destination_list_id: str, position: str = None) -> Dict[str, Any]:
        """Move a task to another list"""
        try:
            await self._ensure_initialized()
            
            # First, get the task details
            task_result = await self.get_tasks_from_list(task_list_id, max_results=1000)
            if not task_result["success"]:
                return task_result
            
            # Find the specific task
            task_to_move = None
            for task in task_result["data"]:
                if task["id"] == task_id:
                    task_to_move = task
                    break
            
            if not task_to_move:
                return {
                    "success": False,
                    "error": "Task not found"
                }
            
            # Delete from source list
            delete_result = await self.delete_task(task_list_id, task_id)
            if not delete_result["success"]:
                return delete_result
            
            # Create in destination list
            create_result = await self.create_task(
                destination_list_id,
                task_to_move["title"],
                task_to_move.get("notes"),
                task_to_move.get("due")
            )
            
            if create_result["success"]:
                # Log activity
                await self.log_activity("move_task", {
                    "task_id": task_id,
                    "source_list_id": task_list_id,
                    "destination_list_id": destination_list_id
                })
            
            return create_result
            
        except Exception as e:
            logger.error(f"Failed to move task: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def is_task_overdue(self, due: str, status: str) -> bool:
        """Check if a task is overdue"""
        if not due or status == "completed":
            return False
        
        try:
            due_date = datetime.fromisoformat(due.replace('Z', '+00:00'))
            return due_date < datetime.now(timezone.utc)
        except:
            return False
    
    async def cache_task_lists(self, task_lists: List[Dict[str, Any]]) -> bool:
        """Cache Google Tasks data"""
        try:
            async with self.db_pool.acquire() as conn:
                # Create cache table if it doesn't exist
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS google_tasks_cache (
                        id SERIAL PRIMARY KEY,
                        user_id VARCHAR(255) NOT NULL,
                        task_list_id VARCHAR(255) NOT NULL,
                        task_list_data JSONB,
                        updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(user_id, task_list_id)
                    );
                    
                    CREATE INDEX IF NOT EXISTS idx_google_tasks_user_id ON google_tasks_cache(user_id);
                    CREATE INDEX IF NOT EXISTS idx_google_tasks_task_list_id ON google_tasks_cache(task_list_id);
                """)
                
                # Update cache
                for task_list in task_lists:
                    await conn.execute("""
                        INSERT INTO google_tasks_cache 
                        (user_id, task_list_id, task_list_data)
                        VALUES ($1, $2, $3)
                        ON CONFLICT (user_id, task_list_id)
                        DO UPDATE SET 
                            task_list_data = EXCLUDED.task_list_data,
                            updated_at = CURRENT_TIMESTAMP
                    """, self.user_id, task_list["id"], json.dumps(task_list))
        
            return True
            
        except Exception as e:
            logger.error(f"Failed to cache Google Tasks: {e}")
            return False
    
    async def log_activity(self, action: str, details: Dict[str, Any] = None, 
                         status: str = "success", error_message: str = None):
        """Log Google Tasks activity"""
        try:
            async with self.db_pool.acquire() as conn:
                # Create activity log table if it doesn't exist
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS google_tasks_activity_logs (
                        id SERIAL PRIMARY KEY,
                        user_id VARCHAR(255) NOT NULL,
                        action VARCHAR(255) NOT NULL,
                        action_details JSONB,
                        status VARCHAR(50),
                        error_message TEXT,
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                    );
                    
                    CREATE INDEX IF NOT EXISTS idx_google_tasks_activity_user_id ON google_tasks_activity_logs(user_id);
                    CREATE INDEX IF NOT EXISTS idx_google_tasks_activity_action ON google_tasks_activity_logs(action);
                """)
                
                await conn.execute("""
                    INSERT INTO google_tasks_activity_logs 
                    (user_id, action, action_details, status, error_message)
                    VALUES ($1, $2, $3, $4, $5)
                """, self.user_id, action, json.dumps(details or {}), status, error_message)
        
            return True
            
        except Exception as e:
            logger.error(f"Failed to log Google Tasks activity: {e}")
            return False