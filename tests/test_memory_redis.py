"""Test memory storage and retrieval via Redis MCP."""

from __future__ import annotations

import asyncio
import json

# MCP server configurations
MCP_SERVERS = {
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


async def test_store_memory():
    """Test storing a memory in Redis via MCP."""
    from claude_agent_sdk import (
        AssistantMessage,
        ClaudeAgentOptions,
        TextBlock,
        ToolUseBlock,
        query,
    )

    print("\n" + "=" * 60)
    print("TEST: Store Memory in Redis")
    print("=" * 60)

    options = ClaudeAgentOptions(
        mcp_servers=MCP_SERVERS,
        permission_mode="bypassPermissions",
        model="haiku",
        allowed_tools=[
            "mcp__redis__hset",
            "mcp__redis__hgetall",
            "mcp__redis__scan_keys",
            "mcp__redis__delete",
        ],
    )

    # Store a test memory
    memory_id = "test-memory-001"
    memory_data = {
        "id": memory_id,
        "content": "Redis MCP works for memory storage",
        "type": "learned",
        "agent": "test-agent",
        "timestamp": "2025-12-07T15:00:00Z",
        "tags": "redis,mcp,test",
    }

    prompt = f"""Store this memory in Redis:
Key: memory:{memory_id}
Fields to store using hset:
- id: {memory_data['id']}
- content: {memory_data['content']}
- type: {memory_data['type']}
- agent: {memory_data['agent']}
- timestamp: {memory_data['timestamp']}
- tags: {memory_data['tags']}

Use hset for each field. Be concise."""

    print(f"\nStoring memory: {memory_data['content']}")

    response = ""
    tools_used = []
    async for msg in query(prompt=prompt, options=options):
        if isinstance(msg, AssistantMessage):
            for block in msg.content:
                if isinstance(block, TextBlock):
                    response += block.text
                elif isinstance(block, ToolUseBlock):
                    tools_used.append(block.name)

    print(f"Tools used: {tools_used}")
    print(f"Response: {response[:200]}...")

    assert any("hset" in t for t in tools_used), "Expected hset to be used"
    print("✅ Memory stored successfully!")
    return memory_id


async def test_retrieve_memory(memory_id: str):
    """Test retrieving a memory from Redis via MCP."""
    from claude_agent_sdk import (
        AssistantMessage,
        ClaudeAgentOptions,
        TextBlock,
        ToolUseBlock,
        query,
    )

    print("\n" + "=" * 60)
    print("TEST: Retrieve Memory from Redis")
    print("=" * 60)

    options = ClaudeAgentOptions(
        mcp_servers=MCP_SERVERS,
        permission_mode="bypassPermissions",
        model="haiku",
        allowed_tools=[
            "mcp__redis__hgetall",
            "mcp__redis__scan_keys",
        ],
    )

    prompt = f"""Retrieve the memory stored at key "memory:{memory_id}" using hgetall.
Tell me what the content and type fields contain. Be concise."""

    print(f"\nRetrieving memory: memory:{memory_id}")

    response = ""
    tools_used = []
    async for msg in query(prompt=prompt, options=options):
        if isinstance(msg, AssistantMessage):
            for block in msg.content:
                if isinstance(block, TextBlock):
                    response += block.text
                elif isinstance(block, ToolUseBlock):
                    tools_used.append(block.name)

    print(f"Tools used: {tools_used}")
    print(f"Response: {response}")

    assert any("hgetall" in t for t in tools_used), "Expected hgetall to be used"
    assert "Redis MCP works" in response or "learned" in response.lower(), "Memory content should be retrieved"
    print("✅ Memory retrieved successfully!")


async def test_list_memories():
    """Test listing all memories from Redis."""
    from claude_agent_sdk import (
        AssistantMessage,
        ClaudeAgentOptions,
        TextBlock,
        ToolUseBlock,
        query,
    )

    print("\n" + "=" * 60)
    print("TEST: List All Memories")
    print("=" * 60)

    options = ClaudeAgentOptions(
        mcp_servers=MCP_SERVERS,
        permission_mode="bypassPermissions",
        model="haiku",
        allowed_tools=[
            "mcp__redis__scan_keys",
            "mcp__redis__hgetall",
        ],
    )

    prompt = """List all memory keys in Redis (pattern: memory:*) using scan_keys.
Then for the first one found, show its contents using hgetall. Be concise."""

    print("\nScanning for memories...")

    response = ""
    tools_used = []
    async for msg in query(prompt=prompt, options=options):
        if isinstance(msg, AssistantMessage):
            for block in msg.content:
                if isinstance(block, TextBlock):
                    response += block.text
                elif isinstance(block, ToolUseBlock):
                    tools_used.append(block.name)

    print(f"Tools used: {tools_used}")
    print(f"Response: {response[:300]}...")

    assert any("scan_keys" in t for t in tools_used), "Expected scan_keys to be used"
    print("✅ Memory listing works!")


async def test_memory_search_workflow():
    """Test a realistic memory search workflow."""
    from claude_agent_sdk import (
        AssistantMessage,
        ClaudeAgentOptions,
        TextBlock,
        ToolUseBlock,
        query,
    )

    print("\n" + "=" * 60)
    print("TEST: Memory Search Workflow")
    print("=" * 60)

    options = ClaudeAgentOptions(
        mcp_servers=MCP_SERVERS,
        permission_mode="bypassPermissions",
        model="haiku",
        allowed_tools=[
            "mcp__redis__hset",
            "mcp__redis__hgetall",
            "mcp__redis__scan_keys",
        ],
    )

    # First, store a few test memories
    memories = [
        {"id": "mem-deploy-1", "content": "deploy needs AWS_PROFILE=prod", "type": "learned", "tags": "deploy,aws"},
        {"id": "mem-api-1", "content": "API rate limit is 100 req/min", "type": "fact", "tags": "api,limits"},
        {"id": "mem-pref-1", "content": "user prefers bullet points", "type": "preference", "tags": "style"},
    ]

    print("\n1. Storing test memories...")
    for mem in memories:
        store_prompt = f"""Store in Redis key memory:{mem['id']}:
- id: {mem['id']}
- content: {mem['content']}
- type: {mem['type']}
- tags: {mem['tags']}
Be silent, just do it."""
        async for _ in query(prompt=store_prompt, options=options):
            pass
    print("   Done storing 3 memories.")

    # Now search for deployment-related memories
    print("\n2. Searching for deployment info...")
    search_prompt = """I need to deploy the app. Search Redis for any memories about deployment.
Use scan_keys with pattern memory:*deploy* or scan all memory:* keys and check their content.
Tell me what you find. Be concise."""

    response = ""
    async for msg in query(prompt=search_prompt, options=options):
        if isinstance(msg, AssistantMessage):
            for block in msg.content:
                if isinstance(block, TextBlock):
                    response += block.text

    print(f"   Search result: {response}")
    assert "AWS" in response or "deploy" in response.lower(), "Should find deployment memory"

    print("\n✅ Memory search workflow works!")


async def test_cleanup():
    """Clean up test memories."""
    from claude_agent_sdk import (
        ClaudeAgentOptions,
        query,
    )

    print("\n" + "=" * 60)
    print("CLEANUP: Removing test memories")
    print("=" * 60)

    options = ClaudeAgentOptions(
        mcp_servers=MCP_SERVERS,
        permission_mode="bypassPermissions",
        model="haiku",
        allowed_tools=["mcp__redis__delete", "mcp__redis__scan_keys"],
    )

    prompt = """Delete all test memories:
- memory:test-memory-001
- memory:mem-deploy-1
- memory:mem-api-1
- memory:mem-pref-1
Use delete for each. Be silent."""

    async for _ in query(prompt=prompt, options=options):
        pass

    print("✅ Cleanup complete!")


async def main():
    """Run all memory Redis tests."""
    print("\n" + "=" * 70)
    print("MEMORY REDIS MCP INTEGRATION TESTS")
    print("=" * 70)

    try:
        # Store a memory
        memory_id = await test_store_memory()

        # Retrieve it
        await test_retrieve_memory(memory_id)

        # List all memories
        await test_list_memories()

        # Full workflow test
        await test_memory_search_workflow()

        # Cleanup
        await test_cleanup()

        print("\n" + "=" * 70)
        print("✅ ALL MEMORY REDIS TESTS PASSED!")
        print("=" * 70)

    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        raise


if __name__ == "__main__":
    asyncio.run(main())
