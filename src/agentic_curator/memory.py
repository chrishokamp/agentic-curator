"""Agent memory system for long-term collaboration via #memory channel."""

from __future__ import annotations

import json
import logging
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)

# Memory types
MEMORY_TYPES = ["learned", "fact", "preference", "context", "decision"]

# Pattern to parse memory messages: "Type: Content" (supports multi-line content)
MEMORY_PATTERN = re.compile(
    r"^(learned|fact|preference|context|decision):\s*(.+)",
    re.IGNORECASE | re.DOTALL,
)

# Pattern to extract tags: #tag1 #tag2
TAG_PATTERN = re.compile(r"#(\w+)")


@dataclass
class Memory:
    """A single memory entry."""

    id: str
    content: str
    memory_type: str
    agent: str
    timestamp: str
    slack_ts: str | None = None
    channel: str | None = None
    tags: list[str] = field(default_factory=list)
    related: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for Redis storage."""
        return {
            "id": self.id,
            "content": self.content,
            "type": self.memory_type,
            "agent": self.agent,
            "timestamp": self.timestamp,
            "slack_ts": self.slack_ts or "",
            "channel": self.channel or "",
            "tags": ",".join(self.tags),
            "related": ",".join(self.related),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Memory:
        """Create from dictionary (Redis retrieval)."""
        return cls(
            id=data.get("id", ""),
            content=data.get("content", ""),
            memory_type=data.get("type", ""),
            agent=data.get("agent", ""),
            timestamp=data.get("timestamp", ""),
            slack_ts=data.get("slack_ts") or None,
            channel=data.get("channel") or None,
            tags=data.get("tags", "").split(",") if data.get("tags") else [],
            related=data.get("related", "").split(",") if data.get("related") else [],
        )

    def to_slack_message(self) -> str:
        """Format as Slack message."""
        msg = f"{self.memory_type.capitalize()}: {self.content}"
        if self.tags:
            msg += f"\nTags: {' '.join('#' + t for t in self.tags)}"
        return msg


def parse_memory_message(text: str, agent: str, slack_ts: str | None = None, channel: str | None = None) -> Memory | None:
    """Parse a Slack message into a Memory object.

    Expected format:
        Type: Content (can be multi-line)

    Examples:
        "Learned: The API uses OAuth2"
        "Fact: Redis port is 6379"
        "learned: vibe-kanban workflow
         1. List projects
         2. Create task
         3. Start attempt"
    """
    text = text.strip()
    if not text:
        return None

    # Match type and content (supports multi-line)
    match = MEMORY_PATTERN.match(text)
    if not match:
        return None

    memory_type = match.group(1).lower()
    content = match.group(2).strip()

    # Extract tags from the entire message
    tags = TAG_PATTERN.findall(text)

    # Generate ID and timestamp
    memory_id = str(uuid.uuid4())
    timestamp = datetime.utcnow().isoformat() + "Z"

    return Memory(
        id=memory_id,
        content=content,
        memory_type=memory_type,
        agent=agent,
        timestamp=timestamp,
        slack_ts=slack_ts,
        channel=channel,
        tags=tags,
    )


class MemoryStore:
    """Interface for storing and retrieving memories.

    This is designed to work with Redis MCP tools, but the actual
    storage calls are made by the agent using MCP tools.
    """

    def __init__(self, redis_prefix: str = "memory:"):
        self.prefix = redis_prefix
        self._memories: dict[str, Memory] = {}  # Local cache

    def get_redis_key(self, memory_id: str) -> str:
        """Get Redis key for a memory."""
        return f"{self.prefix}{memory_id}"

    def get_store_commands(self, memory: Memory) -> list[dict[str, Any]]:
        """Get Redis commands to store a memory.

        Returns commands that the agent can execute via MCP tools.
        """
        key = self.get_redis_key(memory.id)
        data = memory.to_dict()

        # Use hset for each field
        commands = []
        for field_name, value in data.items():
            commands.append({
                "tool": "mcp__redis__hset",
                "params": {
                    "name": key,
                    "key": field_name,
                    "value": str(value),
                },
            })

        return commands

    def get_retrieve_command(self, memory_id: str) -> dict[str, Any]:
        """Get Redis command to retrieve a memory."""
        return {
            "tool": "mcp__redis__hgetall",
            "params": {"name": self.get_redis_key(memory_id)},
        }

    def get_search_command(self, pattern: str = "*") -> dict[str, Any]:
        """Get Redis command to search for memories."""
        return {
            "tool": "mcp__redis__scan_keys",
            "params": {"pattern": f"{self.prefix}{pattern}"},
        }

    def cache_memory(self, memory: Memory) -> None:
        """Cache a memory locally."""
        self._memories[memory.id] = memory

    def get_cached(self, memory_id: str) -> Memory | None:
        """Get a cached memory."""
        return self._memories.get(memory_id)

    def get_all_cached(self) -> list[Memory]:
        """Get all cached memories."""
        return list(self._memories.values())

    def format_memories_for_context(self, memories: list[Memory], max_chars: int = 2000) -> str:
        """Format memories for inclusion in agent context."""
        if not memories:
            return ""

        lines = ["## Relevant Memories\n"]
        total_chars = len(lines[0])

        for mem in memories:
            line = f"- [{mem.memory_type}] {mem.content}"
            if mem.tags:
                line += f" (tags: {', '.join(mem.tags)})"
            line += "\n"

            if total_chars + len(line) > max_chars:
                lines.append("- ... (more memories available)\n")
                break

            lines.append(line)
            total_chars += len(line)

        return "".join(lines)


# Global memory store instance
memory_store = MemoryStore()


def create_memory_from_slack(
    text: str,
    agent: str,
    slack_ts: str | None = None,
    channel: str | None = None,
) -> Memory | None:
    """Create and cache a memory from a Slack message."""
    memory = parse_memory_message(text, agent, slack_ts, channel)
    if memory:
        memory_store.cache_memory(memory)
        logger.info(f"Created memory {memory.id}: [{memory.memory_type}] {memory.content[:50]}...")
    return memory
