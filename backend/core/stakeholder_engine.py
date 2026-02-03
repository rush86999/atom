
import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from sqlalchemy import or_, select

from core.database import get_db_session
from core.lancedb_handler import get_lancedb_handler
from core.models import Team, User, team_members

logger = logging.getLogger(__name__)

class StakeholderEngagementEngine:
    """Engine to identify stakeholders and analyze their engagement levels"""
    
    def __init__(self):
        self.db_handler = get_lancedb_handler()
        self.engagement_threshold_days = 3 # Logic: >3 days is "silent" for active stakeholders
        
    async def get_stakeholders_for_user(self, user_id: str, workspace_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Identify a list of stakeholders (people of interest) for the user"""
        stakeholders = {} # Email/ID -> Metadata
        ws_id = workspace_id or "default"
        
        # 1. Get Team Members from SQL
        with get_db_session() as db:
        try:
            # Find all teams the user is in
            team_ids = db.execute(
                select(team_members.c.team_id).where(team_members.c.user_id == user_id)
            ).scalars().all()
            
            if team_ids:
                # Find all members of those teams
                members = db.execute(
                    select(User).join(team_members).where(team_members.c.team_id.in_(team_ids))
                ).scalars().all()
                
                for member in members:
                    if member.id == user_id:
                        continue
                    stakeholders[member.email] = {
                        "id": member.id,
                        "name": f"{member.first_name} {member.last_name}" if member.first_name else member.email,
                        "email": member.email,
                        "source": "team"
                    }
        finally:
            db.close()
            
        # 2. Get Goal-related stakeholders (Mock/Future integration)
        try:
            from core.goal_engine import goal_engine
            for goal in goal_engine.goals.values():
                if goal.owner_id == user_id:
                    for st in goal.sub_tasks:
                        if st.assigned_to and st.assigned_to not in stakeholders:
                            stakeholders[st.assigned_to] = {
                                "id": None,
                                "name": st.assigned_to,
                                "email": st.assigned_to,
                                "source": "goal"
                            }
        except Exception as e:
            logger.warning(f"Failed to fetch goal stakeholders: {e}")
            
        # 3. Add people from recent communications (last 30 days)
        try:
            from integrations.atom_communication_ingestion_pipeline import get_memory_manager
            memory_manager = get_memory_manager(ws_id)
            if not memory_manager.db:
                memory_manager.initialize()
            
            # Fetch last 30 days of comms to identify active contacts
            thirty_days_ago = datetime.utcnow() - timedelta(days=30)
            recent_comms = memory_manager.get_communications_by_timeframe(thirty_days_ago, datetime.utcnow())
            
            for comm in recent_comms:
                # Need to identify who is 'the other person'
                sender = comm.get("sender")
                recipient = comm.get("recipient")
                
                # Simple logic: if sender isn't "user" and it's an email/name, it's a stakeholder
                for person in [sender, recipient]:
                    if person and person != "system" and person != "user" and "@" in str(person):
                        if person not in stakeholders:
                            stakeholders[person] = {
                                "id": None,
                                "name": person.split("@")[0].title(),
                                "email": person,
                                "source": "communication"
                            }
        except Exception as e:
            logger.warning(f"Failed to fetch communication stakeholders: {e}")
            
        return list(stakeholders.values())

    async def calculate_engagement(self, user_id: str, email: str, workspace_id: Optional[str] = None) -> Dict[str, Any]:
        """Calculate engagement metrics for a specific stakeholder"""
        from integrations.atom_communication_ingestion_pipeline import get_memory_manager
        memory_manager = get_memory_manager(workspace_id)
        if not memory_manager.db:
            memory_manager.initialize()
            
        try:
            # Query LanceDB for interactions with this person
            # We look for records where sender or recipient matches the email
            results = memory_manager.connections_table.search().where(
                f"(sender = '{email}' OR recipient = '{email}')"
            ).limit(100).to_pandas()
            
            if not results.empty:
                # Sort in Pandas as LanceDB sorting in where clause can be finicky
                results = results.sort_values("timestamp", ascending=False)
            
            if results.empty:
                return {
                    "last_interaction": None,
                    "interaction_count": 0,
                    "is_silent": True,
                    "days_since": 999
                }
            
            last_ts = results.iloc[0]["timestamp"]
            # LanceDB/Arrow timestamps might need conversion
            if isinstance(last_ts, (int, float)):
                last_interaction = datetime.fromtimestamp(last_ts / 1000000.0) # Assume microsecs
            else:
                last_interaction = last_ts
                
            days_since = (datetime.utcnow() - last_interaction).days
            
            return {
                "last_interaction": last_interaction.isoformat(),
                "interaction_count": len(results),
                "is_silent": days_since >= self.engagement_threshold_days,
                "days_since": days_since,
                "latest_content": results.iloc[0]["content"][:100] + "..."
            }
        except Exception as e:
            logger.error(f"Error calculating engagement for {email}: {e}")
            return {"error": str(e)}

    async def identify_silent_stakeholders(self, user_id: str, workspace_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Identify stakeholders who haven't engaged recently"""
        all_stakeholders = await self.get_stakeholders_for_user(user_id, workspace_id=workspace_id)
        silent_list = []
        
        for s in all_stakeholders:
            engagement = await self.calculate_engagement(user_id, s["email"], workspace_id=workspace_id)
            if engagement.get("is_silent"):
                s.update(engagement)
                # Generate suggested outreach (Mock LLM)
                s["suggested_outreach"] = f"Hi {s['name']}, I wanted to check in on our last thread about '{engagement.get('latest_content', 'our progress') if engagement.get('latest_content') else 'the project'}'. Any updates on your end?"
                silent_list.append(s)
                
        # Sort by days since interaction descending
        silent_list.sort(key=lambda x: x.get("days_since", 0), reverse=True)
        return silent_list

# Global instance
stakeholder_engine = StakeholderEngagementEngine()

def get_stakeholder_engine():
    return stakeholder_engine
