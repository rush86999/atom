from datetime import datetime, timedelta
import logging
from typing import Any, Dict, List, Optional
from pydantic import BaseModel

logger = logging.getLogger(__name__)

class FollowUpCandidate(BaseModel):
    id: str
    recipient: str
    subject: str
    original_sent_at: datetime
    days_since_sent: int
    thread_id: Optional[str] = None
    last_message_snippet: str

class EmailFollowUpEngine:
    """
    Analyzes sent emails to detect items requiring follow-up.
    """
    
    def __init__(self, days_threshold: int = 3):
        self.days_threshold = days_threshold

    @staticmethod
    def _normalize_ts(ts) -> Optional[datetime]:
        """Coerce a timestamp to a naive datetime for safe comparison.

        Handles ISO strings, timezone-aware datetimes (converted to local
        naive), and None/missing values (returned as None so callers can
        skip the record instead of crashing on mixed-type comparisons).
        """
        if ts is None:
            return None
        if isinstance(ts, str):
            ts = datetime.fromisoformat(ts)
        if ts.tzinfo is not None:
            ts = ts.astimezone().replace(tzinfo=None)
        return ts

    async def detect_missing_replies(self, 
                                   sent_messages: List[Dict[str, Any]], 
                                   received_messages: List[Dict[str, Any]]) -> List[FollowUpCandidate]:
        """
        Identifies sent emails that haven't received a reply.
        """
        candidates = []
        now = datetime.now()
        
        # In a real implementation, we would group by thread_id or subject/recipient
        # For mock, we'll assume sent_messages are all potential items
        for msg in sent_messages:
            sent_at = self._normalize_ts(msg.get("sent_at")) or now
            
            days_diff = (now - sent_at).days
            
            if days_diff >= self.days_threshold:
                # Check if we have a reply in received_messages
                # Mock logic: assume no reply if not explicitly found
                has_reply = False
                msg_id = msg.get("id")
                
                for received in received_messages:
                    received_at = self._normalize_ts(received.get("received_at"))
                    if (received_at is not None
                            and received.get("thread_id") == msg.get("thread_id")
                            and received_at > sent_at):
                        has_reply = True
                        break
                
                if not has_reply:
                    candidates.append(FollowUpCandidate(
                        id=msg.get("id", "unknown"),
                        recipient=msg.get("to", "unknown"),
                        subject=msg.get("subject", "No Subject"),
                        original_sent_at=sent_at,
                        days_since_sent=days_diff,
                        thread_id=msg.get("thread_id"),
                        last_message_snippet=msg.get("snippet", "")
                    ))
                    
        return candidates

followup_engine = EmailFollowUpEngine()
