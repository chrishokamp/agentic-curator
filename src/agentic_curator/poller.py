"""Message poller for Slack conversations."""

from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

from .slack_client import Message, SlackClient

logger = logging.getLogger(__name__)


@dataclass
class MessagePoller:
    """Polls Slack for new messages."""

    client: SlackClient
    handle: str  # e.g., "ai-chris"
    poll_interval: float = 5.0
    respond_to_all_relevant: bool = False

    _running: bool = False
    _last_seen: dict[str, str] = field(default_factory=dict)  # channel -> ts
    _conversations: list[dict[str, Any]] = field(default_factory=list)

    @property
    def handle_pattern(self) -> re.Pattern[str]:
        """Pattern to match handle mentions."""
        # Match @handle or <@USER_ID> for the authenticated user
        user_id = self.client.user_id
        return re.compile(
            rf"(?:@{re.escape(self.handle)}|<@{re.escape(user_id)}>)",
            re.IGNORECASE,
        )

    async def start(self) -> AsyncIterator[Message]:
        """Start polling and yield new messages that mention the handle."""
        self._running = True

        # Initial auth test to get user info
        await self.client.auth_test()
        logger.info(f"Authenticated as {self.client.user_name} ({self.client.user_id})")

        # Get initial conversation list
        await self._refresh_conversations()

        # Initialize last_seen timestamps
        await self._initialize_timestamps()

        logger.info(f"Polling {len(self._conversations)} conversations...")
        logger.info(f"Listening for mentions of @{self.handle}")

        while self._running:
            try:
                async for message in self._poll_once():
                    yield message
            except Exception as e:
                logger.error(f"Error polling: {e}")

            await asyncio.sleep(self.poll_interval)

    async def stop(self) -> None:
        """Stop polling."""
        self._running = False

    async def _refresh_conversations(self) -> None:
        """Refresh the list of conversations to poll."""
        self._conversations = await self.client.get_conversations()
        logger.debug(f"Found {len(self._conversations)} conversations")

    async def _initialize_timestamps(self) -> None:
        """Initialize last_seen timestamps to current time."""
        # For each conversation, get the latest message timestamp
        for conv in self._conversations:
            channel_id = conv["id"]
            try:
                messages = await self.client.get_history(channel_id, limit=1)
                if messages:
                    self._last_seen[channel_id] = messages[0].ts
                else:
                    self._last_seen[channel_id] = "0"
            except Exception as e:
                logger.debug(f"Could not get history for {channel_id}: {e}")
                self._last_seen[channel_id] = "0"

    async def _poll_once(self) -> AsyncIterator[Message]:
        """Poll all conversations once for new messages."""
        for conv in self._conversations:
            channel_id = conv["id"]
            oldest = self._last_seen.get(channel_id, "0")

            try:
                messages = await self.client.get_history(channel_id, oldest=oldest)

                # Process messages in chronological order (oldest first)
                for msg in reversed(messages):
                    # Update last seen
                    self._last_seen[channel_id] = msg.ts

                    # Skip own messages
                    if msg.user == self.client.user_id:
                        continue

                    # Check if this message should trigger a response
                    if self._should_respond(msg, conv):
                        yield msg

            except Exception as e:
                logger.debug(f"Error polling {channel_id}: {e}")

    def _should_respond(self, message: Message, conv: dict[str, Any]) -> bool:
        """Determine if we should respond to this message."""
        # Always respond to DMs
        if conv.get("is_im"):
            logger.debug(f"DM from {message.user}: {message.text[:50]}...")
            return True

        # Check for handle mention
        if self.handle_pattern.search(message.text):
            logger.debug(f"Mention in {conv.get('name', conv['id'])}: {message.text[:50]}...")
            return True

        # TODO: If respond_to_all_relevant, use LLM to determine relevance

        return False
