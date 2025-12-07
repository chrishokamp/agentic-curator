"""Full Vibe Kanban workflow test - from Slack message to launching AI agent.

This test demonstrates the complete workflow:
1. User requests a feature in Slack
2. Agent creates a task in Vibe Kanban
3. Agent can start an AI coding agent to work on the task

Prerequisites:
    - Redis Stack running: docker run -d --name redis-stack -p 6379:6379 redis/redis-stack:latest
    - Vibe Kanban running: npx vibe-kanban (for the UI)

Vibe Kanban MCP Tools (from task_server.rs):
    - list_projects: {} -> {projects: [...], count: N}
    - list_tasks: {project_id, status?, limit?} -> {tasks: [...], count: N}
    - create_task: {project_id, title, description?} -> {task_id}
    - get_task: {task_id} -> TaskDetails
    - update_task: {task_id, title?, description?, status?} -> TaskDetails
    - delete_task: {task_id} -> success
    - start_task_attempt: {task_id, executor, base_branch, variant?} -> {task_id, attempt_id}
    - get_context: {} -> context (if in task attempt)

Executors: CLAUDE_CODE, CODEX, GEMINI, CURSOR_AGENT, OPENCODE
Status values: todo, inprogress, inreview, done, cancelled
"""

from __future__ import annotations

import asyncio

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

SYSTEM_PROMPT = """You are an AI assistant integrated with Slack that manages coding tasks.

## Vibe Kanban Tools

### Project & Task Management
- `list_projects` - List all projects
- `list_tasks` - List tasks (params: project_id, status?, limit?)
- `create_task` - Create task (params: project_id, title, description?)
- `get_task` - Get details (params: task_id)
- `update_task` - Update task (params: task_id, title?, description?, status?)
- `delete_task` - Delete task (params: task_id)

### Starting AI Agents on Tasks
- `start_task_attempt` - Launch an AI agent to work on a task
  - task_id: The task UUID
  - executor: CLAUDE_CODE, CODEX, GEMINI, CURSOR_AGENT, or OPENCODE
  - base_branch: The git branch to base work on (e.g., 'main')

### Task Status Values
- todo, inprogress, inreview, done, cancelled

## Redis Tools
Store data with `hset`, `get`, `set` for tracking requests.

Be concise. When creating tasks, use clear titles and descriptions.
"""


async def run_command(message: str):
    """Run a command through the agent."""
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
        system_prompt=SYSTEM_PROMPT,
        allowed_tools=[
            "mcp__vibe_kanban__list_projects",
            "mcp__vibe_kanban__list_tasks",
            "mcp__vibe_kanban__create_task",
            "mcp__vibe_kanban__get_task",
            "mcp__vibe_kanban__update_task",
            "mcp__vibe_kanban__delete_task",
            "mcp__vibe_kanban__start_task_attempt",
            "mcp__redis__hset",
            "mcp__redis__hgetall",
        ],
    )

    print(f"\n{'='*70}")
    print(f"USER: {message}")
    print(f"{'='*70}")

    response = ""
    tools = []

    async for msg in query(prompt=message, options=options):
        if isinstance(msg, AssistantMessage):
            for block in msg.content:
                if isinstance(block, TextBlock):
                    response += block.text
                elif isinstance(block, ToolUseBlock):
                    tools.append({"name": block.name, "input": block.input})

    print(f"\nAGENT: {response}")
    print(f"\nTools: {[t['name'] for t in tools]}")
    return response, tools


async def main():
    print("\n" + "=" * 70)
    print("FULL VIBE KANBAN WORKFLOW TEST")
    print("=" * 70)

    # Step 1: List projects
    print("\n\n" + "-" * 70)
    print("STEP 1: List available projects")
    print("-" * 70)
    await run_command("What projects do we have?")

    # Step 2: Create a task
    print("\n\n" + "-" * 70)
    print("STEP 2: Create a task from a Slack feature request")
    print("-" * 70)
    await run_command("""
    Create a task in agentic-curator:

    Title: Add /task slash command for quick task creation
    Description: Implement a /task slash command that lets users quickly create Kanban tasks from Slack.
    Should parse format: /task [project] [title] - [description]
    """)

    # Step 3: List tasks to get the ID
    print("\n\n" + "-" * 70)
    print("STEP 3: List tasks to see what we have")
    print("-" * 70)
    await run_command("Show me all tasks in agentic-curator with their IDs")

    # Step 4: Start a task attempt (launch Claude Code on the task)
    print("\n\n" + "-" * 70)
    print("STEP 4: Start Claude Code working on the slash command task")
    print("-" * 70)
    await run_command("""
    Start Claude Code working on the '/task slash command' task.
    Use 'main' as the base branch.
    """)

    # Step 5: Check task status after starting
    print("\n\n" + "-" * 70)
    print("STEP 5: Check task status")
    print("-" * 70)
    await run_command("What's the status of the slash command task now?")

    print("\n\n" + "=" * 70)
    print("WORKFLOW COMPLETE")
    print("=" * 70)
    print("""
Summary of Slack commands that trigger Vibe Kanban:

1. LIST PROJECTS:
   "What projects do we have?"
   "Show me the kanban projects"

2. CREATE TASK:
   "Create a task in [project]: [title] - [description]"
   "Add a task for [feature request]"

3. LIST TASKS:
   "Show tasks in [project]"
   "What's on the backlog?"

4. UPDATE TASK:
   "Mark [task] as done"
   "Update [task] status to inprogress"

5. START AI AGENT:
   "Start Claude Code on [task] using main branch"
   "Have Gemini work on [task]"

Executors: CLAUDE_CODE, CODEX, GEMINI, CURSOR_AGENT, OPENCODE
""")


if __name__ == "__main__":
    asyncio.run(main())
