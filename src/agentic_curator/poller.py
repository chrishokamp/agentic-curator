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
    memory_channel_name: str = "memory"  # Name of the #memory channel

    _running: bool = False
    _last_seen: dict[str, str] = field(default_factory=dict)  # channel -> ts
    _conversations: list[dict[str, Any]] = field(default_factory=list)
    # Track threads we've participated in: (channel, thread_ts) -> last_seen_ts
    _active_threads: dict[tuple[str, str], str] = field(default_factory=dict)
    # Memory channel ID (found during init)
    _memory_channel_id: str | None = None

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

        # Find the memory channel
        for conv in self._conversations:
            if conv.get("name") == self.memory_channel_name:
                self._memory_channel_id = conv["id"]
                logger.info(f"Found #{self.memory_channel_name} channel: {self._memory_channel_id}")
                break

    @property
    def memory_channel_id(self) -> str | None:
        """Get the memory channel ID."""
        return self._memory_channel_id

    def is_memory_channel(self, channel_id: str) -> bool:
        """Check if a channel is the memory channel."""
        return self._memory_channel_id is not None and channel_id == self._memory_channel_id

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
        # First, poll channel-level messages
        for conv in self._conversations:
            channel_id = conv["id"]
            oldest = self._last_seen.get(channel_id, "0")

            try:
                messages = await self.client.get_history(channel_id, oldest=oldest)

                if messages:
                    conv_name = conv.get("name", channel_id)
                    logger.debug(f"Found {len(messages)} new message(s) in {conv_name}")

                # Process messages in chronological order (oldest first)
                for msg in reversed(messages):
                    # Update last seen
                    self._last_seen[channel_id] = msg.ts

                    # Check if this message should trigger a response
                    if self._should_respond(msg, conv):
                        logger.info(f"New message to respond to: {msg.text[:80]}...")
                        yield msg
                    else:
                        logger.debug(f"Ignoring message: {msg.text[:50]}...")

            except Exception as e:
                logger.debug(f"Error polling {channel_id}: {e}")

        # Then, poll active threads for new replies
        async for msg in self._poll_active_threads():
            yield msg

    async def _poll_active_threads(self) -> AsyncIterator[Message]:
        """Poll threads we've participated in for new replies."""
        if not self._active_threads:
            return

        logger.debug(f"Polling {len(self._active_threads)} active threads...")

        for (channel_id, thread_ts), last_seen in list(self._active_threads.items()):
            try:
                # Get all replies in the thread
                replies = await self.client.get_thread_replies(
                    channel=channel_id,
                    thread_ts=thread_ts,
                )

                logger.debug(f"Thread {thread_ts}: {len(replies)} total messages, last_seen={last_seen}")

                # Filter to only new replies (timestamp > last_seen, not the parent, not from us)
                for reply in replies:
                    # Skip parent message
                    if reply.ts == thread_ts:
                        continue

                    # Skip already-seen messages
                    if reply.ts <= last_seen:
                        continue

                    # Skip our own messages but update last_seen
                    if reply.user == self.client.user_id:
                        self._active_threads[(channel_id, thread_ts)] = reply.ts
                        logger.debug(f"Skipping our own message in thread, updating last_seen to {reply.ts}")
                        continue

                    # Update last seen for this thread
                    self._active_threads[(channel_id, thread_ts)] = reply.ts

                    logger.info(f"New reply in tracked thread {thread_ts}: {reply.text[:80]}...")
                    yield reply

            except Exception as e:
                logger.warning(f"Error polling thread {thread_ts}: {e}")

    def track_thread(self, channel: str, thread_ts: str, last_ts: str | None = None) -> None:
        """Start tracking a thread for new replies.

        Call this after the agent responds in a thread to continue monitoring it.
        """
        key = (channel, thread_ts)
        if key not in self._active_threads:
            self._active_threads[key] = last_ts or thread_ts
            logger.info(f"Now tracking thread {thread_ts} in channel {channel}")

    def untrack_thread(self, channel: str, thread_ts: str) -> None:
        """Stop tracking a thread."""
        key = (channel, thread_ts)
        if key in self._active_threads:
            del self._active_threads[key]
            logger.info(f"Stopped tracking thread {thread_ts}")

    def _should_respond(self, message: Message, conv: dict[str, Any]) -> bool:
        """Determine if we should respond to this message."""
        # Skip messages that look like our startup message
        if "AI Agent Online" in message.text:
            return False

        # Check for handle mention - this is the primary trigger
        if self.handle_pattern.search(message.text):
            logger.debug(f"Handle mention detected: {message.text[:50]}...")
            return True

        # Respond to all DMs (including self-DMs)
        if conv.get("is_im"):
            logger.debug(f"DM: {message.text[:50]}...")
            return True

        # TODO: If respond_to_all_relevant, use LLM to determine relevance

        return False
