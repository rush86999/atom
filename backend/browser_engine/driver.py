import logging
import asyncio
from typing import Optional, List, Dict
from playwright.async_api import async_playwright, Browser, BrowserContext, Page

logger = logging.getLogger(__name__)

class BrowserManager:
    """
    Manages Playwright browser instances and contexts.
    Abstraction layer to support future "Remote Cloud PC" connections.
    """
    _instance = None

    def __init__(self, headless: bool = True):
        self.headless = headless
        self.playwright = None
        self.browser: Optional[Browser] = None
        self.active_contexts: List[BrowserContext] = []

    @classmethod
    def get_instance(cls, headless: bool = True):
        if cls._instance is None:
            cls._instance = BrowserManager(headless)
        return cls._instance

    async def start(self):
        """Initialize Playwright and Browser."""
        if self.browser:
            return
            
        import os
        cdp_url = os.getenv("BROWSER_WS_ENDPOINT")

        logger.info("Starting Browser Engine...")
        self.playwright = await async_playwright().start()
        
        if cdp_url:
            logger.info(f"Connecting to remote browser at {cdp_url}...")
            self.browser = await self.playwright.chromium.connect_over_cdp(cdp_url)
            logger.info("Connected to remote browser.")
        else:
            # User Agent & Viewport to mimic Desktop
            self.browser = await self.playwright.chromium.launch(
                headless=self.headless,
                args=['--no-sandbox', '--disable-setuid-sandbox', '--disable-gpu', '--disable-dev-shm-usage', '--single-process']
            )
            logger.info("Browser Engine started (Local).")

    async def new_context(self) -> BrowserContext:
        """Create a new isolated browser context."""
        if not self.browser:
            await self.start()
            
        context = await self.browser.new_context(
            viewport={'width': 1280, 'height': 720},
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            accept_downloads=True
        )
        self.active_contexts.append(context)
        return context

    async def close(self):
        """Shutdown all contexts and browser."""
        for ctx in self.active_contexts:
            await ctx.close()
        
        if self.browser:
            await self.browser.close()
        
        if self.playwright:
            await self.playwright.stop()
            
        logger.info("Browser Engine stopped.")
