"""End-to-end tests for the memory workflow."""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from agentic_curator.agent import AgentResponse, parse_agent_response
from agentic_curator.memory import MemoryEntry, MemoryStore, generate_memory_cache


class TestParseAgentResponse:
    """Tests for parsing agent JSON responses."""

    def test_parse_valid_json(self) -> None:
        """Test parsing a valid JSON response."""
        raw = '''{
            "slack_reply": "Hello! I can help with that.",
            "memory_entries": [
                {
                    "summary": "User prefers dark mode",
                    "details": "Mentioned they always use dark mode",
                    "status": "active",
                    "task_type": "preference",
                    "should_persist": true
                }
            ]
        }'''

        result = parse_agent_response(raw)

        assert result.slack_reply == "Hello! I can help with that."
        assert len(result.memory_entries) == 1
        assert result.memory_entries[0]["summary"] == "User prefers dark mode"
        assert result.memory_entries[0]["should_persist"] is True

    def test_parse_json_with_empty_memories(self) -> None:
        """Test parsing response with no memory entries."""
        raw = '''{
            "slack_reply": "Just a simple response.",
            "memory_entries": []
        }'''

        result = parse_agent_response(raw)

        assert result.slack_reply == "Just a simple response."
        assert result.memory_entries == []

    def test_parse_json_embedded_in_text(self) -> None:
        """Test parsing JSON that's embedded in other text."""
        raw = '''Here's my response:

        {
            "slack_reply": "The answer is 42.",
            "memory_entries": []
        }

        Hope that helps!'''

        result = parse_agent_response(raw)

        assert result.slack_reply == "The answer is 42."

    def test_parse_invalid_json_falls_back(self) -> None:
        """Test that invalid JSON falls back to raw text."""
        raw = "This is just plain text without any JSON."

        result = parse_agent_response(raw)

        assert result.slack_reply == raw
        assert result.memory_entries == []
        assert result.raw_response == raw

    def test_parse_malformed_json(self) -> None:
        """Test that malformed JSON falls back gracefully."""
        raw = '{"slack_reply": "missing closing bracket"'

        result = parse_agent_response(raw)

        assert result.slack_reply == raw
        assert result.memory_entries == []

    def test_parse_multiple_memories(self) -> None:
        """Test parsing response with multiple memory entries."""
        raw = '''{
            "slack_reply": "I've noted several things.",
            "memory_entries": [
                {
                    "summary": "Task: Review PR #123",
                    "details": "Need to review before EOD",
                    "status": "active",
                    "task_type": "task",
                    "should_persist": true
                },
                {
                    "summary": "Meeting scheduled for 3pm",
                    "details": "Team sync meeting",
                    "status": "active",
                    "task_type": "general",
                    "should_persist": true
                },
                {
                    "summary": "Temporary note",
                    "should_persist": false
                }
            ]
        }'''

        result = parse_agent_response(raw)

        assert len(result.memory_entries) == 3
        assert result.memory_entries[0]["task_type"] == "task"
        assert result.memory_entries[2]["should_persist"] is False


class TestMemoryWorkflowIntegration:
    """Integration tests for the memory workflow."""

    @pytest.fixture
    def mock_store(self) -> MagicMock:
        """Create a mock memory store."""
        store = MagicMock(spec=MemoryStore)
        store.query.return_value = []
        store.upsert.return_value = "test-memory-id"
        store.upsert_batch.return_value = ["id1", "id2"]
        return store

    def test_workflow_with_no_prior_memories(self, mock_store: MagicMock) -> None:
        """Test workflow when no prior memories exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = Path(tmpdir) / "memory_cache.md"

            # Simulate query with no results
            mock_store.query.return_value = []

            # Generate cache
            memories = mock_store.query("test message", user_id="U123")
            generate_memory_cache(
                query_text="test message",
                memories=memories,
                output_path=cache_path,
            )

            # Verify cache was generated
            assert cache_path.exists()
            content = cache_path.read_text()
            assert "No relevant memories found" in content

    def test_workflow_with_existing_memories(self, mock_store: MagicMock) -> None:
        """Test workflow when prior memories exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = Path(tmpdir) / "memory_cache.md"

            # Simulate query with results
            existing_memories = [
                MemoryEntry(
                    summary="User's timezone is PST",
                    details="Mentioned in previous conversation",
                    user_id="U123",
                    score=0.89,
                ),
                MemoryEntry(
                    summary="Prefers Python over JavaScript",
                    user_id="U123",
                    score=0.75,
                ),
            ]
            mock_store.query.return_value = existing_memories

            # Generate cache
            memories = mock_store.query("What time works for you?", user_id="U123")
            generate_memory_cache(
                query_text="What time works for you?",
                memories=memories,
                output_path=cache_path,
            )

            # Verify cache contains memories
            content = cache_path.read_text()
            assert "User's timezone is PST" in content
            assert "0.89" in content
            assert "Prefers Python" in content

    def test_workflow_stores_new_memories(self, mock_store: MagicMock) -> None:
        """Test that new memories from agent response are stored."""
        # Simulate agent response with memory entries
        agent_response = AgentResponse(
            slack_reply="Sure, I'll help with that!",
            memory_entries=[
                {
                    "summary": "User wants help with deployment",
                    "details": "Deploying to production environment",
                    "status": "active",
                    "task_type": "task",
                    "should_persist": True,
                },
                {
                    "summary": "Temporary thought",
                    "should_persist": False,
                },
            ],
        )

        # Filter and create entries to store
        entries_to_store = []
        for entry_data in agent_response.memory_entries:
            if entry_data.get("should_persist", True):
                entry = MemoryEntry(
                    summary=entry_data.get("summary", ""),
                    details=entry_data.get("details", ""),
                    user_id="U123",
                    channel_id="C456",
                    thread_ts="1234567890.123456",
                    source="conversation",
                    status=entry_data.get("status", "active"),
                    task_type=entry_data.get("task_type", "general"),
                )
                entries_to_store.append(entry)

        # Store entries
        if entries_to_store:
            mock_store.upsert_batch(entries_to_store)

        # Verify only should_persist=True entries were stored
        assert len(entries_to_store) == 1
        assert entries_to_store[0].summary == "User wants help with deployment"
        mock_store.upsert_batch.assert_called_once()

    def test_workflow_handles_empty_memory_entries(self, mock_store: MagicMock) -> None:
        """Test workflow when agent returns no memory entries."""
        agent_response = AgentResponse(
            slack_reply="Just a simple answer.",
            memory_entries=[],
        )

        entries_to_store = []
        for entry_data in agent_response.memory_entries:
            if entry_data.get("should_persist", True):
                entries_to_store.append(MemoryEntry(summary=entry_data["summary"]))

        # No storage should happen
        assert len(entries_to_store) == 0

    def test_memory_cache_cleanup(self) -> None:
        """Test that memory cache file can be cleaned up."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = Path(tmpdir) / "memory_cache.md"

            # Generate cache
            generate_memory_cache(
                query_text="test",
                memories=[],
                output_path=cache_path,
            )

            assert cache_path.exists()

            # Clean up
            cache_path.unlink()
            assert not cache_path.exists()


class TestAgentResponseDataclass:
    """Tests for AgentResponse dataclass."""

    def test_default_values(self) -> None:
        """Test default values."""
        response = AgentResponse(slack_reply="Hello")

        assert response.slack_reply == "Hello"
        assert response.memory_entries == []
        assert response.raw_response == ""

    def test_with_all_values(self) -> None:
        """Test with all values set."""
        response = AgentResponse(
            slack_reply="Hello",
            memory_entries=[{"summary": "test"}],
            raw_response='{"slack_reply": "Hello"}',
        )

        assert response.slack_reply == "Hello"
        assert len(response.memory_entries) == 1
        assert response.raw_response == '{"slack_reply": "Hello"}'
