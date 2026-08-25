
import logging
import os
from typing import Optional

from core.byok_endpoints import get_byok_manager

logger = logging.getLogger(__name__)


class LuxConfig:
    def get_anthropic_key(self) -> Optional[str]:
        """
        Retrieve Anthropic API key from BYOK system or Environment.
        """
        # 1. Try BYOK System first
        try:
            byok = get_byok_manager()
            key = byok.get_api_key("anthropic")
            if key:
                return key

            # Also check for 'lux' provider in BYOK
            key = byok.get_api_key("lux")
            if key:
                return key
        except Exception as e:
            logger.debug(f"BYOK system unavailable, falling back to environment variables: {e}")
            
        # 2. Fallback to Environment Variables
        return os.getenv("ANTHROPIC_API_KEY") or os.getenv("LUX_MODEL_API_KEY")

lux_config = LuxConfig()
