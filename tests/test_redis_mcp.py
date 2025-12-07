"""Tests for Redis MCP server integration.

These tests verify that the Redis MCP server is properly configured
and can perform basic operations through the Claude agent SDK.

Prerequisites:
    - Redis Stack running on localhost:6379 (use docker run -d --name redis-stack -p 6379:6379 redis/redis-stack:latest)
    - redis-mcp-server package available via uvx
"""

from __future__ import annotations

import asyncio
import json
import pytest

# Redis MCP server configuration for testing
REDIS_MCP_CONFIG = {
    "redis": {
        "command": "uvx",
        "args": [
            "--from",
            "redis-mcp-server@latest",
            "redis-mcp-server",
            "--url",
            "redis://localhost:6379/0",
        ],
    },
}


@pytest.fixture
def redis_mcp_servers():
    """Provide Redis MCP server configuration."""
    return REDIS_MCP_CONFIG


class TestRedisMCPTools:
    """Test Redis MCP tool availability and basic operations."""

    @pytest.mark.asyncio
    async def test_redis_mcp_string_operations(self, redis_mcp_servers):
        """Test basic string set/get operations via Claude agent."""
        from claude_agent_sdk import (
            AssistantMessage,
            ClaudeAgentOptions,
            TextBlock,
            ToolUseBlock,
            query,
        )

        options = ClaudeAgentOptions(
            mcp_servers=redis_mcp_servers,
            permission_mode="bypassPermissions",
            model="haiku",
            allowed_tools=[
                "mcp__redis__set",
                "mcp__redis__get",
                "mcp__redis__delete",
            ],
        )

        # Test setting a value
        response_text = ""
        tool_used = False
        async for msg in query(
            prompt="Use the Redis MCP tools to set a key 'test:greeting' to 'Hello from MCP test'. Then get it back to verify. Be concise.",
            options=options,
        ):
            if isinstance(msg, AssistantMessage):
                for block in msg.content:
                    if isinstance(block, TextBlock):
                        response_text += block.text
                    elif isinstance(block, ToolUseBlock):
                        tool_used = True

        assert tool_used, "Expected Redis MCP tools to be used"
        assert "Hello" in response_text or "set" in response_text.lower()

    @pytest.mark.asyncio
    async def test_redis_mcp_hash_operations(self, redis_mcp_servers):
        """Test hash operations for storing structured data."""
        from claude_agent_sdk import (
            AssistantMessage,
            ClaudeAgentOptions,
            TextBlock,
            ToolUseBlock,
            query,
        )

        options = ClaudeAgentOptions(
            mcp_servers=redis_mcp_servers,
            permission_mode="bypassPermissions",
            model="haiku",
            allowed_tools=[
                "mcp__redis__hset",
                "mcp__redis__hget",
                "mcp__redis__hgetall",
                "mcp__redis__hdel",
            ],
        )

        response_text = ""
        tool_used = False
        async for msg in query(
            prompt="Use Redis hash tools to store user:1 with fields name='Alice' and role='admin'. Then retrieve all fields. Be concise.",
            options=options,
        ):
            if isinstance(msg, AssistantMessage):
                for block in msg.content:
                    if isinstance(block, TextBlock):
                        response_text += block.text
                    elif isinstance(block, ToolUseBlock):
                        tool_used = True

        assert tool_used, "Expected Redis hash tools to be used"

    @pytest.mark.asyncio
    async def test_redis_mcp_vector_index_creation(self, redis_mcp_servers):
        """Test vector index creation for semantic search."""
        from claude_agent_sdk import (
            AssistantMessage,
            ClaudeAgentOptions,
            TextBlock,
            ToolUseBlock,
            query,
        )

        options = ClaudeAgentOptions(
            mcp_servers=redis_mcp_servers,
            permission_mode="bypassPermissions",
            model="haiku",
            allowed_tools=[
                "mcp__redis__create_vector_index_hash",
                "mcp__redis__get_indexes",
                "mcp__redis__get_index_info",
            ],
        )

        response_text = ""
        tool_used = False
        async for msg in query(
            prompt="Create a vector index called 'test_embeddings' with prefix 'doc:' for 1536-dimensional vectors using COSINE distance. Then list all indexes. Be concise.",
            options=options,
        ):
            if isinstance(msg, AssistantMessage):
                for block in msg.content:
                    if isinstance(block, TextBlock):
                        response_text += block.text
                    elif isinstance(block, ToolUseBlock):
                        tool_used = True

        assert tool_used, "Expected Redis vector index tools to be used"

    @pytest.mark.asyncio
    async def test_redis_mcp_list_tools(self, redis_mcp_servers):
        """Test that Claude can list available Redis MCP tools."""
        from claude_agent_sdk import (
            AssistantMessage,
            ClaudeAgentOptions,
            TextBlock,
            query,
        )

        options = ClaudeAgentOptions(
            mcp_servers=redis_mcp_servers,
            permission_mode="bypassPermissions",
            model="haiku",
        )

        response_text = ""
        async for msg in query(
            prompt="List all available Redis MCP tools you have access to. Just list the tool names.",
            options=options,
        ):
            if isinstance(msg, AssistantMessage):
                for block in msg.content:
                    if isinstance(block, TextBlock):
                        response_text += block.text

        # Check that key Redis tools are mentioned
        response_lower = response_text.lower()
        assert "redis" in response_lower, f"Expected Redis tools to be listed. Got: {response_text}"


class TestRedisMCPVectorSearch:
    """Test vector search capabilities."""

    @pytest.mark.asyncio
    async def test_store_and_search_vectors(self, redis_mcp_servers):
        """Test storing vectors and performing similarity search."""
        from claude_agent_sdk import (
            AssistantMessage,
            ClaudeAgentOptions,
            TextBlock,
            ToolUseBlock,
            query,
        )

        # First, ensure we have a vector index
        options = ClaudeAgentOptions(
            mcp_servers=redis_mcp_servers,
            permission_mode="bypassPermissions",
            model="haiku",
            allowed_tools=[
                "mcp__redis__create_vector_index_hash",
                "mcp__redis__set_vector_in_hash",
                "mcp__redis__vector_search_hash",
                "mcp__redis__hset",
                "mcp__redis__get_indexes",
            ],
        )

        # Create index and store a test vector
        async for msg in query(
            prompt="""Do the following steps:
1. Try to create a vector index called 'semantic_test' with prefix 'emb:' for 4-dimensional vectors (dim=4) using COSINE distance
2. Store a vector [0.1, 0.2, 0.3, 0.4] in hash key 'emb:doc1' with vector_field='embedding'
3. Store a vector [0.15, 0.25, 0.35, 0.45] in hash key 'emb:doc2' with vector_field='embedding'
Be concise and report what you did.""",
            options=options,
        ):
            pass  # Just execute, we'll verify in the next query

        # Now search for similar vectors
        response_text = ""
        async for msg in query(
            prompt="Search the 'semantic_test' index for vectors similar to [0.12, 0.22, 0.32, 0.42] returning top 2 results. Report the results.",
            options=options,
        ):
            if isinstance(msg, AssistantMessage):
                for block in msg.content:
                    if isinstance(block, TextBlock):
                        response_text += block.text

        # The search should return results
        assert len(response_text) > 0, "Expected search results"


if __name__ == "__main__":
    # Run a quick smoke test
    async def smoke_test():
        """Quick smoke test for Redis MCP integration."""
        from claude_agent_sdk import (
            AssistantMessage,
            ClaudeAgentOptions,
            TextBlock,
            query,
        )

        print("Testing Redis MCP integration...")

        options = ClaudeAgentOptions(
            mcp_servers=REDIS_MCP_CONFIG,
            permission_mode="bypassPermissions",
            model="haiku",
        )

        print("\n1. Listing available Redis tools...")
        async for msg in query(
            prompt="List all Redis MCP tools available to you. Be very brief.",
            options=options,
        ):
            if isinstance(msg, AssistantMessage):
                for block in msg.content:
                    if isinstance(block, TextBlock):
                        print(block.text)

        print("\n2. Testing basic set/get...")
        async for msg in query(
            prompt="Set Redis key 'smoke:test' to 'working' and get it back. Be very brief.",
            options=ClaudeAgentOptions(
                mcp_servers=REDIS_MCP_CONFIG,
                permission_mode="bypassPermissions",
                model="haiku",
                allowed_tools=["mcp__redis__set", "mcp__redis__get"],
            ),
        ):
            if isinstance(msg, AssistantMessage):
                for block in msg.content:
                    if isinstance(block, TextBlock):
                        print(block.text)

        print("\nSmoke test complete!")

    asyncio.run(smoke_test())
