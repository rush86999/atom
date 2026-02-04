"""
Scheduled & Recurring Messaging Service

Handles one-time and recurring messages with cron expression support.
Integrates with APScheduler for reliable execution.

Features:
- One-time scheduled messages
- Recurring messages with cron expressions
- Natural language parsing ("every day at 9am" → cron)
- Message templates with variable substitution
- Timezone support
- Execution limits (max_runs, end_date)
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from core.agent_integration_gateway import ActionType, agent_integration_gateway
from core.models import (
    AgentRegistry,
    ScheduledMessage,
    ScheduledMessageStatus,
)
from core.cron_parser import CronParser, natural_language_to_cron

logger = logging.getLogger(__name__)


class ScheduledMessagingService:
    """
    Service for creating and managing scheduled and recurring messages.

    Supports:
    - One-time scheduled messages
    - Recurring messages with cron expressions
    - Natural language schedule parsing
    - Template variable substitution
    """

    def __init__(self, db: Session):
        self.db = db
        self.cron_parser = CronParser()

    def create_scheduled_message(
        self,
        agent_id: str,
        platform: str,
        recipient_id: str,
        template: str,
        schedule_type: str,  # "one_time" or "recurring"
        scheduled_for: Optional[datetime] = None,
        cron_expression: Optional[str] = None,
        natural_language_schedule: Optional[str] = None,
        template_variables: Optional[Dict[str, Any]] = None,
        max_runs: Optional[int] = None,
        end_date: Optional[datetime] = None,
        timezone_str: str = "UTC",
        governance_metadata: Optional[Dict[str, Any]] = None,
    ) -> ScheduledMessage:
        """
        Create a new scheduled message.

        Args:
            agent_id: ID of the agent sending the message
            platform: Target platform (slack, discord, etc.)
            recipient_id: Target recipient ID
            template: Message template (can include {{variables}})
            schedule_type: "one_time" or "recurring"
            scheduled_for: Specific datetime (for one_time)
            cron_expression: Cron expression (for recurring)
            natural_language_schedule: Natural language (e.g., "every day at 9am")
            template_variables: Variable definitions for substitution
            max_runs: Maximum number of executions (None = infinite)
            end_date: Stop after this date
            timezone_str: Timezone for schedule
            governance_metadata: Optional governance metadata

        Returns:
            Created ScheduledMessage object

        Raises:
            HTTPException: If validation fails
        """
        # Validate agent
        agent = self.db.query(AgentRegistry).filter(
            AgentRegistry.id == agent_id
        ).first()
        if not agent:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Agent {agent_id} not found"
            )

        # Validate schedule type
        if schedule_type not in ["one_time", "recurring"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid schedule_type: {schedule_type}. Must be 'one_time' or 'recurring'"
            )

        # Parse natural language if provided
        if natural_language_schedule:
            cron_expression = natural_language_to_cron(natural_language_schedule)

        # Calculate next_run based on schedule type
        if schedule_type == "one_time":
            if not scheduled_for:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="scheduled_for is required for one_time messages"
                )
            next_run = scheduled_for
        else:  # recurring
            if not cron_expression:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="cron_expression or natural_language_schedule is required for recurring messages"
                )
            # Calculate next run from cron
            next_run = self.cron_parser.get_next_run(cron_expression)

        # Create the scheduled message
        message = ScheduledMessage(
            agent_id=agent_id,
            agent_name=agent.name,
            platform=platform,
            recipient_id=recipient_id,
            template=template,
            template_variables=template_variables or {},
            schedule_type=schedule_type,
            cron_expression=cron_expression,
            natural_language_schedule=natural_language_schedule,
            next_run=next_run,
            last_run=None,
            run_count=0,
            max_runs=max_runs,
            end_date=end_date,
            status=ScheduledMessageStatus.ACTIVE.value,
            timezone=timezone_str,
            governance_metadata=governance_metadata or {},
        )

        self.db.add(message)
        self.db.commit()
        self.db.refresh(message)

        logger.info(
            f"Created scheduled message {message.id} ({schedule_type}) "
            f"from agent {agent.name} to {platform}:{recipient_id}, "
            f"next run: {next_run}"
        )

        return message

    def update_scheduled_message(
        self,
        message_id: str,
        template: Optional[str] = None,
        cron_expression: Optional[str] = None,
        natural_language_schedule: Optional[str] = None,
        max_runs: Optional[int] = None,
        end_date: Optional[datetime] = None,
    ) -> ScheduledMessage:
        """Update an existing scheduled message."""
        message = self.db.query(ScheduledMessage).filter(
            ScheduledMessage.id == message_id
        ).first()

        if not message:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Scheduled message {message_id} not found"
            )

        # Update fields
        if template is not None:
            message.template = template

        if natural_language_schedule:
            message.cron_expression = natural_language_to_cron(natural_language_schedule)
            message.natural_language_schedule = natural_language_schedule
            # Recalculate next run
            message.next_run = self.cron_parser.get_next_run(message.cron_expression)

        elif cron_expression is not None:
            message.cron_expression = cron_expression
            # Recalculate next run
            message.next_run = self.cron_parser.get_next_run(cron_expression)

        if max_runs is not None:
            message.max_runs = max_runs

        if end_date is not None:
            message.end_date = end_date

        self.db.commit()
        self.db.refresh(message)

        logger.info(f"Updated scheduled message {message_id}")

        return message

    def pause_scheduled_message(self, message_id: str) -> ScheduledMessage:
        """Pause a scheduled message."""
        message = self.db.query(ScheduledMessage).filter(
            ScheduledMessage.id == message_id
        ).first()

        if not message:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Scheduled message {message_id} not found"
            )

        message.status = ScheduledMessageStatus.PAUSED.value
        self.db.commit()
        self.db.refresh(message)

        logger.info(f"Paused scheduled message {message_id}")

        return message

    def resume_scheduled_message(self, message_id: str) -> ScheduledMessage:
        """Resume a paused scheduled message."""
        message = self.db.query(ScheduledMessage).filter(
            ScheduledMessage.id == message_id
        ).first()

        if not message:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Scheduled message {message_id} not found"
            )

        message.status = ScheduledMessageStatus.ACTIVE.value
        self.db.commit()
        self.db.refresh(message)

        logger.info(f"Resumed scheduled message {message_id}")

        return message

    def cancel_scheduled_message(self, message_id: str) -> ScheduledMessage:
        """Cancel a scheduled message."""
        message = self.db.query(ScheduledMessage).filter(
            ScheduledMessage.id == message_id
        ).first()

        if not message:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Scheduled message {message_id} not found"
            )

        message.status = ScheduledMessageStatus.CANCELLED.value
        self.db.commit()
        self.db.refresh(message)

        logger.info(f"Cancelled scheduled message {message_id}")

        return message

    def get_scheduled_messages(
        self,
        agent_id: Optional[str] = None,
        status: Optional[str] = None,
        schedule_type: Optional[str] = None,
        limit: int = 100,
    ) -> List[ScheduledMessage]:
        """Get scheduled messages with optional filters."""
        query = self.db.query(ScheduledMessage)

        if agent_id:
            query = query.filter(ScheduledMessage.agent_id == agent_id)

        if status:
            query = query.filter(ScheduledMessage.status == status)

        if schedule_type:
            query = query.filter(ScheduledMessage.schedule_type == schedule_type)

        messages = query.order_by(ScheduledMessage.next_run.asc()).limit(limit).all()
        return messages

    def get_scheduled_message(self, message_id: str) -> Optional[ScheduledMessage]:
        """Get a specific scheduled message by ID."""
        return self.db.query(ScheduledMessage).filter(
            ScheduledMessage.id == message_id
        ).first()

    async def execute_due_messages(self) -> Dict[str, int]:
        """
        Execute all scheduled messages that are due.

        Should be called periodically (e.g., every minute).
        Updates next_run for recurring messages, marks completed one-time messages.

        Returns:
            Dictionary with counts: {"sent": X, "failed": Y, "completed": Z}
        """
        now = datetime.now(timezone.utc)

        # Find active messages due to run
        messages = self.db.query(ScheduledMessage).filter(
            ScheduledMessage.status == ScheduledMessageStatus.ACTIVE.value,
            ScheduledMessage.next_run <= now,
        ).all()

        sent_count = 0
        failed_count = 0
        completed_count = 0

        for message in messages:
            try:
                # Check if should still run (end_date, max_runs)
                if message.end_date and message.end_date < now:
                    message.status = ScheduledMessageStatus.COMPLETED.value
                    self.db.commit()
                    completed_count += 1
                    continue

                if message.max_runs and message.run_count >= message.max_runs:
                    message.status = ScheduledMessageStatus.COMPLETED.value
                    self.db.commit()
                    completed_count += 1
                    continue

                # Substitute template variables
                content = self._substitute_template_variables(
                    message.template,
                    message.template_variables
                )

                # Send the message
                params = {
                    "recipient_id": message.recipient_id,
                    "content": content,
                    "workspace_id": "default",
                }

                result = await agent_integration_gateway.execute_action(
                    ActionType.SEND_MESSAGE,
                    message.platform,
                    params
                )

                if result.get("status") == "success":
                    sent_count += 1
                    message.last_run = now
                    message.run_count += 1

                    # Calculate next run or mark as completed
                    if message.schedule_type == "one_time":
                        message.status = ScheduledMessageStatus.COMPLETED.value
                        completed_count += 1
                    else:  # recurring
                        # Calculate next run from cron
                        next_run = self.cron_parser.get_next_run(
                            message.cron_expression,
                            after=now
                        )

                        # Check if next run is past end_date
                        if message.end_date and next_run > message.end_date:
                            message.status = ScheduledMessageStatus.COMPLETED.value
                            completed_count += 1
                        else:
                            message.next_run = next_run

                    self.db.commit()

                    logger.info(
                        f"Executed scheduled message {message.id} "
                        f"(run {message.run_count})"
                    )
                else:
                    failed_count += 1
                    message.status = ScheduledMessageStatus.FAILED.value
                    self.db.commit()
                    logger.error(
                        f"Failed to execute scheduled message {message.id}: "
                        f"{result.get('error')}"
                    )

            except Exception as e:
                failed_count += 1
                message.status = ScheduledMessageStatus.FAILED.value
                self.db.commit()
                logger.error(
                    f"Error executing scheduled message {message.id}: {e}",
                    exc_info=True
                )

        logger.info(
            f"Executed due messages: {sent_count} sent, "
            f"{failed_count} failed, {completed_count} completed"
        )

        return {"sent": sent_count, "failed": failed_count, "completed": completed_count}

    def _substitute_template_variables(
        self,
        template: str,
        variables: Dict[str, Any]
    ) -> str:
        """
        Substitute variables in template.

        Supports {{variable_name}} syntax.
        Includes built-in variables: {{date}}, {{time}}, {{datetime}}
        """
        # Built-in variables
        now = datetime.now(timezone.utc)
        built_ins = {
            "date": now.strftime("%Y-%m-%d"),
            "time": now.strftime("%H:%M:%S"),
            "datetime": now.strftime("%Y-%m-%d %H:%M:%S"),
            "iso_datetime": now.isoformat(),
        }

        # Merge with user variables (user variables take precedence)
        all_variables = {**built_ins, **variables}

        # Substitute
        result = template
        for key, value in all_variables.items():
            placeholder = f"{{{{{key}}}}}"
            result = result.replace(placeholder, str(value))

        return result

    def get_execution_history(
        self,
        agent_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        Get execution history for scheduled messages.

        Returns a list of executions with metadata.
        """
        query = self.db.query(ScheduledMessage)

        if agent_id:
            query = query.filter(ScheduledMessage.agent_id == agent_id)

        messages = query.order_by(ScheduledMessage.last_run.desc()).limit(limit).all()

        history = []
        for msg in messages:
            if msg.last_run:
                history.append({
                    "id": msg.id,
                    "agent_name": msg.agent_name,
                    "platform": msg.recipient_id,
                    "schedule_type": msg.schedule_type,
                    "last_run": msg.last_run,
                    "run_count": msg.run_count,
                    "status": msg.status,
                    "next_run": msg.next_run,
                })

        return history
