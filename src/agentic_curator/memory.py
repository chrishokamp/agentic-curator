"""Memory store for agent context using Redis with vector search."""

from __future__ import annotations

import hashlib
import logging
import os
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
from redisvl.index import SearchIndex
from redisvl.query import VectorQuery
from redisvl.query.filter import Tag

logger = logging.getLogger(__name__)

# Default Redis URL
DEFAULT_REDIS_URL = "redis://localhost:6379"

# Schema for memory storage
MEMORY_SCHEMA = {
    "index": {
        "name": "agent_memory",
        "prefix": "memory",
    },
    "fields": [
        {"name": "memory_id", "type": "tag"},
        {"name": "summary", "type": "text"},
        {"name": "details", "type": "text"},
        {"name": "user_id", "type": "tag"},
        {"name": "channel_id", "type": "tag"},
        {"name": "thread_ts", "type": "tag"},
        {"name": "source", "type": "tag"},
        {"name": "status", "type": "tag"},
        {"name": "task_type", "type": "tag"},
        {"name": "created_at", "type": "numeric"},
        {
            "name": "embedding",
            "type": "vector",
            "attrs": {
                "dims": 384,  # Common dimension for sentence-transformers
                "distance_metric": "cosine",
                "algorithm": "flat",
                "datatype": "float32",
            },
        },
    ],
}


@dataclass
class MemoryEntry:
    """A memory entry to be stored or retrieved."""

    summary: str
    details: str = ""
    user_id: str = ""
    channel_id: str = ""
    thread_ts: str = ""
    source: str = "conversation"
    status: str = "active"
    task_type: str = "general"
    memory_id: str = ""
    created_at: float = 0.0
    score: float = 0.0  # Vector similarity score (for search results)

    def __post_init__(self) -> None:
        if not self.memory_id:
            self.memory_id = str(uuid.uuid4())
        if not self.created_at:
            self.created_at = datetime.now().timestamp()


class MockEmbedder:
    """Mock embedder for development/testing when no real embedder is available."""

    def __init__(self, dims: int = 384) -> None:
        self.dims = dims
        self._cache: dict[str, np.ndarray] = {}

    def embed(self, texts: list[str]) -> list[np.ndarray]:
        """Generate deterministic mock embeddings based on text hash."""
        results = []
        for text in texts:
            text_hash = hashlib.md5(text.encode()).hexdigest()
            if text_hash in self._cache:
                results.append(self._cache[text_hash])
            else:
                np.random.seed(int(text_hash[:8], 16))
                vec = np.random.rand(self.dims).astype(np.float32)
                vec = vec / np.linalg.norm(vec)  # Normalize
                self._cache[text_hash] = vec
                results.append(vec)
        return results

    def embed_one(self, text: str) -> np.ndarray:
        """Embed a single text."""
        return self.embed([text])[0]


class SentenceTransformerEmbedder:
    """Real embedder using sentence-transformers for semantic embeddings."""

    def __init__(self, model_name: str = "all-MiniLM-L6-v2") -> None:
        """Initialize with a sentence-transformers model.

        Args:
            model_name: Model to use. Default 'all-MiniLM-L6-v2' is fast and 384 dims.
                        Other options: 'all-mpnet-base-v2' (768 dims, more accurate)
        """
        from sentence_transformers import SentenceTransformer

        self.model = SentenceTransformer(model_name)
        self.dims = self.model.get_sentence_embedding_dimension()
        logger.info(f"Loaded embedding model '{model_name}' with {self.dims} dimensions")

    def embed(self, texts: list[str]) -> list[np.ndarray]:
        """Generate embeddings for multiple texts."""
        embeddings = self.model.encode(texts, convert_to_numpy=True)
        return [emb.astype(np.float32) for emb in embeddings]

    def embed_one(self, text: str) -> np.ndarray:
        """Embed a single text."""
        return self.model.encode(text, convert_to_numpy=True).astype(np.float32)


def create_embedder(use_real: bool = True) -> MockEmbedder | SentenceTransformerEmbedder:
    """Create an embedder instance.

    Args:
        use_real: If True, use sentence-transformers. If False, use mock embedder.

    Returns:
        An embedder instance.
    """
    if use_real:
        try:
            return SentenceTransformerEmbedder()
        except Exception as e:
            logger.warning(f"Could not load sentence-transformers: {e}")
            logger.warning("Falling back to mock embedder")
            return MockEmbedder()
    return MockEmbedder()


class MemoryStore:
    """Redis-backed memory store with vector search capabilities."""

    def __init__(
        self,
        redis_url: str | None = None,
        embedder: Any | None = None,
        embedding_dims: int = 384,
        use_real_embedder: bool = True,
    ) -> None:
        """Initialize the memory store.

        Args:
            redis_url: Redis connection URL. Defaults to REDIS_URL env var.
            embedder: Optional embedder instance. If None, creates one.
            embedding_dims: Embedding dimensions (default 384 for sentence-transformers).
            use_real_embedder: If True and no embedder provided, use sentence-transformers.
        """
        self.redis_url = redis_url or os.getenv("REDIS_URL", DEFAULT_REDIS_URL)

        # Create embedder if not provided
        if embedder is None:
            self._embedder = create_embedder(use_real=use_real_embedder)
        else:
            self._embedder = embedder

        # Get actual embedding dimensions from embedder
        self.embedding_dims = getattr(self._embedder, "dims", embedding_dims)

        # Update schema with correct dimensions
        schema = MEMORY_SCHEMA.copy()
        schema["fields"] = [
            f if f["name"] != "embedding" else {
                **f,
                "attrs": {**f["attrs"], "dims": self.embedding_dims},
            }
            for f in MEMORY_SCHEMA["fields"]
        ]

        self._index: SearchIndex | None = None
        self._schema = schema
        self._initialized = False

    def _get_index(self) -> SearchIndex:
        """Get or create the search index."""
        if self._index is None:
            self._index = SearchIndex.from_dict(
                self._schema,
                redis_url=self.redis_url,
                validate_on_load=False,
            )
        return self._index

    def ensure_index(self) -> None:
        """Ensure the index exists, creating it if necessary."""
        if self._initialized:
            return

        index = self._get_index()
        try:
            if not index.exists():
                index.create()
                logger.info("Created memory index")
            else:
                logger.debug("Memory index already exists")
            self._initialized = True
        except Exception as e:
            logger.warning(f"Could not create/verify index: {e}")
            raise

    def _embed_text(self, text: str) -> bytes:
        """Generate embedding for text."""
        vec = self._embedder.embed_one(text)
        return vec.astype(np.float32).tobytes()

    def _embed_texts(self, texts: list[str]) -> list[bytes]:
        """Generate embeddings for multiple texts."""
        vecs = self._embedder.embed(texts)
        return [v.astype(np.float32).tobytes() for v in vecs]

    def upsert(self, entry: MemoryEntry) -> str:
        """Store or update a memory entry.

        Args:
            entry: The memory entry to store.

        Returns:
            The memory_id of the stored entry.
        """
        self.ensure_index()
        index = self._get_index()

        # Create embedding from summary + details
        embed_text = f"{entry.summary} {entry.details}".strip()
        embedding = self._embed_text(embed_text)

        data = {
            "memory_id": entry.memory_id,
            "summary": entry.summary,
            "details": entry.details,
            "user_id": entry.user_id,
            "channel_id": entry.channel_id,
            "thread_ts": entry.thread_ts,
            "source": entry.source,
            "status": entry.status,
            "task_type": entry.task_type,
            "created_at": entry.created_at,
            "embedding": embedding,
        }

        index.load([data], keys=[f"memory:{entry.memory_id}"])
        logger.debug(f"Stored memory {entry.memory_id}: {entry.summary[:50]}...")
        return entry.memory_id

    def upsert_batch(self, entries: list[MemoryEntry]) -> list[str]:
        """Store multiple memory entries efficiently.

        Args:
            entries: List of memory entries to store.

        Returns:
            List of memory_ids for stored entries.
        """
        if not entries:
            return []

        self.ensure_index()
        index = self._get_index()

        # Batch embed all texts
        embed_texts = [f"{e.summary} {e.details}".strip() for e in entries]
        embeddings = self._embed_texts(embed_texts)

        data = []
        keys = []
        for entry, embedding in zip(entries, embeddings):
            data.append({
                "memory_id": entry.memory_id,
                "summary": entry.summary,
                "details": entry.details,
                "user_id": entry.user_id,
                "channel_id": entry.channel_id,
                "thread_ts": entry.thread_ts,
                "source": entry.source,
                "status": entry.status,
                "task_type": entry.task_type,
                "created_at": entry.created_at,
                "embedding": embedding,
            })
            keys.append(f"memory:{entry.memory_id}")

        index.load(data, keys=keys)
        logger.info(f"Stored {len(entries)} memories")
        return [e.memory_id for e in entries]

    def query(
        self,
        text: str,
        user_id: str | None = None,
        channel_id: str | None = None,
        thread_ts: str | None = None,
        status: str | None = None,
        task_type: str | None = None,
        top_k: int = 5,
    ) -> list[MemoryEntry]:
        """Search for similar memories.

        Args:
            text: Query text to search for.
            user_id: Optional filter by user.
            channel_id: Optional filter by channel.
            thread_ts: Optional filter by thread.
            status: Optional filter by status.
            task_type: Optional filter by task type.
            top_k: Number of results to return.

        Returns:
            List of matching MemoryEntry objects with scores.
        """
        self.ensure_index()
        index = self._get_index()

        # Generate query embedding
        vec = self._embedder.embed_one(text)

        # Build filter expression
        filters = []
        if user_id:
            filters.append(Tag("user_id") == user_id)
        if channel_id:
            filters.append(Tag("channel_id") == channel_id)
        if thread_ts:
            filters.append(Tag("thread_ts") == thread_ts)
        if status:
            filters.append(Tag("status") == status)
        if task_type:
            filters.append(Tag("task_type") == task_type)

        filter_expression = None
        if filters:
            filter_expression = filters[0]
            for f in filters[1:]:
                filter_expression = filter_expression & f

        query = VectorQuery(
            vector=vec.tolist(),
            vector_field_name="embedding",
            return_fields=[
                "memory_id",
                "summary",
                "details",
                "user_id",
                "channel_id",
                "thread_ts",
                "source",
                "status",
                "task_type",
                "created_at",
                "vector_distance",
            ],
            num_results=top_k,
            filter_expression=filter_expression,
        )

        results = index.query(query)

        entries = []
        for r in results:
            try:
                entry = MemoryEntry(
                    memory_id=r.get("memory_id", ""),
                    summary=r.get("summary", ""),
                    details=r.get("details", ""),
                    user_id=r.get("user_id", ""),
                    channel_id=r.get("channel_id", ""),
                    thread_ts=r.get("thread_ts", ""),
                    source=r.get("source", ""),
                    status=r.get("status", ""),
                    task_type=r.get("task_type", ""),
                    created_at=float(r.get("created_at", 0)),
                    # Convert distance to similarity score
                    score=1.0 - float(r.get("vector_distance", 1.0)),
                )
                entries.append(entry)
            except Exception as e:
                logger.warning(f"Error parsing memory result: {e}")

        return entries

    def delete(self, memory_id: str) -> bool:
        """Delete a memory entry.

        Args:
            memory_id: The ID of the memory to delete.

        Returns:
            True if deleted, False if not found.
        """
        self.ensure_index()
        index = self._get_index()

        try:
            index.client.delete(f"memory:{memory_id}")
            logger.debug(f"Deleted memory {memory_id}")
            return True
        except Exception as e:
            logger.warning(f"Could not delete memory {memory_id}: {e}")
            return False

    def clear_all(self) -> None:
        """Clear all memories from the index (use with caution)."""
        self.ensure_index()
        index = self._get_index()

        try:
            # Drop and recreate the index
            index.delete(drop=True)
            index.create()
            logger.info("Cleared all memories")
        except Exception as e:
            logger.warning(f"Could not clear memories: {e}")
            raise

    def store_message(
        self,
        text: str,
        user_id: str = "",
        channel_id: str = "",
        thread_ts: str = "",
        response: str = "",
    ) -> str:
        """Store a message and optionally its response as a memory.

        This is a convenience method for storing conversation messages.

        Args:
            text: The message text (user's message).
            user_id: Slack user ID.
            channel_id: Slack channel ID.
            thread_ts: Thread timestamp.
            response: Optional agent response to include.

        Returns:
            The memory_id of the stored entry.
        """
        # Create a summary from the message
        summary = text[:200] if len(text) <= 200 else text[:197] + "..."

        # Include response in details if provided
        details = ""
        if response:
            details = f"Response: {response[:500]}"

        entry = MemoryEntry(
            summary=summary,
            details=details,
            user_id=user_id,
            channel_id=channel_id,
            thread_ts=thread_ts,
            source="conversation",
            status="active",
            task_type="message",
        )

        return self.upsert(entry)


def generate_memory_cache(
    query_text: str,
    memories: list[MemoryEntry],
    output_path: Path | str,
    trigger_context: str = "",
) -> Path:
    """Generate a memory_cache.md file for Claude to read.

    Args:
        query_text: The triggering message/query.
        memories: List of retrieved memories.
        output_path: Path to write the cache file.
        trigger_context: Additional context about the trigger.

    Returns:
        Path to the generated file.
    """
    output_path = Path(output_path)

    lines = [
        "# Memory Cache",
        "",
        "This file contains relevant memories retrieved for the current request.",
        "Consult this information before responding.",
        "",
        "## Trigger Context",
        "",
        f"**Query:** {query_text}",
    ]

    if trigger_context:
        lines.append(f"**Context:** {trigger_context}")

    lines.extend([
        "",
        "## Retrieved Memories",
        "",
    ])

    if not memories:
        lines.append("*No relevant memories found.*")
    else:
        for i, mem in enumerate(memories, 1):
            created = datetime.fromtimestamp(mem.created_at).strftime("%Y-%m-%d %H:%M")
            lines.extend([
                f"### {i}. {mem.summary}",
                "",
                f"- **Score:** {mem.score:.2f}",
                f"- **Created:** {created}",
                f"- **Source:** {mem.source}",
                f"- **Status:** {mem.status}",
            ])
            if mem.task_type != "general":
                lines.append(f"- **Type:** {mem.task_type}")
            if mem.channel_id:
                lines.append(f"- **Channel:** {mem.channel_id}")
            if mem.details:
                lines.extend([
                    "",
                    "**Details:**",
                    mem.details,
                ])
            lines.append("")

    lines.extend([
        "---",
        "",
        "*Note: Memories are ranked by relevance. Higher scores indicate closer semantic match.*",
    ])

    content = "\n".join(lines)
    output_path.write_text(content)
    logger.debug(f"Generated memory cache at {output_path}")

    return output_path
