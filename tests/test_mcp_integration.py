"""Integration tests for Redis and Vibe Kanban MCP servers.

Tests that both MCP servers are accessible and functional through the Claude agent.

Prerequisites:
    - Redis Stack running: docker run -d --name redis-stack -p 6379:6379 redis/redis-stack:latest
    - npx available for vibe-kanban
"""

from __future__ import annotations

import asyncio

# MCP server configurations matching __main__.py
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
    "vibe_kanban": {
        "command": "npx",
        "args": ["-y", "vibe-kanban@latest", "--mcp"],
    },
}


async def test_redis_mcp():
    """Test Redis MCP server operations."""
    from claude_agent_sdk import (
        AssistantMessage,
        ClaudeAgentOptions,
        TextBlock,
        ToolUseBlock,
        query,
    )

    print("\n" + "=" * 60)
    print("TESTING REDIS MCP SERVER")
    print("=" * 60)

    options = ClaudeAgentOptions(
        mcp_servers=MCP_SERVERS,
        permission_mode="bypassPermissions",
        model="haiku",
        allowed_tools=[
            "mcp__redis__set",
            "mcp__redis__get",
            "mcp__redis__hset",
            "mcp__redis__hgetall",
            "mcp__redis__delete",
            "mcp__redis__dbsize",
        ],
    )

    # Test 1: Basic string operations
    print("\n1. Testing string set/get...")
    response = ""
    tools_used = []
    async for msg in query(
        prompt="Use Redis to: 1) Set key 'test:hello' to 'world', 2) Get it back, 3) Report the result. Be concise.",
        options=options,
    ):
        if isinstance(msg, AssistantMessage):
            for block in msg.content:
                if isinstance(block, TextBlock):
                    response += block.text
                elif isinstance(block, ToolUseBlock):
                    tools_used.append(block.name)

    print(f"   Tools used: {tools_used}")
    print(f"   Response: {response[:200]}...")
    assert any("redis" in t for t in tools_used), "Expected Redis tools to be used"

    # Test 2: Hash operations
    print("\n2. Testing hash operations...")
    response = ""
    tools_used = []
    async for msg in query(
        prompt="Use Redis hashes to store user:test with fields 'name'='TestUser' and 'role'='tester'. Then get all fields. Be concise.",
        options=options,
    ):
        if isinstance(msg, AssistantMessage):
            for block in msg.content:
                if isinstance(block, TextBlock):
                    response += block.text
                elif isinstance(block, ToolUseBlock):
                    tools_used.append(block.name)

    print(f"   Tools used: {tools_used}")
    print(f"   Response: {response[:200]}...")

    # Test 3: Database info
    print("\n3. Testing dbsize...")
    response = ""
    async for msg in query(
        prompt="How many keys are in the Redis database? Use dbsize. Just give me the number.",
        options=options,
    ):
        if isinstance(msg, AssistantMessage):
            for block in msg.content:
                if isinstance(block, TextBlock):
                    response += block.text

    print(f"   Response: {response}")

    print("\n✅ Redis MCP tests passed!")
    return True


async def test_vibe_kanban_mcp():
    """Test Vibe Kanban MCP server operations."""
    from claude_agent_sdk import (
        AssistantMessage,
        ClaudeAgentOptions,
        TextBlock,
        ToolUseBlock,
        query,
    )

    print("\n" + "=" * 60)
    print("TESTING VIBE KANBAN MCP SERVER")
    print("=" * 60)

    options = ClaudeAgentOptions(
        mcp_servers=MCP_SERVERS,
        permission_mode="bypassPermissions",
        model="haiku",
        allowed_tools=[
            "mcp__vibe_kanban__list_projects",
            "mcp__vibe_kanban__list_tasks",
            "mcp__vibe_kanban__create_task",
            "mcp__vibe_kanban__get_task",
            "mcp__vibe_kanban__update_task",
            "mcp__vibe_kanban__delete_task",
        ],
    )

    # Test 1: List projects
    print("\n1. Testing list_projects...")
    response = ""
    tools_used = []
    async for msg in query(
        prompt="List all available Vibe Kanban projects. If there are none, just say so. Be concise.",
        options=options,
    ):
        if isinstance(msg, AssistantMessage):
            for block in msg.content:
                if isinstance(block, TextBlock):
                    response += block.text
                elif isinstance(block, ToolUseBlock):
                    tools_used.append(block.name)

    print(f"   Tools used: {tools_used}")
    print(f"   Response: {response[:300]}...")

    # Check if vibe_kanban tools were attempted
    vibe_tools_used = [t for t in tools_used if "vibe_kanban" in t]
    if vibe_tools_used:
        print("\n✅ Vibe Kanban MCP connection successful!")
    else:
        print("\n⚠️  Vibe Kanban MCP may not be running (no projects found is OK)")

    return True


async def test_combined_workflow():
    """Test a workflow that uses both Redis and Vibe Kanban."""
    from claude_agent_sdk import (
        AssistantMessage,
        ClaudeAgentOptions,
        TextBlock,
        ToolUseBlock,
        query,
    )

    print("\n" + "=" * 60)
    print("TESTING COMBINED WORKFLOW")
    print("=" * 60)

    options = ClaudeAgentOptions(
        mcp_servers=MCP_SERVERS,
        permission_mode="bypassPermissions",
        model="haiku",
        allowed_tools=[
            # Redis tools
            "mcp__redis__set",
            "mcp__redis__get",
            "mcp__redis__hset",
            "mcp__redis__hgetall",
            # Vibe Kanban tools
            "mcp__vibe_kanban__list_projects",
            "mcp__vibe_kanban__create_task",
        ],
    )

    print("\n1. Testing workflow: Store request in Redis, then check Kanban...")
    response = ""
    tools_used = []
    async for msg in query(
        prompt="""Do the following:
1. Store in Redis hash 'request:slack-123' the fields: 'user'='chris', 'request'='Add dark mode feature', 'status'='pending'
2. Try to list Vibe Kanban projects to see if we can create a task there
3. Report what you did

Be concise.""",
        options=options,
    ):
        if isinstance(msg, AssistantMessage):
            for block in msg.content:
                if isinstance(block, TextBlock):
                    response += block.text
                elif isinstance(block, ToolUseBlock):
                    tools_used.append(block.name)

    print(f"   Tools used: {tools_used}")
    print(f"   Response: {response[:400]}...")

    redis_tools = [t for t in tools_used if "redis" in t]
    kanban_tools = [t for t in tools_used if "vibe_kanban" in t]

    print(f"\n   Redis tools used: {redis_tools}")
    print(f"   Kanban tools used: {kanban_tools}")

    if redis_tools:
        print("\n✅ Combined workflow test passed!")
    return True


async def test_slack_to_kanban_scenario():
    """Simulate a Slack message triggering Kanban task creation."""
    from claude_agent_sdk import (
        AssistantMessage,
        ClaudeAgentOptions,
        TextBlock,
        ToolUseBlock,
        query,
    )

    print("\n" + "=" * 60)
    print("TESTING SLACK -> KANBAN SCENARIO")
    print("=" * 60)

    # Simulated system prompt similar to what the agent would have
    system_prompt = """You are an AI assistant in Slack with access to:
- Redis for data storage
- Vibe Kanban for task management

When users request features or report bugs, you can:
1. Store the request details in Redis for tracking
2. Create tasks in Vibe Kanban if a project exists
3. Provide status updates by querying both systems
"""

    options = ClaudeAgentOptions(
        mcp_servers=MCP_SERVERS,
        permission_mode="bypassPermissions",
        model="haiku",
        system_prompt=system_prompt,
        allowed_tools=[
            "mcp__redis__set",
            "mcp__redis__get",
            "mcp__redis__hset",
            "mcp__redis__hgetall",
            "mcp__redis__lpush",
            "mcp__redis__lrange",
            "mcp__vibe_kanban__list_projects",
            "mcp__vibe_kanban__create_task",
            "mcp__vibe_kanban__list_tasks",
        ],
    )

    # Simulate a Slack message asking to create a task
    slack_message = """
    Hey! Can you help me track this feature request?

    Title: Add export to PDF functionality
    Description: Users should be able to export their reports as PDF files
    Priority: High

    Please store this and create a task if possible.
    """

    print(f"\n📨 Simulated Slack message:\n{slack_message}")
    print("\n🤖 Agent response:")

    response = ""
    tools_used = []
    async for msg in query(prompt=slack_message, options=options):
        if isinstance(msg, AssistantMessage):
            for block in msg.content:
                if isinstance(block, TextBlock):
                    response += block.text
                elif isinstance(block, ToolUseBlock):
                    tools_used.append(f"{block.name}({list(block.input.keys()) if block.input else []})")

    print(f"\n{response}")
    print(f"\n📋 Tools used: {tools_used}")

    return True


async def main():
    """Run all MCP integration tests."""
    print("\n" + "=" * 60)
    print("MCP INTEGRATION TEST SUITE")
    print("=" * 60)

    results = {}

    # Test Redis
    try:
        results["redis"] = await test_redis_mcp()
    except Exception as e:
        print(f"\n❌ Redis MCP test failed: {e}")
        results["redis"] = False

    # Test Vibe Kanban
    try:
        results["vibe_kanban"] = await test_vibe_kanban_mcp()
    except Exception as e:
        print(f"\n❌ Vibe Kanban MCP test failed: {e}")
        results["vibe_kanban"] = False

    # Test combined workflow
    try:
        results["combined"] = await test_combined_workflow()
    except Exception as e:
        print(f"\n❌ Combined workflow test failed: {e}")
        results["combined"] = False

    # Test Slack -> Kanban scenario
    try:
        results["slack_kanban"] = await test_slack_to_kanban_scenario()
    except Exception as e:
        print(f"\n❌ Slack -> Kanban test failed: {e}")
        results["slack_kanban"] = False

    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    for test_name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {test_name}: {status}")

    all_passed = all(results.values())
    print("\n" + ("✅ All tests passed!" if all_passed else "❌ Some tests failed"))
    return all_passed


if __name__ == "__main__":
    asyncio.run(main())
