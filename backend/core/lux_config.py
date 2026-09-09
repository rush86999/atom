
import logging
import os
from typing import Optional

from core.byok_endpoints import get_byok_manager

logger = logging.getLogger(__name__)


class LuxConfig:
    # Default computer-use brain. gpt-6-astra (quality 100, vision+tools)
    # is the frontier pick; claude-3-5-sonnet-20241022 was the pre-astra
    # default and remains a working fallback for Anthropic-keyed installs.
    DEFAULT_COMPUTER_USE_MODEL = "gpt-6-astra"

    # Safety rail for the run_task loop: desktop actuation is irreversible
    # in the real world, so the loop caps itself instead of trusting the
    # model's done-detection alone.
    DEFAULT_MAX_STEPS = 15

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

    def get_computer_use_model(self) -> str:
        """
        Model id for the computer-use loop (LuxModel).

        Env-overridable via ATOM_COMPUTER_USE_MODEL. The id is passed as an
        explicit model pick to the routing layer, so BYOK/fallback rules
        apply if the configured model's provider has no key.
        """
        return os.getenv("ATOM_COMPUTER_USE_MODEL") or self.DEFAULT_COMPUTER_USE_MODEL

    def get_max_steps(self) -> int:
        """Step budget for the computer-use agent loop."""
        try:
            return max(1, int(os.getenv("ATOM_COMPUTER_USE_MAX_STEPS", str(self.DEFAULT_MAX_STEPS))))
        except ValueError:
            return self.DEFAULT_MAX_STEPS

lux_config = LuxConfig()
