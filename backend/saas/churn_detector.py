import logging
from typing import Dict

logger = logging.getLogger(__name__)

class ChurnRiskDetector:
    def __init__(self):
        pass

    def analyze_usage_trend(self, current_usage: Dict[str, float], previous_usage: Dict[str, float]) -> Dict[str, str]:
        """
        Detects churn risk based on usage drop.
        Returns: {risk_level: "low"|"high", reason: str}
        """
        # Key metrics to watch
        metrics = ["api_call", "active_seat", "login"]
        
        drops = []
        
        for metric in metrics:
            curr = current_usage.get(metric, 0)
            prev = previous_usage.get(metric, 0)
            
            if prev > 0:
                drop_pct = (prev - curr) / prev
                if drop_pct > 0.30: # 30% drop threshold
                    drops.append(f"{metric} dropped by {int(drop_pct*100)}%")
            elif prev == 0 and curr == 0:
                 pass # No usage
            
        if drops:
            return {
                "risk_level": "high",
                "risk_score": 80,
                "reason": ", ".join(drops)
            }
            
        return {
            "risk_level": "low",
            "risk_score": 10,
            "reason": "Stable usage"
        }
