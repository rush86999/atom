"""
Background Agent Runner - Phase 35
Long-running periodic agent execution with logging and status updates.
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import json
import logging
import os
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

class AgentStatus(Enum):
    STOPPED = "stopped"
    RUNNING = "running"
    PAUSED = "paused"
    ERROR = "error"

@dataclass
class AgentLog:
    """Log entry for agent execution"""
    timestamp: datetime
    agent_id: str
    event: str
    details: Optional[str] = None
    status: str = "info"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp.isoformat(),
            "agent_id": self.agent_id,
            "event": self.event,
            "details": self.details,
            "status": self.status
        }

@dataclass
class AgentState:
    """State of a background agent"""
    agent_id: str
    status: AgentStatus = AgentStatus.STOPPED
    last_run: Optional[datetime] = None
    next_run: Optional[datetime] = None
    run_count: int = 0
    error_count: int = 0
    last_error: Optional[str] = None
    interval_seconds: int = 3600  # Default 1 hour

class BackgroundAgentRunner:
    """
    Manages long-running background agents with periodic execution.
    """
    
    def __init__(self, log_dir: str = "/tmp/agent_logs"):
        self._agents: Dict[str, AgentState] = {}
        self._tasks: Dict[str, asyncio.Task] = {}
        self._logs: List[AgentLog] = []
        self._log_dir = log_dir
        self._running = False
        
        os.makedirs(log_dir, exist_ok=True)
    
    def register_agent(
        self,
        agent_id: str,
        interval_seconds: int = 3600
    ):
        """Register an agent for background execution"""
        self._agents[agent_id] = AgentState(
            agent_id=agent_id,
            interval_seconds=interval_seconds
        )
        self._log(agent_id, "registered", f"Interval: {interval_seconds}s")
        logger.info(f"Registered background agent: {agent_id}")
    
    async def start_agent(self, agent_id: str):
        """Start periodic execution of an agent"""
        if agent_id not in self._agents:
            raise ValueError(f"Agent {agent_id} not registered")
        
        state = self._agents[agent_id]
        if state.status == AgentStatus.RUNNING:
            return  # Already running
        
        state.status = AgentStatus.RUNNING
        self._log(agent_id, "started", "Periodic execution started")
        
        # Create background task
        task = asyncio.create_task(self._run_loop(agent_id))
        self._tasks[agent_id] = task
        logger.info(f"Started background agent: {agent_id}")
    
    async def stop_agent(self, agent_id: str):
        """Stop periodic execution of an agent"""
        if agent_id in self._tasks:
            self._tasks[agent_id].cancel()
            del self._tasks[agent_id]
        
        if agent_id in self._agents:
            self._agents[agent_id].status = AgentStatus.STOPPED
            self._log(agent_id, "stopped", "Periodic execution stopped")
        
        logger.info(f"Stopped background agent: {agent_id}")
    
    async def _run_loop(self, agent_id: str):
        """Main loop for periodic agent execution"""
        state = self._agents[agent_id]
        
        while state.status == AgentStatus.RUNNING:
            try:
                # Execute agent
                await self._execute_agent(agent_id)
                
                state.last_run = datetime.now()
                state.run_count += 1
                state.next_run = datetime.now()
                
                # Wait for next interval
                await asyncio.sleep(state.interval_seconds)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                state.error_count += 1
                state.last_error = str(e)
                state.status = AgentStatus.ERROR
                self._log(agent_id, "error", str(e), "error")
                logger.error(f"Agent {agent_id} error: {e}")
                break
    
    async def _execute_agent(self, agent_id: str):
        """Execute a single agent run"""
        self._log(agent_id, "executing", "Portal check started")
        
        try:
            from api.agent_routes import AGENTS, execute_agent_task
            
            if agent_id in AGENTS:
                agent_def = AGENTS[agent_id]
                
                # Phase 35: Inject Context particularly user_id if we can determine it
                # For background runners, they usually run as 'system' or 'owner'
                # We can check if agent has an owner in DB
                from core.database import get_db_session
                from core.models import AgentRegistry
                
                context = {"agent_id": agent_id}
                
                try:
                    with get_db_session() as db:
                    agent_record = db.query(AgentRegistry).filter(AgentRegistry.id == agent_id).first()
                    if agent_record and agent_record.user_id:
                        context["user_id"] = agent_record.user_id
                except Exception as e:
                    logger.warning(f"Could not fetch agent owner context: {e}")
                finally:
                    db.close()

                result = await execute_agent_task(agent_id, agent_def, context)
                
                self._log(agent_id, "completed", f"Result: {json.dumps(result)[:200]}")
                return result
            else:
                self._log(agent_id, "skipped", "Agent not found in registry")
                
        except Exception as e:
            self._log(agent_id, "failed", str(e), "error")
            raise
    
    def _log(self, agent_id: str, event: str, details: str = None, status: str = "info"):
        """Log agent activity"""
        log = AgentLog(
            timestamp=datetime.now(),
            agent_id=agent_id,
            event=event,
            details=details,
            status=status
        )
        self._logs.append(log)
        
        # Write to file
        log_file = os.path.join(self._log_dir, f"{agent_id}.log")
        with open(log_file, "a") as f:
            f.write(f"{log.timestamp.isoformat()} [{status.upper()}] {event}: {details}\n")
    
    def get_status(self, agent_id: str = None) -> Dict[str, Any]:
        """Get status of agents"""
        if agent_id:
            if agent_id not in self._agents:
                return {"error": f"Agent {agent_id} not found"}
            state = self._agents[agent_id]
            return {
                "agent_id": agent_id,
                "status": state.status.value,
                "last_run": state.last_run.isoformat() if state.last_run else None,
                "run_count": state.run_count,
                "error_count": state.error_count,
                "last_error": state.last_error
            }
        
        return {
            agent_id: {
                "status": s.status.value,
                "run_count": s.run_count,
                "error_count": s.error_count
            }
            for agent_id, s in self._agents.items()
        }
    
    def get_logs(self, agent_id: str = None, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent logs"""
        logs = self._logs
        if agent_id:
            logs = [l for l in logs if l.agent_id == agent_id]
        return [l.to_dict() for l in logs[-limit:]]

# Global runner instance
background_runner = BackgroundAgentRunner()
