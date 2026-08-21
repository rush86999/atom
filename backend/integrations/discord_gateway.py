"""
Discord Gateway client — real-time MESSAGE_CREATE ingestion via Discord's
WebSocket gateway (P0.4 §7 follow-up: "no poller, bridge drops non-interaction
messages").

Design:
  - Injected ``ws_factory`` (async callable -> ws-like object with
    send/recv/close) keeps the protocol logic fully unit-testable; production
    wires ``websockets.connect``.
  - Lifecycle per connection: await HELLO (op 10) -> IDENTIFY (op 2) with bot
    token + GUILD_MESSAGES|MESSAGE_CONTENT intents -> consume frames,
    heartbeating (op 1) whenever the interval elapses (recv timeout), treating
    op 11 as ACK.
  - MESSAGE_CREATE dispatches to the ``on_message`` callback with the same
    normalized record shape the Discord poller/bridge produce, so everything
    downstream (ingest_message, provenance, search) is unchanged.
  - Resilience: any error/closed connection ends the lifetime; ``start()``
    reconnects with exponential backoff (capped). Fresh IDENTIFY on reconnect
    (RESUME is a v2 optimization).
  - Gated: ``maybe_start_from_env()`` requires DISCORD_GATEWAY_ENABLED=true
    AND DISCORD_BOT_TOKEN. Never raises at the entry points.
"""

import asyncio
import json
import logging
import os
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

GATEWAY_URL = "wss://gateway.discord.gg/?v=10&encoding=json"
_INTENTS = 512 | 32768  # GUILD_MESSAGES | MESSAGE_CONTENT


def _now() -> float:
    import time

    return time.monotonic()


class DiscordGatewayClient:
    """Discord gateway consumer. See module docstring."""

    def __init__(
        self,
        bot_token: str,
        on_message: Optional[Callable[[Dict[str, Any]], Any]] = None,
        heartbeat_jitter: bool = True,
        max_backoff_s: float = 60.0,
    ):
        self.bot_token = bot_token
        self.on_message = on_message
        self.max_backoff_s = max_backoff_s
        self._heartbeat_jitter = heartbeat_jitter
        self._running = False
        self._reconnected_once = False
        self._heartbeat_interval_s = 41.25  # Discord default guidance
        self._last_heartbeat = 0.0

    # ------------------------------------------------------------------ util

    async def _sleep(self, seconds: float) -> None:
        await asyncio.sleep(seconds)

    def _backoff(self, attempt: int) -> float:
        return min(2.0 ** attempt, self.max_backoff_s)

    # ------------------------------------------------------------ single life

    async def _run_once(self, ws: Any, max_iterations: int = 10000) -> None:
        """One connection lifetime: identify, consume, heartbeat. Raises or
        returns when the socket dies."""
        self._last_heartbeat = _now()
        deadline_wait = None
        iterations = 0

        raw = await ws.recv()
        frame = json.loads(raw) if isinstance(raw, (str, bytes)) else {}
        if frame.get("op") == 10:
            interval_ms = (frame.get("d") or {}).get("heartbeat_interval")
            if interval_ms:
                self._heartbeat_interval_s = interval_ms / 1000.0

        await ws.send(json.dumps({
            "op": 2,
            "d": {
                "token": self.bot_token,
                "intents": _INTENTS,
                "properties": {
                    "os": "linux", "browser": "atom", "device": "atom",
                },
            },
        }))

        while not self.closed(ws) and iterations < max_iterations:
            iterations += 1
            elapsed = _now() - self._last_heartbeat
            wait_for = max(0.0, self._heartbeat_interval_s - elapsed)
            try:
                if wait_for > 0:
                    raw = await asyncio.wait_for(ws.recv(), timeout=wait_for)
                else:
                    raise asyncio.TimeoutError()
            except asyncio.TimeoutError:
                await ws.send(json.dumps({"op": 1, "d": None}))
                self._last_heartbeat = _now()
                continue
            except (ConnectionError, OSError, asyncio.IncompleteReadError):
                # Socket died — end this lifetime cleanly; start() backs off
                # and reconnects.
                return

            if not raw:
                continue
            try:
                frame = json.loads(raw)
            except Exception:
                continue

            op = frame.get("op")
            if op == 11:  # heartbeat ACK
                continue
            if op == 0 and frame.get("t") == "MESSAGE_CREATE":
                self._dispatch_message(frame.get("d") or {})

    def closed(self, ws: Any) -> bool:
        return bool(getattr(ws, "closed", False))

    def _dispatch_message(self, data: Dict[str, Any]) -> None:
        if not self.on_message:
            return
        author = data.get("author") or {}
        record = {
            "id": str(data.get("id", "")),
            "content": data.get("content", ""),
            "author": author.get("username", ""),
            "channel_id": str(data.get("channel_id", "")),
            "guild_id": str(data.get("guild_id", "")),
            "timestamp": data.get("timestamp")
            or datetime_utc_now_iso(),
            "direction": "inbound",
            "source_app": "discord",
        }
        try:
            result = self.on_message(record)
            # support sync + async callbacks transparently
            if asyncio.iscoroutine(result):
                asyncio.ensure_future(result)
        except Exception as e:
            logger.warning(f"Discord gateway on_message callback failed: {e}")

    # ------------------------------------------------------------- lifecycle

    async def start(
        self,
        ws_factory: Optional[Callable[[], Any]] = None,
    ) -> None:
        """Consume forever, reconnecting with capped exponential backoff."""
        if ws_factory is None:
            ws_factory = self._default_ws_factory
        self._running = True
        attempt = 0
        while self._running:
            try:
                ws = await ws_factory()
                attempt = 0
                await self._run_once(ws)
                logger.info("Discord gateway connection closed cleanly")
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.warning(f"Discord gateway disconnected: {e}")
            if not self._running:
                break
            delay = self._backoff(attempt)
            attempt += 1
            logger.info(f"Discord gateway reconnecting in {delay:.1f}s")
            await self._sleep(delay)

    def stop(self) -> None:
        self._running = False

    async def _default_ws_factory(self):
        import websockets  # optional dependency

        return await websockets.connect(GATEWAY_URL)


def datetime_utc_now_iso() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()


def maybe_start_from_env(cb: Optional[Callable[[Dict[str, Any]], Any]] = None,
                         ) -> bool:
    """
    Start the gateway iff DISCORD_GATEWAY_ENABLED=true and DISCORD_BOT_TOKEN
    is set. Returns whether the client was started. Never raises.
    """
    try:
        enabled = os.getenv("DISCORD_GATEWAY_ENABLED", "").strip().lower() in (
            "1", "true", "yes", "on",
        )
        token = os.getenv("DISCORD_BOT_TOKEN", "")
        if not enabled or not token:
            return False

        def _on_message(record: Dict[str, Any]) -> None:
            from integrations.atom_communication_ingestion_pipeline import (
                get_ingestion_pipeline,
            )

            pipeline = get_ingestion_pipeline()
            result = pipeline.ingest_message("discord", record)
            if asyncio.iscoroutine(result):
                asyncio.ensure_future(result)

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            logger.warning(
                "Discord gateway start requires a running event loop"
            )
            return False
        client = DiscordGatewayClient(bot_token=token, on_message=cb or _on_message)
        loop.create_task(client.start())
        return True
    except Exception as e:
        logger.warning(f"Discord gateway start failed: {e}")
        return False