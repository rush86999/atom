"""
Canvas Presentation Summary Service

Generates LLM-based semantic summaries of canvas state for episodic memory.
Summaries capture business context, intent, and key information.
"""

import json
import hashlib
from typing import Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
import logging



logger = logging.getLogger(__name__)


# Canvas-specific prompts for semantic summarization
CANVAS_PROMPTS = {
    'terminal': """Analyze this terminal canvas and provide a semantic summary:
- Context: What commands were executed and what was the user trying to accomplish?
- Results: What output was produced? Were there errors?
- Working directory: Where is this running?
- State: Is the terminal active or idle?""",

    'desktop': """Analyze this desktop canvas and provide a semantic summary:
- Windows: What applications or windows are open?
- Activity: What is the user working on based on active windows?
- State: Is the desktop organized or cluttered?""",

    'docs': """Analyze this document canvas and provide a semantic summary:
- Document purpose: What is this document about?
- Key sections: What are the main sections or topics?
- Content summary: What are the key points or arguments?
- Collaboration: Is this being actively edited?""",

    'sheets': """Analyze this spreadsheet canvas and provide a semantic summary:
- Purpose: What data is this spreadsheet tracking or analyzing?
- Key data: What are the important values or trends?
- Structure: How is the data organized?""",

    'email': """Analyze this email canvas and provide a semantic summary:
- Purpose: What is this email for (compose, reply, read)?
- Recipients: Who is it addressed to?
- Key content: What is being communicated?
- Attachments: What files are attached?
- Action required: What response is needed?""",

    'integration': """Analyze this integration canvas and provide a semantic summary:
- Integration: What service or API is being integrated?
- Status: Is the connection healthy or are there errors?
- Activity: What data is being synced or processed?
- Issues: Are there any configuration or authentication problems?""",

    'browser': """Analyze this browser canvas and provide a semantic summary:
- Page: What website or web application is loaded?
- Purpose: What is the user doing on this page?
- Content: What is the main content or activity?
- State: Is the page fully loaded and interactive?""",

    'generic': """Analyze this canvas and provide a semantic summary:
- What is the primary activity or purpose?
- What key information is displayed?
- What is the current state?
- Are there any notable issues or errors?"""
}


class CanvasPresentationSummaryService:
    """Generates and caches LLM-based canvas presentation summaries"""

    def __init__(self, db: AsyncSession):
        self.db = db
        from core.service_factory import ServiceFactory
        self.llm = ServiceFactory.get_llm_service()

    def _get_cache_key(self, canvas_id: str, canvas_type: str, state_hash: str) -> str:
        """Generate Redis cache key for canvas summary"""
        return f"canvas:summary:{canvas_id}:{canvas_type}:{state_hash}"

    def _hash_canvas_state(self, canvas_state: Dict[str, Any]) -> str:
        """Generate hash of canvas state for cache invalidation"""
        state_str = json.dumps(canvas_state, sort_keys=True)
        return hashlib.md5(state_str.encode()).hexdigest()[:16]

    async def generate_presentation_summary(
        self,
        canvas_id: str,
        canvas_type: str,
        canvas_state: Dict[str, Any],
        tenant_id: str,
        use_cache: bool = True
    ) -> str:
        """
        Generate LLM-based semantic summary for canvas presentation

        Args:
            canvas_id: Canvas identifier
            canvas_type: Type of canvas (terminal, desktop, docs, etc.)
            canvas_state: Current canvas state as dict
            tenant_id: Tenant ID for LLM routing
            use_cache: Whether to use cache (default: True)

        Returns:
            1-2 sentence semantic summary capturing business context
        """
        # Try to get cache from core
        try:
            from core.cache import cache
            has_cache = hasattr(cache, 'get') and hasattr(cache, 'set')
        except ImportError:
            has_cache = False

        # Generate state hash for cache key
        state_hash = self._hash_canvas_state(canvas_state)
        cache_key = self._get_cache_key(canvas_id, canvas_type, state_hash)

        # Check cache first
        if use_cache and has_cache:
            try:
                # Cache might be async or sync depending on implementation
                import asyncio
                if asyncio.iscoroutinefunction(cache.get):
                    cached_summary = await cache.get(cache_key)
                else:
                    cached_summary = cache.get(cache_key)
                
                if cached_summary:
                    logger.info(f"Cache hit for canvas summary: {canvas_id}")
                    return cached_summary
            except Exception as e:
                logger.warning(f"Cache get failed: {e}")

        # Get canvas-specific prompt
        prompt = CANVAS_PROMPTS.get(canvas_type, CANVAS_PROMPTS['generic'])

        # Build full prompt with canvas state
        state_json = json.dumps(canvas_state, indent=2)
        full_prompt = f"""{prompt}

Canvas State:
{state_json}

Provide a 1-2 sentence semantic summary capturing:
- What the user is doing or trying to accomplish
- Key context or business intent
- Current state or outcome

Summary:"""

        # Generate summary using LLM
        try:
            content = await self.llm.generate_response(
                tenant_id=tenant_id,
                messages=[
                    {'role': 'system', 'content': 'You are an AI assistant that provides concise semantic summaries of canvas state.'},
                    {'role': 'user', 'content': full_prompt}
                ],
                max_tokens=150,
                temperature=0.3
            )

            summary = (content or "").strip()

            # Cache the summary with 1-hour TTL
            if use_cache and summary and has_cache:
                try:
                    import asyncio
                    if asyncio.iscoroutinefunction(cache.set):
                        await cache.set(cache_key, summary, expire=3600)
                    else:
                        cache.set(cache_key, summary, expire=3600)
                    logger.info(f"Cached canvas summary: {canvas_id}")
                except Exception as e:
                    logger.warning(f"Cache set failed: {e}")

            return summary

        except Exception as e:
            logger.error(f"Failed to generate LLM summary for canvas {canvas_id}: {e}")
            # Fallback to generic summary on error
            return f"{canvas_type.capitalize()} canvas with {len(canvas_state)} state elements"
