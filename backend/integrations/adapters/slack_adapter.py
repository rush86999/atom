"""
Slack Adapter for Upstream Orchestrator.
Wraps SlackUnifiedService to provide a unified IntegrationService interface.
"""
from typing import Any, Dict, List, Optional
import logging

from core.integration_service import IntegrationService, OperationResult, IntegrationErrorCode
from integrations.slack_service_unified import SlackUnifiedService, SlackError

logger = logging.getLogger(__name__)

class SlackAdapter(IntegrationService):
    """Adapter for Slack integration in Upstream."""

    def __init__(self, tenant_id: Optional[str] = None, config: Optional[Dict[str, Any]] = None):
        super().__init__(tenant_id or "default", config or {})
        self.workspace_id = self.tenant_id
        self.service = SlackUnifiedService(config=self.config)

    def get_capabilities(self) -> Dict[str, Any]:
        return {
            "operations": self.get_supported_operations(),
            "required_params": ["bot_token"],
            "optional_params": [],
            "rate_limits": {},
            "supports_webhooks": True,
        }

    def health_check(self) -> Dict[str, Any]:
        return {"healthy": True, "message": "SlackAdapter ready", "last_check": None}

    async def execute_operation(
        self, 
        operation: str, 
        parameters: Dict[str, Any], 
        context: Optional[Dict[str, Any]] = None
    ) -> OperationResult:
        """
        Execute Slack operations.
        Operations:
        - post_message: channel_id, text, thread_ts, blocks
        - list_channels: types
        - get_channel_history: channel_id, limit
        """
        token = self.config.get("access_token") or parameters.get("access_token")
        if not token:
            return OperationResult(
                success=False, 
                error=IntegrationErrorCode.AUTH_EXPIRED, 
                message="Missing Slack access token"
            )

        try:
            if operation == "post_message":
                channel_id = parameters.get("channel_id")
                text = parameters.get("text")
                if not channel_id or not text:
                    return OperationResult(success=False, error=IntegrationErrorCode.INVALID_PARAMETERS, message="Missing channel_id or text")
                
                result = await self.service.post_message(
                    token, channel_id, text, 
                    thread_ts=parameters.get("thread_ts"),
                    blocks=parameters.get("blocks")
                )
                return OperationResult(success=True, data=result)

            elif operation == "list_channels":
                result = await self.service.list_channels(
                    token, types=parameters.get("types", "public_channel,private_channel")
                )
                return OperationResult(success=True, data={"channels": result})

            elif operation == "get_channel_history":
                channel_id = parameters.get("channel_id")
                result = await self.service.get_channel_history(
                    token, channel_id, limit=parameters.get("limit", 100)
                )
                return OperationResult(success=True, data=result)

            elif operation == "add_reaction":
                channel_id = parameters.get("channel_id")
                timestamp = parameters.get("timestamp")
                reaction = parameters.get("reaction")
                result = await self.service.add_reaction(token, channel_id, timestamp, reaction)
                return OperationResult(success=True, data=result)

            else:
                return OperationResult(
                    success=False, 
                    error=IntegrationErrorCode.NOT_FOUND, 
                    message=f"Operation {operation} not supported by SlackAdapter"
                )

        except SlackError as e:
            return OperationResult(success=False, error=IntegrationErrorCode.API_ERROR, message=str(e))
        except Exception as e:
            logger.error(f"SlackAdapter execution failed: {e}")
            return OperationResult(
                success=False, 
                error=IntegrationErrorCode.EXECUTION_EXCEPTION, 
                message=str(e)
            )

    def get_supported_operations(self) -> List[str]:
        return ["post_message", "list_channels", "get_channel_history", "add_reaction", "update_message"]
