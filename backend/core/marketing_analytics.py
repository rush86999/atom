from datetime import datetime
import json
import logging
from typing import Any, Dict, List, Optional

# ai_enhanced_service is an optional dependency. When absent, the AI branches
# below degrade to the static fallback instead of raising ModuleNotFoundError
# (BUG-87-4: the module-level guarded import, per business_health_service).
try:
    from integrations.ai_enhanced_service import (
        AIModelType,
        AIRequest,
        AIServiceType,
        AITaskType,
    )
except ImportError:
    AIModelType = None
    AIRequest = None
    AIServiceType = None
    AITaskType = None

logger = logging.getLogger(__name__)

class PlainEnglishReporter:
    """
    Converts complex marketing metrics into simple narrative reports.
    """
    
    def __init__(self, ai_service: Any = None):
        self.ai = ai_service

    NO_DATA_NARRATIVE = (
        "No marketing channel data is available yet. Connect a channel or "
        "record ad spend to see performance."
    )
    NO_DATA_BUDGET_ADVICE = (
        "No channel performance data is available yet; connect a channel "
        "before reallocating budget."
    )

    @staticmethod
    def _channel_rows(metrics_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Return only entries that carry a recorded number.

        The dashboard used to fall back to a fixed "performing well" sentence
        whenever the model was unavailable — a fabricated success on an empty
        workspace. The truthful fallback is derived from these rows, and is
        empty when nothing was recorded.
        """
        rows: List[Dict[str, Any]] = []
        if not isinstance(metrics_data, dict):
            return rows
        for name, value in metrics_data.items():
            if not isinstance(value, dict):
                continue
            leads = value.get("leads", 0) or 0
            spend = value.get("cost", value.get("spend", 0)) or 0
            conversions = value.get("conversions", 0) or 0
            try:
                leads = float(leads)
                spend = float(spend)
                conversions = float(conversions)
            except (TypeError, ValueError):
                continue
            if leads or spend or conversions:
                rows.append({
                    "name": name.replace("_", " "),
                    "leads": leads,
                    "spend": spend,
                    "conversions": conversions,
                })
        return rows

    @classmethod
    def _static_narrative(cls, metrics_data: Dict[str, Any]) -> str:
        rows = cls._channel_rows(metrics_data)
        if not rows:
            return cls.NO_DATA_NARRATIVE
        total_leads = sum(r["leads"] for r in rows)
        total_spend = sum(r["spend"] for r in rows)
        top = max(rows, key=lambda r: r["leads"])
        parts = [
            f"Recorded channels produced {total_leads:g} leads"
            + (f" from {total_spend:g} in spend." if total_spend else ".")
        ]
        if top["leads"]:
            parts.append(
                f"{top['name']} contributed the most leads ({top['leads']:g})."
            )
        remaining = [r["name"] for r in rows if r is not top and r["leads"]]
        if remaining:
            parts.append(
                "Other channels with recorded leads: " + ", ".join(remaining) + "."
            )
        parts.append(
            "These figures come from recorded channel rows only; review them "
            "before changing budget."
        )
        return " ".join(parts)

    async def generate_narrative_report(self, metrics_data: Dict[str, Any]) -> str:
        """
        Takes raw metrics (calls, clicks, spend) and produces a 3-4 sentence plain English report.
        """
        prompt = f"""
        Convert these marketing metrics into a simple, non-technical report for a small business owner:
        Metrics: {json.dumps(metrics_data)}
        
        The report should answer:
        1. Where did leads come from?
        2. What was the most successful channel?
        3. Simple advice for next week.
        
        Avoid technical jargon like "CTR", "CPC", or "ROAS". Use "Calls", "Clicks", and "Value".
        """
        
        if self.ai:
            if AIRequest is None:
                logger.warning(
                    "ai_enhanced_service unavailable; using data-derived narrative report"
                )
                return self._static_narrative(metrics_data)
            request = AIRequest(
                request_id=f"report_{datetime.now().timestamp()}",
                task_type=AITaskType.CONTENT_GENERATION,
                model_type=AIModelType.GPT_4O,
                service_type=AIServiceType.OPENAI,
                input_data=prompt
            )
            response = await self.ai.process_ai_request(request)
            output = response.output_data
            if isinstance(output, dict):
                return output.get('content') or str(output)
            return str(output)

        else:
            return self._static_narrative(metrics_data)

    @classmethod
    def _static_budget_advice(cls, performance_by_channel: Dict[str, Dict[str, Any]]) -> str:
        rows = cls._channel_rows(performance_by_channel)
        if not rows:
            return cls.NO_DATA_BUDGET_ADVICE
        with_spend = [r for r in rows if r["spend"] > 0]
        if with_spend:
            best = min(with_spend, key=lambda r: r["spend"] / max(r["leads"], 1))
            return (
                f"{best['name']} has the lowest recorded cost per lead "
                f"({best['spend'] / max(best['leads'], 1):.2f}). "
                "Review volume and conversion quality before increasing its "
                "budget; this compares recorded rows only."
            )
        top = max(rows, key=lambda r: r["leads"])
        return (
            f"{top['name']} recorded the most leads ({top['leads']:g}), but no "
            "spend was recorded, so no budget change is recommended yet."
        )

    async def get_budget_advice(self, performance_by_channel: Dict[str, Dict[str, Any]]) -> str:
        """
        Suggests budget reallocations based on ROI signals.
        """
        prompt = f"""
        Analyze the performance of these marketing channels and suggest where to put more or less money:
        Performance: {json.dumps(performance_by_channel)}
        
        Provide 1-2 practical recommendations.
        """
        
        if self.ai:
            if AIRequest is None:
                logger.warning(
                    "ai_enhanced_service unavailable; using data-derived budget advice"
                )
                return self._static_budget_advice(performance_by_channel)
            request = AIRequest(
                request_id=f"advice_{datetime.now().timestamp()}",
                task_type=AITaskType.CONTENT_GENERATION,
                model_type=AIModelType.GPT_4O,
                service_type=AIServiceType.OPENAI,
                input_data=prompt
            )
            response = await self.ai.process_ai_request(request)
            output = response.output_data
            if isinstance(output, dict):
                return output.get('content') or str(output)
            return str(output)
        else:
            return self._static_budget_advice(performance_by_channel)
