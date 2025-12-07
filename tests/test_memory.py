"""Tests for the memory system."""

import pytest
from agentic_curator.memory import (
    Memory,
    MemoryStore,
    parse_memory_message,
    create_memory_from_slack,
    memory_store,
    MEMORY_TYPES,
)


class TestMemoryParsing:
    """Test memory message parsing."""

    def test_parse_learned(self):
        """Parse a 'learned' memory."""
        memory = parse_memory_message(
            "Learned: The deploy script needs sudo",
            agent="ai-chris",
        )
        assert memory is not None
        assert memory.memory_type == "learned"
        assert memory.content == "The deploy script needs sudo"
        assert memory.agent == "ai-chris"

    def test_parse_fact(self):
        """Parse a 'fact' memory."""
        memory = parse_memory_message(
            "Fact: Redis runs on port 6379",
            agent="ai-chris",
        )
        assert memory is not None
        assert memory.memory_type == "fact"
        assert memory.content == "Redis runs on port 6379"

    def test_parse_preference(self):
        """Parse a 'preference' memory."""
        memory = parse_memory_message(
            "Preference: User likes bullet points",
            agent="ai-chris",
        )
        assert memory is not None
        assert memory.memory_type == "preference"
        assert memory.content == "User likes bullet points"

    def test_parse_context(self):
        """Parse a 'context' memory."""
        memory = parse_memory_message(
            "Context: Working on auth refactor",
            agent="ai-chris",
        )
        assert memory is not None
        assert memory.memory_type == "context"
        assert memory.content == "Working on auth refactor"

    def test_parse_decision(self):
        """Parse a 'decision' memory."""
        memory = parse_memory_message(
            "Decision: Using PostgreSQL for the database",
            agent="ai-chris",
        )
        assert memory is not None
        assert memory.memory_type == "decision"
        assert memory.content == "Using PostgreSQL for the database"

    def test_parse_with_tags(self):
        """Parse a memory with tags - tags are extracted from content."""
        memory = parse_memory_message(
            "Learned: CI takes 10 minutes #ci #deployment",
            agent="ai-chris",
        )
        assert memory is not None
        assert "CI takes 10 minutes" in memory.content
        assert "ci" in memory.tags
        assert "deployment" in memory.tags

    def test_parse_multiline(self):
        """Parse a multi-line memory."""
        memory = parse_memory_message(
            "learned: vibe-kanban workflow\n1. List projects\n2. Create task",
            agent="ai-chris",
        )
        assert memory is not None
        assert memory.memory_type == "learned"
        assert "vibe-kanban workflow" in memory.content
        assert "List projects" in memory.content
        assert "Create task" in memory.content

    def test_parse_case_insensitive(self):
        """Memory types should be case insensitive."""
        memory = parse_memory_message(
            "LEARNED: Something important",
            agent="ai-chris",
        )
        assert memory is not None
        assert memory.memory_type == "learned"

    def test_parse_invalid_format(self):
        """Invalid format should return None."""
        memory = parse_memory_message(
            "This is just a regular message",
            agent="ai-chris",
        )
        assert memory is None

    def test_parse_with_slack_metadata(self):
        """Parse with Slack metadata."""
        memory = parse_memory_message(
            "Fact: API rate limit is 100/min",
            agent="ai-chris",
            slack_ts="1234567890.123456",
            channel="C0123456",
        )
        assert memory is not None
        assert memory.slack_ts == "1234567890.123456"
        assert memory.channel == "C0123456"


class TestMemory:
    """Test Memory dataclass."""

    def test_to_dict(self):
        """Convert memory to dict."""
        memory = Memory(
            id="abc123",
            content="Test content",
            memory_type="fact",
            agent="ai-chris",
            timestamp="2025-12-07T12:00:00Z",
            tags=["test", "example"],
        )
        data = memory.to_dict()
        assert data["id"] == "abc123"
        assert data["content"] == "Test content"
        assert data["type"] == "fact"
        assert data["tags"] == "test,example"

    def test_from_dict(self):
        """Create memory from dict."""
        data = {
            "id": "abc123",
            "content": "Test content",
            "type": "fact",
            "agent": "ai-chris",
            "timestamp": "2025-12-07T12:00:00Z",
            "tags": "test,example",
        }
        memory = Memory.from_dict(data)
        assert memory.id == "abc123"
        assert memory.content == "Test content"
        assert memory.memory_type == "fact"
        assert memory.tags == ["test", "example"]

    def test_to_slack_message(self):
        """Format memory as Slack message."""
        memory = Memory(
            id="abc123",
            content="Redis runs on 6379",
            memory_type="fact",
            agent="ai-chris",
            timestamp="2025-12-07T12:00:00Z",
            tags=["redis", "infrastructure"],
        )
        msg = memory.to_slack_message()
        assert "Fact: Redis runs on 6379" in msg
        assert "#redis" in msg
        assert "#infrastructure" in msg


class TestMemoryStore:
    """Test MemoryStore."""

    def test_cache_memory(self):
        """Cache and retrieve memory."""
        store = MemoryStore()
        memory = Memory(
            id="test123",
            content="Test",
            memory_type="fact",
            agent="ai-chris",
            timestamp="2025-12-07T12:00:00Z",
        )
        store.cache_memory(memory)
        assert store.get_cached("test123") == memory

    def test_get_all_cached(self):
        """Get all cached memories."""
        store = MemoryStore()
        m1 = Memory(id="1", content="A", memory_type="fact", agent="a", timestamp="t")
        m2 = Memory(id="2", content="B", memory_type="fact", agent="a", timestamp="t")
        store.cache_memory(m1)
        store.cache_memory(m2)
        cached = store.get_all_cached()
        assert len(cached) == 2

    def test_format_memories_for_context(self):
        """Format memories for agent context."""
        store = MemoryStore()
        m1 = Memory(id="1", content="Redis on 6379", memory_type="fact", agent="a", timestamp="t", tags=["redis"])
        m2 = Memory(id="2", content="User likes brevity", memory_type="preference", agent="a", timestamp="t")
        store.cache_memory(m1)
        store.cache_memory(m2)

        context = store.format_memories_for_context(store.get_all_cached())
        assert "## Relevant Memories" in context
        assert "[fact] Redis on 6379" in context
        assert "[preference] User likes brevity" in context
        assert "redis" in context

    def test_redis_key_generation(self):
        """Test Redis key generation."""
        store = MemoryStore(redis_prefix="memory:")
        assert store.get_redis_key("abc123") == "memory:abc123"


class TestCreateMemoryFromSlack:
    """Test the convenience function."""

    def test_create_and_cache(self):
        """Create memory and cache it."""
        # Clear any existing cache
        memory_store._memories.clear()

        memory = create_memory_from_slack(
            text="Fact: Test fact",
            agent="ai-chris",
            slack_ts="123.456",
            channel="C123",
        )
        assert memory is not None
        assert memory_store.get_cached(memory.id) == memory

    def test_invalid_message_returns_none(self):
        """Invalid message should return None."""
        memory = create_memory_from_slack(
            text="Just a regular message",
            agent="ai-chris",
        )
        assert memory is None
