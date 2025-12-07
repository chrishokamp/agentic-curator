"""Test triggering Vibe Kanban tasks via simulated Slack messages.

This demonstrates how the Slack agent can create and manage Kanban tasks
from natural language conversations.

Prerequisites:
    - Redis Stack running: docker run -d --name redis-stack -p 6379:6379 redis/redis-stack:latest
    - Vibe Kanban running: npx vibe-kanban (for the UI at localhost:5173)
"""

from __future__ import annotations

import asyncio

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
    "vibe_kanban": {
        "command": "npx",
        "args": ["-y", "vibe-kanban@latest", "--mcp"],
    },
}

# System prompt that enables Slack-to-Kanban workflows
SLACK_KANBAN_SYSTEM_PROMPT = """You are an AI assistant integrated with Slack that can manage tasks.

## Your Capabilities

### Vibe Kanban (Task Management)
You can create, view, and manage tasks using Vibe Kanban:
- `list_projects` - See all available projects
- `list_tasks` - View tasks in a project (params: project_id, status?, limit?)
- `create_task` - Create a new task (params: project_id, title, description?)
- `get_task` - Get task details (params: task_id)
- `update_task` - Update a task (params: task_id, title?, description?, status?)
- `delete_task` - Delete a task (params: task_id)
- `start_task_attempt` - Start an AI agent working on a task (params: task_id, executor, base_branch)

### Redis (Data Storage)
You can store and retrieve data for tracking conversations and requests.

## Task Workflow
When users ask you to create tasks or track work:
1. Use `list_projects` to find the right project
2. Use `create_task` with the project_id, a clear title, and description
3. Confirm the task was created with the task ID

## Status Values
Tasks can have these statuses: Ready, InProgress, Done, Blocked

Be helpful and concise in your responses.
"""


async def simulate_slack_command(message: str, verbose: bool = True):
    """Simulate a Slack message and get the agent's response."""
    from claude_agent_sdk import (
        AssistantMessage,
        ClaudeAgentOptions,
        TextBlock,
        ToolUseBlock,
        query,
    )

    options = ClaudeAgentOptions(
        mcp_servers=MCP_SERVERS,
        permission_mode="bypassPermissions",
        model="haiku",
        system_prompt=SLACK_KANBAN_SYSTEM_PROMPT,
        allowed_tools=[
            # Vibe Kanban tools
            "mcp__vibe_kanban__list_projects",
            "mcp__vibe_kanban__list_tasks",
            "mcp__vibe_kanban__create_task",
            "mcp__vibe_kanban__get_task",
            "mcp__vibe_kanban__update_task",
            "mcp__vibe_kanban__delete_task",
            "mcp__vibe_kanban__start_task_attempt",
            # Redis tools
            "mcp__redis__set",
            "mcp__redis__get",
            "mcp__redis__hset",
            "mcp__redis__hgetall",
        ],
    )

    if verbose:
        print(f"\n{'='*60}")
        print(f"📨 SLACK MESSAGE:")
        print(f"{'='*60}")
        print(message)
        print(f"{'='*60}")
        print(f"🤖 AGENT RESPONSE:")
        print(f"{'='*60}")

    response = ""
    tools_used = []

    async for msg in query(prompt=message, options=options):
        if isinstance(msg, AssistantMessage):
            for block in msg.content:
                if isinstance(block, TextBlock):
                    response += block.text
                elif isinstance(block, ToolUseBlock):
                    tools_used.append({
                        "name": block.name,
                        "input": block.input,
                    })

    if verbose:
        print(response)
        print(f"\n📋 Tools used:")
        for tool in tools_used:
            print(f"   - {tool['name']}: {tool['input']}")

    return response, tools_used


async def main():
    """Run example Slack commands that trigger Vibe Kanban."""

    print("\n" + "=" * 70)
    print("SLACK → VIBE KANBAN INTEGRATION EXAMPLES")
    print("=" * 70)

    # Example 1: List projects
    print("\n\n" + "🔹" * 30)
    print("EXAMPLE 1: List available projects")
    print("🔹" * 30)
    await simulate_slack_command(
        "What projects do we have in the kanban board?"
    )

    # Example 2: Create a task
    print("\n\n" + "🔹" * 30)
    print("EXAMPLE 2: Create a new task from a feature request")
    print("🔹" * 30)
    await simulate_slack_command(
        """Create a task in agentic-curator project:

Title: Implement webhook support for real-time Slack events
Description: Add webhook endpoint to receive Slack events in real-time instead of polling. Should support message events, reactions, and thread replies.
"""
    )

    # Example 3: List tasks
    print("\n\n" + "🔹" * 30)
    print("EXAMPLE 3: View tasks in a project")
    print("🔹" * 30)
    await simulate_slack_command(
        "Show me all tasks in the agentic-curator project"
    )

    # Example 4: Natural language task creation
    print("\n\n" + "🔹" * 30)
    print("EXAMPLE 4: Natural language task creation")
    print("🔹" * 30)
    await simulate_slack_command(
        "Hey, we need to add rate limiting to the API. Can you create a task for that in agentic-curator?"
    )

    # Example 5: Update task status
    print("\n\n" + "🔹" * 30)
    print("EXAMPLE 5: Update a task")
    print("🔹" * 30)
    response, tools = await simulate_slack_command(
        "List the tasks in agentic-curator and tell me their IDs"
    )

    # If we got tasks, try to update one
    if tools and any("list_tasks" in t["name"] for t in tools):
        print("\n\n" + "🔹" * 30)
        print("EXAMPLE 5b: Mark a task as in progress")
        print("🔹" * 30)
        await simulate_slack_command(
            "Update the webhook support task - mark it as InProgress and add to description: 'Started implementation on Dec 7'"
        )

    print("\n\n" + "=" * 70)
    print("✅ ALL EXAMPLES COMPLETED")
    print("=" * 70)
    print("\nYou can now use these patterns in real Slack conversations!")
    print("The agent will use Vibe Kanban MCP tools to manage tasks.")


if __name__ == "__main__":
    asyncio.run(main())
