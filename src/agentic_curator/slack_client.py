"""Slack API client with cookie authentication."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import httpx

from .auth import SlackAuth

logger = logging.getLogger(__name__)

SLACK_API_BASE = "https://slack.com/api"


@dataclass
class Message:
    """A Slack message."""

    ts: str
    channel: str
    user: str
    text: str
    thread_ts: str | None = None
    reply_count: int = 0

    @property
    def is_thread_parent(self) -> bool:
        """Check if this is the parent of a thread."""
        return self.reply_count > 0

    @property
    def is_thread_reply(self) -> bool:
        """Check if this is a reply in a thread."""
        return self.thread_ts is not None and self.ts != self.thread_ts


@dataclass
class User:
    """A Slack user."""

    id: str
    name: str
    real_name: str = ""


@dataclass
class SlackClient:
    """Slack API client using token + cookie auth."""

    auth: SlackAuth
    _client: httpx.AsyncClient = field(default=None, repr=False)  # type: ignore
    _user_id: str = ""
    _user_name: str = ""
    _team_id: str = ""

    def __post_init__(self) -> None:
        # For xoxc tokens: Authorization header + Cookie header
        # See: https://stackoverflow.com/questions/62759949/accessing-slack-api-with-chrome-authentication-token-xoxc
        headers: dict[str, str] = {
            "Authorization": f"Bearer {self.auth.token}",
        }
        if self.auth.is_client_token:
            # Cookie format: d=xoxd-...
            headers["Cookie"] = f"d={self.auth.cookie}"

        self._client = httpx.AsyncClient(
            base_url=SLACK_API_BASE,
            headers=headers,
            timeout=30.0,
        )

    async def close(self) -> None:
        """Close the HTTP client."""
        await self._client.aclose()

    async def __aenter__(self) -> SlackClient:
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()

    async def _api_call(self, method: str, **kwargs: Any) -> dict[str, Any]:
        """Make a Slack API call."""
        # Use GET for simple calls, POST with form data for others
        if kwargs:
            response = await self._client.post(f"/{method}", data=kwargs)
        else:
            response = await self._client.get(f"/{method}")

        data = response.json()

        if not data.get("ok"):
            error = data.get("error", "unknown_error")
            logger.error(f"Slack API error: {error}")
            raise SlackAPIError(error)

        return data

    async def auth_test(self) -> dict[str, Any]:
        """Test authentication and get user info."""
        data = await self._api_call("auth.test")
        self._user_id = data.get("user_id", "")
        self._user_name = data.get("user", "")
        self._team_id = data.get("team_id", "")
        return data

    @property
    def user_id(self) -> str:
        """Get authenticated user's ID."""
        return self._user_id

    @property
    def user_name(self) -> str:
        """Get authenticated user's name."""
        return self._user_name

    async def get_conversations(
        self,
        types: str = "public_channel,private_channel,mpim,im",
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Get list of conversations the user is in."""
        conversations = []
        cursor = None

        while True:
            kwargs: dict[str, Any] = {"types": types, "limit": limit}
            if cursor:
                kwargs["cursor"] = cursor

            data = await self._api_call("conversations.list", **kwargs)
            conversations.extend(data.get("channels", []))

            cursor = data.get("response_metadata", {}).get("next_cursor")
            if not cursor:
                break

        return conversations

    async def get_history(
        self,
        channel: str,
        oldest: str | None = None,
        limit: int = 100,
    ) -> list[Message]:
        """Get message history from a channel."""
        kwargs: dict[str, Any] = {"channel": channel, "limit": limit}
        if oldest:
            kwargs["oldest"] = oldest
            kwargs["inclusive"] = False

        data = await self._api_call("conversations.history", **kwargs)
        messages = []

        for msg in data.get("messages", []):
            if msg.get("type") != "message":
                continue
            messages.append(
                Message(
                    ts=msg["ts"],
                    channel=channel,
                    user=msg.get("user", ""),
                    text=msg.get("text", ""),
                    thread_ts=msg.get("thread_ts"),
                    reply_count=msg.get("reply_count", 0),
                )
            )

        return messages

    async def get_thread_replies(
        self,
        channel: str,
        thread_ts: str,
        oldest: str | None = None,
    ) -> list[Message]:
        """Get replies in a thread."""
        kwargs: dict[str, Any] = {"channel": channel, "ts": thread_ts, "limit": 100}
        if oldest:
            kwargs["oldest"] = oldest

        data = await self._api_call("conversations.replies", **kwargs)
        messages = []

        for msg in data.get("messages", []):
            if msg.get("type") != "message":
                continue
            messages.append(
                Message(
                    ts=msg["ts"],
                    channel=channel,
                    user=msg.get("user", ""),
                    text=msg.get("text", ""),
                    thread_ts=msg.get("thread_ts"),
                )
            )

        return messages

    async def post_message(
        self,
        channel: str,
        text: str,
        thread_ts: str | None = None,
    ) -> dict[str, Any]:
        """Post a message to a channel or thread."""
        kwargs: dict[str, Any] = {"channel": channel, "text": text}
        if thread_ts:
            kwargs["thread_ts"] = thread_ts

        return await self._api_call("chat.postMessage", **kwargs)

    async def open_dm(self, user_id: str) -> str:
        """Open a DM channel with a user. Returns channel ID."""
        data = await self._api_call("conversations.open", users=user_id)
        return data["channel"]["id"]

    async def send_dm(self, user_id: str, text: str) -> dict[str, Any]:
        """Send a DM to a user."""
        channel_id = await self.open_dm(user_id)
        return await self.post_message(channel=channel_id, text=text)

    async def search_messages(
        self,
        query: str,
        channel: str | None = None,
        count: int = 20,
    ) -> list[dict[str, Any]]:
        """Search for messages.

        Args:
            query: Search query (supports Slack search syntax)
            channel: Optional channel name to search in (e.g., "memory")
            count: Max results to return

        Returns:
            List of message matches
        """
        # Build search query
        search_query = query
        if channel:
            search_query = f"in:#{channel} {query}"

        data = await self._api_call(
            "search.messages",
            query=search_query,
            count=count,
            sort="timestamp",
            sort_dir="desc",
        )

        matches = data.get("messages", {}).get("matches", [])
        return matches

    async def add_reaction(self, channel: str, timestamp: str, reaction: str) -> dict[str, Any]:
        """Add a reaction to a message.

        Args:
            channel: Channel ID
            timestamp: Message timestamp
            reaction: Emoji name without colons (e.g., "white_check_mark")
        """
        return await self._api_call(
            "reactions.add",
            channel=channel,
            timestamp=timestamp,
            name=reaction,
        )

    async def list_users(self, limit: int = 200) -> list[User]:
        """List all users in the workspace.

        Args:
            limit: Max users to return

        Returns:
            List of User objects
        """
        users = []
        cursor = None

        while len(users) < limit:
            kwargs: dict[str, Any] = {"limit": min(limit - len(users), 200)}
            if cursor:
                kwargs["cursor"] = cursor

            data = await self._api_call("users.list", **kwargs)

            for member in data.get("members", []):
                if member.get("deleted") or member.get("is_bot"):
                    continue
                users.append(User(
                    id=member.get("id", ""),
                    name=member.get("name", ""),
                    real_name=member.get("real_name", member.get("name", "")),
                ))

            cursor = data.get("response_metadata", {}).get("next_cursor")
            if not cursor:
                break

        return users

    async def find_user_by_name(self, name: str) -> User | None:
        """Find a user by name (case-insensitive partial match).

        Args:
            name: Name to search for (matches against name or real_name)

        Returns:
            User object or None if not found
        """
        name_lower = name.lower()
        users = await self.list_users()

        for user in users:
            if (name_lower in user.name.lower() or
                name_lower in user.real_name.lower()):
                return user

        return None


class SlackAPIError(Exception):
    """Slack API error."""
