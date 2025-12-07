"""Tests for the memory store module."""

from __future__ import annotations

import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from redisvl.query import VectorQuery

from agentic_curator.memory import (
    MemoryEntry,
    MemoryStore,
    MockEmbedder,
    generate_memory_cache,
)


class TestMemoryEntry:
    """Tests for MemoryEntry dataclass."""

    def test_default_values(self) -> None:
        """Test that default values are set correctly."""
        entry = MemoryEntry(summary="Test summary")

        assert entry.summary == "Test summary"
        assert entry.details == ""
        assert entry.user_id == ""
        assert entry.channel_id == ""
        assert entry.thread_ts == ""
        assert entry.source == "conversation"
        assert entry.status == "active"
        assert entry.task_type == "general"
        assert entry.memory_id != ""  # Auto-generated UUID
        assert entry.created_at > 0  # Auto-generated timestamp
        assert entry.score == 0.0

    def test_custom_values(self) -> None:
        """Test that custom values override defaults."""
        entry = MemoryEntry(
            summary="Test",
            details="Details here",
            user_id="U123",
            channel_id="C456",
            thread_ts="1234567890.123456",
            source="manual",
            status="completed",
            task_type="task",
            memory_id="custom-id",
            created_at=1000.0,
            score=0.95,
        )

        assert entry.details == "Details here"
        assert entry.user_id == "U123"
        assert entry.channel_id == "C456"
        assert entry.thread_ts == "1234567890.123456"
        assert entry.source == "manual"
        assert entry.status == "completed"
        assert entry.task_type == "task"
        assert entry.memory_id == "custom-id"
        assert entry.created_at == 1000.0
        assert entry.score == 0.95


class TestMockEmbedder:
    """Tests for MockEmbedder."""

    def test_embed_produces_normalized_vectors(self) -> None:
        """Test that embeddings are normalized."""
        import numpy as np

        embedder = MockEmbedder(dims=384)
        vec = embedder.embed_one("test text")

        assert vec.shape == (384,)
        # Check normalization (magnitude should be ~1)
        magnitude = np.linalg.norm(vec)
        assert abs(magnitude - 1.0) < 1e-5

    def test_embed_deterministic(self) -> None:
        """Test that same text produces same embedding."""
        embedder = MockEmbedder(dims=384)

        vec1 = embedder.embed_one("test text")
        vec2 = embedder.embed_one("test text")

        assert (vec1 == vec2).all()

    def test_embed_different_texts(self) -> None:
        """Test that different texts produce different embeddings."""
        embedder = MockEmbedder(dims=384)

        vec1 = embedder.embed_one("text one")
        vec2 = embedder.embed_one("text two")

        assert not (vec1 == vec2).all()

    def test_embed_batch(self) -> None:
        """Test batch embedding."""
        embedder = MockEmbedder(dims=128)
        texts = ["text one", "text two", "text three"]

        vecs = embedder.embed(texts)

        assert len(vecs) == 3
        for vec in vecs:
            assert vec.shape == (128,)

    def test_caching(self) -> None:
        """Test that embeddings are cached."""
        embedder = MockEmbedder(dims=384)

        embedder.embed_one("cached text")
        assert "cached text" not in embedder._cache  # Key is hash, not text
        assert len(embedder._cache) == 1


class TestMemoryStore:
    """Tests for MemoryStore (mocked Redis)."""

    @pytest.fixture
    def mock_index(self) -> MagicMock:
        """Create a mock SearchIndex."""
        index = MagicMock()
        index.exists.return_value = True
        index.query.return_value = []
        index.load.return_value = ["memory:test-id"]
        return index

    @pytest.fixture
    def store(self, mock_index: MagicMock) -> MemoryStore:
        """Create a MemoryStore with mocked index."""
        with patch("agentic_curator.memory.SearchIndex") as mock_search_index:
            mock_search_index.from_dict.return_value = mock_index
            store = MemoryStore(redis_url="redis://localhost:6379")
            store._index = mock_index
            store._initialized = True
            return store

    def test_upsert_creates_entry(self, store: MemoryStore, mock_index: MagicMock) -> None:
        """Test upserting a memory entry."""
        entry = MemoryEntry(
            summary="Test memory",
            details="Test details",
            user_id="U123",
        )

        result = store.upsert(entry)

        assert result == entry.memory_id
        mock_index.load.assert_called_once()
        call_args = mock_index.load.call_args
        data = call_args[0][0][0]
        assert data["summary"] == "Test memory"
        assert data["details"] == "Test details"
        assert data["user_id"] == "U123"

    def test_upsert_batch(self, store: MemoryStore, mock_index: MagicMock) -> None:
        """Test batch upserting memory entries."""
        entries = [
            MemoryEntry(summary="Memory 1"),
            MemoryEntry(summary="Memory 2"),
            MemoryEntry(summary="Memory 3"),
        ]

        mock_index.load.return_value = [f"memory:{e.memory_id}" for e in entries]
        result = store.upsert_batch(entries)

        assert len(result) == 3
        mock_index.load.assert_called_once()
        call_args = mock_index.load.call_args
        data = call_args[0][0]
        assert len(data) == 3

    def test_upsert_batch_empty(self, store: MemoryStore, mock_index: MagicMock) -> None:
        """Test batch upserting with empty list."""
        result = store.upsert_batch([])

        assert result == []
        mock_index.load.assert_not_called()

    def test_query_returns_entries(self, store: MemoryStore, mock_index: MagicMock) -> None:
        """Test querying memories."""
        mock_index.query.return_value = [
            {
                "memory_id": "test-id-1",
                "summary": "Found memory",
                "details": "Details",
                "user_id": "U123",
                "channel_id": "C456",
                "thread_ts": "1234567890.123456",
                "source": "conversation",
                "status": "active",
                "task_type": "general",
                "created_at": 1000.0,
                "vector_distance": 0.1,
            }
        ]

        results = store.query("test query", user_id="U123")

        assert len(results) == 1
        assert results[0].summary == "Found memory"
        assert results[0].user_id == "U123"
        assert results[0].score == pytest.approx(0.9)  # 1.0 - 0.1

    def test_query_with_filters(self, store: MemoryStore, mock_index: MagicMock) -> None:
        """Test querying with filters."""
        mock_index.query.return_value = []

        store.query(
            "test query",
            user_id="U123",
            channel_id="C456",
            status="active",
            task_type="task",
            top_k=10,
        )

        mock_index.query.assert_called_once()
        # Verify a VectorQuery was passed
        call_args = mock_index.query.call_args
        query = call_args[0][0]
        assert isinstance(query, VectorQuery)

    def test_delete(self, store: MemoryStore, mock_index: MagicMock) -> None:
        """Test deleting a memory."""
        result = store.delete("test-id")

        assert result is True
        mock_index.client.delete.assert_called_once_with("memory:test-id")

    def test_delete_not_found(self, store: MemoryStore, mock_index: MagicMock) -> None:
        """Test deleting non-existent memory."""
        mock_index.client.delete.side_effect = Exception("Not found")

        result = store.delete("nonexistent")

        assert result is False


class TestGenerateMemoryCache:
    """Tests for memory cache file generation."""

    def test_generates_file(self) -> None:
        """Test that memory cache file is generated."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "memory_cache.md"
            memories = [
                MemoryEntry(
                    summary="Test memory",
                    details="Test details",
                    created_at=datetime(2024, 1, 15, 10, 30).timestamp(),
                    score=0.85,
                ),
            ]

            result = generate_memory_cache(
                query_text="test query",
                memories=memories,
                output_path=output_path,
            )

            assert result == output_path
            assert output_path.exists()
            content = output_path.read_text()
            assert "# Memory Cache" in content
            assert "test query" in content
            assert "Test memory" in content

    def test_empty_memories(self) -> None:
        """Test generation with no memories."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "memory_cache.md"

            generate_memory_cache(
                query_text="test query",
                memories=[],
                output_path=output_path,
            )

            content = output_path.read_text()
            assert "No relevant memories found" in content

    def test_includes_trigger_context(self) -> None:
        """Test that trigger context is included."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "memory_cache.md"

            generate_memory_cache(
                query_text="test query",
                memories=[],
                output_path=output_path,
                trigger_context="From user U123 in channel C456",
            )

            content = output_path.read_text()
            assert "From user U123 in channel C456" in content

    def test_memory_formatting(self) -> None:
        """Test that memories are formatted correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "memory_cache.md"
            memories = [
                MemoryEntry(
                    summary="Important task",
                    details="Must complete by Friday",
                    source="conversation",
                    status="active",
                    task_type="task",
                    channel_id="C123",
                    created_at=datetime(2024, 1, 15, 10, 30).timestamp(),
                    score=0.92,
                ),
            ]

            generate_memory_cache(
                query_text="task query",
                memories=memories,
                output_path=output_path,
            )

            content = output_path.read_text()
            assert "Important task" in content
            assert "Score:" in content
            assert "0.92" in content
            assert "Must complete by Friday" in content
            assert "Type:** task" in content
            assert "Channel:** C123" in content
