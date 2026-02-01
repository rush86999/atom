
import asyncio
import json
import logging
import os
import signal
import sys
from typing import Optional

try:
    import redis.asyncio as redis
except ImportError:
    redis = None

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("REDIS_LISTENER")

# Configuration
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
CHANNEL_PATTERN = "workspace:*"  # Listen to all workspace events

class RedisListener:
    def __init__(self):
        self.redis: Optional[redis.Redis] = None
        self.pubsub = None
        self.should_exit = False

    async def connect(self):
        if not redis:
            logger.error("redis-py not installed")
            return False
            
        try:
            self.redis = redis.from_url(REDIS_URL, decode_responses=True)
            await self.redis.ping()
            logger.info(f"✅ Connected to Redis at {REDIS_URL}")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to connect to Redis: {e}")
            return False

    def stop(self):
        self.should_exit = True

    async def start(self):
        if not await self.connect():
            return

        self.pubsub = self.redis.pubsub()
        await self.pubsub.psubscribe(CHANNEL_PATTERN)
        logger.info(f"🎧 Listening for events on {CHANNEL_PATTERN}")

        # Import manager here to avoid circular imports during startup if used as library
        # In a real app, this would be dependency injected
        from core.websockets import manager

        try:
            while not self.should_exit:
                message = await self.pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if message:
                    channel = message['channel']
                    data = message['data']
                    
                    logger.info(f"📨 Received event on {channel}")
                    
                    try:
                        payload = json.loads(data)
                        # Identify event type
                        event_type = payload.get('type', 'update')
                        
                        # Broadcast via WebSocket Manager
                        # We use broadcast_event which standardizes the wrapper
                        await manager.broadcast(channel, payload)
                        
                    except json.JSONDecodeError:
                        logger.warning(f"⚠️ Received non-JSON message on {channel}")
                    except Exception as e:
                        logger.error(f"⚠️ Error processing message: {e}")
                        
                await asyncio.sleep(0.01) # fast loop
                
        except asyncio.CancelledError:
            logger.info("🛑 Listener loop cancelled")
        finally:
            await self.cleanup()

    async def cleanup(self):
        logger.info("Cleaning up...")
        if self.pubsub:
            await self.pubsub.close()
        if self.redis:
            await self.redis.close()

async def main():
    listener = RedisListener()
    
    # Handle signals
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, lambda: setattr(listener, 'should_exit', True))
        
    await listener.start()

if __name__ == "__main__":
    # Add parent dir to path to allow imports from core
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    asyncio.run(main())
