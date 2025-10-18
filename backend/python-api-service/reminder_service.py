import logging
import uuid
import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any
from enum import Enum

# Configure logging
logger = logging.getLogger(__name__)


class ReminderType(Enum):
    """Types of reminders"""

    CALENDAR = "calendar"
    TASK = "task"
    MEETING = "meeting"
    DEADLINE = "deadline"
    CUSTOM = "custom"


class ReminderPriority(Enum):
    """Reminder priority levels"""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class Reminder:
    """Reminder representation"""

    def __init__(
        self,
        id: str,
        user_id: str,
        title: str,
        due_time: datetime,
        reminder_type: ReminderType = ReminderType.CUSTOM,
        priority: ReminderPriority = ReminderPriority.MEDIUM,
        description: Optional[str] = None,
        related_item_id: Optional[str] = None,
        recurring: bool = False,
        recurrence_pattern: Optional[str] = None,
        snooze_count: int = 0,
        completed: bool = False,
        created_at: Optional[datetime] = None,
        updated_at: Optional[datetime] = None,
    ):
        self.id = id
        self.user_id = user_id
        self.title = title
        self.due_time = due_time
        self.reminder_type = reminder_type
        self.priority = priority
        self.description = description
        self.related_item_id = related_item_id
        self.recurring = recurring
        self.recurrence_pattern = recurrence_pattern
        self.snooze_count = snooze_count
        self.completed = completed
        self.created_at = created_at or datetime.now()
        self.updated_at = updated_at or datetime.now()

    def to_dict(self) -> Dict[str, Any]:
        """Convert reminder to dictionary"""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "title": self.title,
            "due_time": self.due_time.isoformat(),
            "reminder_type": self.reminder_type.value,
            "priority": self.priority.value,
            "description": self.description,
            "related_item_id": self.related_item_id,
            "recurring": self.recurring,
            "recurrence_pattern": self.recurrence_pattern,
            "snooze_count": self.snooze_count,
            "completed": self.completed,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Reminder":
        """Create reminder from dictionary"""
        return cls(
            id=data["id"],
            user_id=data["user_id"],
            title=data["title"],
            due_time=datetime.fromisoformat(data["due_time"]),
            reminder_type=ReminderType(data["reminder_type"]),
            priority=ReminderPriority(data["priority"]),
            description=data.get("description"),
            related_item_id=data.get("related_item_id"),
            recurring=data.get("recurring", False),
            recurrence_pattern=data.get("recurrence_pattern"),
            snooze_count=data.get("snooze_count", 0),
            completed=data.get("completed", False),
            created_at=datetime.fromisoformat(data["created_at"])
            if data.get("created_at")
            else None,
            updated_at=datetime.fromisoformat(data["updated_at"])
            if data.get("updated_at")
            else None,
        )


class ReminderService:
    """Service for reminder management operations"""

    def __init__(self):
        self.reminders = {}  # In-memory storage for demo purposes
        self.active_tasks = {}

    async def create_reminder(
        self,
        user_id: str,
        title: str,
        due_time: datetime,
        reminder_type: ReminderType = ReminderType.CUSTOM,
        priority: ReminderPriority = ReminderPriority.MEDIUM,
        description: Optional[str] = None,
        related_item_id: Optional[str] = None,
        recurring: bool = False,
        recurrence_pattern: Optional[str] = None,
    ) -> Optional[Reminder]:
        """
        Create a new reminder

        Args:
            user_id: User identifier
            title: Reminder title
            due_time: When the reminder should trigger
            reminder_type: Type of reminder
            priority: Reminder priority
            description: Reminder description
            related_item_id: ID of related item (task, event, etc.)
            recurring: Whether the reminder recurs
            recurrence_pattern: Pattern for recurrence

        Returns:
            Created reminder or None if failed
        """
        try:
            reminder_id = str(uuid.uuid4())
            reminder = Reminder(
                id=reminder_id,
                user_id=user_id,
                title=title,
                due_time=due_time,
                reminder_type=reminder_type,
                priority=priority,
                description=description,
                related_item_id=related_item_id,
                recurring=recurring,
                recurrence_pattern=recurrence_pattern,
            )

            # Store reminder
            if user_id not in self.reminders:
                self.reminders[user_id] = {}
            self.reminders[user_id][reminder_id] = reminder

            # Schedule reminder notification
            await self._schedule_reminder_notification(reminder)

            logger.info(f"Created reminder {reminder_id} for user {user_id}")
            return reminder

        except Exception as e:
            logger.error(f"Error creating reminder for user {user_id}: {e}")
            return None

    async def get_reminders(
        self,
        user_id: str,
        reminder_type: Optional[ReminderType] = None,
        priority: Optional[ReminderPriority] = None,
        completed: Optional[bool] = None,
        due_before: Optional[datetime] = None,
        due_after: Optional[datetime] = None,
    ) -> List[Reminder]:
        """
        Get reminders for a user

        Args:
            user_id: User identifier
            reminder_type: Filter by reminder type
            priority: Filter by priority
            completed: Filter by completion status
            due_before: Filter by due time before
            due_after: Filter by due time after

        Returns:
            List of reminders
        """
        try:
            if user_id not in self.reminders:
                return []

            user_reminders = list(self.reminders[user_id].values())

            # Apply filters
            filtered_reminders = user_reminders

            if reminder_type:
                filtered_reminders = [
                    r for r in filtered_reminders if r.reminder_type == reminder_type
                ]

            if priority:
                filtered_reminders = [
                    r for r in filtered_reminders if r.priority == priority
                ]

            if completed is not None:
                filtered_reminders = [
                    r for r in filtered_reminders if r.completed == completed
                ]

            if due_before:
                filtered_reminders = [
                    r for r in filtered_reminders if r.due_time <= due_before
                ]

            if due_after:
                filtered_reminders = [
                    r for r in filtered_reminders if r.due_time >= due_after
                ]

            # Sort by due time (soonest first)
            filtered_reminders.sort(key=lambda x: x.due_time)

            return filtered_reminders

        except Exception as e:
            logger.error(f"Error getting reminders for user {user_id}: {e}")
            return []

    async def update_reminder(
        self, user_id: str, reminder_id: str, updates: Dict[str, Any]
    ) -> Optional[Reminder]:
        """
        Update an existing reminder

        Args:
            user_id: User identifier
            reminder_id: Reminder identifier
            updates: Fields to update

        Returns:
            Updated reminder or None if not found
        """
        try:
            if (
                user_id not in self.reminders
                or reminder_id not in self.reminders[user_id]
            ):
                logger.warning(f"Reminder {reminder_id} not found for user {user_id}")
                return None

            reminder = self.reminders[user_id][reminder_id]

            # Update fields
            if "title" in updates:
                reminder.title = updates["title"]
            if "due_time" in updates:
                reminder.due_time = updates["due_time"]
            if "reminder_type" in updates:
                reminder.reminder_type = ReminderType(updates["reminder_type"])
            if "priority" in updates:
                reminder.priority = ReminderPriority(updates["priority"])
            if "description" in updates:
                reminder.description = updates["description"]
            if "completed" in updates:
                reminder.completed = updates["completed"]
            if "recurring" in updates:
                reminder.recurring = updates["recurring"]
            if "recurrence_pattern" in updates:
                reminder.recurrence_pattern = updates["recurrence_pattern"]

            reminder.updated_at = datetime.now()

            # Reschedule notification if due_time changed
            if "due_time" in updates:
                await self._cancel_reminder_notification(reminder_id)
                await self._schedule_reminder_notification(reminder)

            logger.info(f"Updated reminder {reminder_id} for user {user_id}")
            return reminder

        except Exception as e:
            logger.error(
                f"Error updating reminder {reminder_id} for user {user_id}: {e}"
            )
            return None

    async def delete_reminder(self, user_id: str, reminder_id: str) -> bool:
        """
        Delete a reminder

        Args:
            user_id: User identifier
            reminder_id: Reminder identifier

        Returns:
            True if deleted, False if not found
        """
        try:
            if user_id in self.reminders and reminder_id in self.reminders[user_id]:
                await self._cancel_reminder_notification(reminder_id)
                del self.reminders[user_id][reminder_id]
                logger.info(f"Deleted reminder {reminder_id} for user {user_id}")
                return True
            else:
                logger.warning(f"Reminder {reminder_id} not found for user {user_id}")
                return False

        except Exception as e:
            logger.error(
                f"Error deleting reminder {reminder_id} for user {user_id}: {e}"
            )
            return False

    async def mark_completed(
        self, user_id: str, reminder_id: str
    ) -> Optional[Reminder]:
        """
        Mark reminder as completed

        Args:
            user_id: User identifier
            reminder_id: Reminder identifier

        Returns:
            Updated reminder or None if not found
        """
        try:
            if (
                user_id not in self.reminders
                or reminder_id not in self.reminders[user_id]
            ):
                return None

            reminder = self.reminders[user_id][reminder_id]
            reminder.completed = True
            reminder.updated_at = datetime.now()

            # Cancel notification for completed reminder
            await self._cancel_reminder_notification(reminder_id)

            logger.info(
                f"Marked reminder {reminder_id} as completed for user {user_id}"
            )
            return reminder

        except Exception as e:
            logger.error(f"Error marking reminder {reminder_id} as completed: {e}")
            return None

    async def snooze_reminder(
        self, user_id: str, reminder_id: str, snooze_minutes: int = 15
    ) -> Optional[Reminder]:
        """
        Snooze a reminder

        Args:
            user_id: User identifier
            reminder_id: Reminder identifier
            snooze_minutes: Minutes to snooze

        Returns:
            Updated reminder or None if not found
        """
        try:
            if (
                user_id not in self.reminders
                or reminder_id not in self.reminders[user_id]
            ):
                return None

            reminder = self.reminders[user_id][reminder_id]
            reminder.due_time = datetime.now() + timedelta(minutes=snooze_minutes)
            reminder.snooze_count += 1
            reminder.updated_at = datetime.now()

            # Reschedule notification
            await self._cancel_reminder_notification(reminder_id)
            await self._schedule_reminder_notification(reminder)

            logger.info(f"Snoozed reminder {reminder_id} for {snooze_minutes} minutes")
            return reminder

        except Exception as e:
            logger.error(f"Error snoozing reminder {reminder_id}: {e}")
            return None

    async def get_upcoming_reminders(
        self, user_id: str, hours_ahead: int = 24
    ) -> List[Reminder]:
        """
        Get reminders due in the next specified hours

        Args:
            user_id: User identifier
            hours_ahead: Hours to look ahead

        Returns:
            List of upcoming reminders
        """
        try:
            now = datetime.now()
            end_time = now + timedelta(hours=hours_ahead)

            reminders = await self.get_reminders(
                user_id,
                completed=False,
                due_after=now,
                due_before=end_time,
            )

            return reminders

        except Exception as e:
            logger.error(f"Error getting upcoming reminders for user {user_id}: {e}")
            return []

    async def _schedule_reminder_notification(self, reminder: Reminder):
        """Schedule a reminder notification"""
        try:
            delay = (reminder.due_time - datetime.now()).total_seconds()
            if delay > 0:
                task = asyncio.create_task(
                    self._send_reminder_notification(reminder, delay)
                )
                self.active_tasks[reminder.id] = task
                logger.debug(f"Scheduled notification for reminder {reminder.id}")
        except Exception as e:
            logger.error(
                f"Error scheduling notification for reminder {reminder.id}: {e}"
            )

    async def _cancel_reminder_notification(self, reminder_id: str):
        """Cancel a scheduled reminder notification"""
        try:
            if reminder_id in self.active_tasks:
                self.active_tasks[reminder_id].cancel()
                del self.active_tasks[reminder_id]
                logger.debug(f"Cancelled notification for reminder {reminder_id}")
        except Exception as e:
            logger.error(
                f"Error cancelling notification for reminder {reminder_id}: {e}"
            )

    async def _send_reminder_notification(self, reminder: Reminder, delay: float):
        """Send reminder notification after delay"""
        try:
            await asyncio.sleep(delay)

            # Check if reminder still exists and is not completed
            if (
                reminder.user_id in self.reminders
                and reminder.id in self.reminders[reminder.user_id]
                and not self.reminders[reminder.user_id][reminder.id].completed
            ):
                logger.info(
                    f"REMINDER: {reminder.title} - {reminder.description or 'No description'}"
                )

                # In a real implementation, this would:
                # 1. Send desktop notification
                # 2. Send email notification
                # 3. Send mobile push notification
                # 4. Trigger sound/audio alert

                # For now, just log the reminder
                print(f"\n🔔 REMINDER NOTIFICATION")
                print(f"Title: {reminder.title}")
                print(f"Time: {reminder.due_time}")
                print(f"Priority: {reminder.priority.value}")
                if reminder.description:
                    print(f"Description: {reminder.description}")
                print()

        except asyncio.CancelledError:
            # Task was cancelled, which is expected
            pass
        except Exception as e:
            logger.error(f"Error sending reminder notification for {reminder.id}: {e}")


# Global reminder service instance
reminder_service = ReminderService()


# Utility functions
async def create_task_reminder(
    user_id: str,
    task_title: str,
    due_time: datetime,
    priority: ReminderPriority = ReminderPriority.MEDIUM,
    task_description: Optional[str] = None,
    task_id: Optional[str] = None,
) -> Optional[Reminder]:
    """Create a reminder for a task"""
    return await reminder_service.create_reminder(
        user_id=user_id,
        title=f"Task: {task_title}",
        due_time=due_time,
        reminder_type=ReminderType.TASK,
        priority=priority,
        description=task_description,
        related_item_id=task_id,
    )


async def create_meeting_reminder(
    user_id: str,
    meeting_title: str,
    meeting_time: datetime,
    priority: ReminderPriority = ReminderPriority.HIGH,
    meeting_description: Optional[str] = None,
    meeting_id: Optional[str] = None,
) -> Optional[Reminder]:
    """Create a reminder for a meeting"""
    # Set reminder 15 minutes before meeting
    reminder_time = meeting_time - timedelta(minutes=15)

    return await reminder_service.create_reminder(
        user_id=user_id,
        title=f"Meeting: {meeting_title}",
        due_time=reminder_time,
        reminder_type=ReminderType.MEETING,
        priority=priority,
        description=meeting_description,
        related_item_id=meeting_id,
    )


async def create_deadline_reminder(
    user_id: str,
    deadline_title: str,
    deadline_time: datetime,
    priority: ReminderPriority = ReminderPriority.HIGH,
    deadline_description: Optional[str] = None,
    deadline_id: Optional[str] = None,
) -> Optional[Reminder]:
    """Create a reminder for a deadline"""
    # Set reminder 1 hour before deadline
    reminder_time = deadline_time - timedelta(hours=1)

    return await reminder_service.create_reminder(
        user_id=user_id,
        title=f"Deadline: {deadline_title}",
        due_time=reminder_time,
        reminder_type=ReminderType.DEADLINE,
        priority=priority,
        description=deadline_description,
        related_item_id=deadline_id,
    )


async def get_overdue_reminders(user_id: str) -> List[Reminder]:
    """Get overdue reminders"""
    now = datetime.now()
    reminders = await reminder_service.get_reminders(
        user_id, completed=False, due_before=now
    )
    return reminders


async def clear_completed_reminders(user_id: str) -> int:
    """Clear all completed reminders for a user"""
