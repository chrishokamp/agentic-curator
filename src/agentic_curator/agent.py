"""Claude Code agent integration."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

logger = logging.getLogger(__name__)

# Default system prompt with Slack-specific guidance
DEFAULT_SYSTEM_PROMPT = """You are a helpful AI assistant integrated with Slack.

## Response Style
- Be concise and direct
- Use bullet points for lists
- Don't over-explain - assume the user knows context
- For simple requests, just do it without asking for confirmation

## When to Ask Questions vs Just Do It

**Just do it** (no questions needed):
- "Create a task for X" → Create it in the most relevant project
- "List tasks/projects" → Show them
- "Update task X" → Make the update
- "What's the status of X" → Look it up and report

**Ask questions** when:
- Multiple projects exist AND user didn't specify which one
- Request is ambiguous about what they actually want
- Destructive action (delete) on something important

## MCP Tools Available

### Vibe Kanban - Task Management
Quick actions - just call the tools directly:
- `list_projects` → Shows all projects (use to find project_id)
- `list_tasks` → Tasks in a project (needs project_id)
- `create_task` → Create task (needs project_id, title; description optional)
- `update_task` → Update task (needs task_id)
- `delete_task` → Delete task (needs task_id)
- `start_task_attempt` → Launch AI agent (needs task_id, executor like CLAUDE_CODE, base_branch like main)

**Default project**: If user says "create a task" without specifying project, use "agentic-curator" if it exists.

### Redis - Data Storage
- `set`/`get` - Key-value storage
- `hset`/`hgetall` - Hash storage for structured data
- `json_set`/`json_get` - JSON documents

## Examples of Good Responses

User: "create a task to fix the login bug"
→ List projects, find agentic-curator, create task with title "Fix login bug", respond: "Created task: Fix login bug (id: abc123)"

User: "what tasks do we have?"
→ List projects, list tasks from main project, show brief summary

User: "start claude on the login task"
→ Find the task, call start_task_attempt with CLAUDE_CODE and main branch, confirm it started
"""


# Pre-approved MCP tools that don't require permission prompts
ALLOWED_MCP_TOOLS = [
    # Redis tools
    "mcp__redis__set",
    "mcp__redis__get",
    "mcp__redis__delete",
    "mcp__redis__expire",
    "mcp__redis__rename",
    "mcp__redis__type",
    "mcp__redis__hset",
    "mcp__redis__hget",
    "mcp__redis__hgetall",
    "mcp__redis__hdel",
    "mcp__redis__hexists",
    "mcp__redis__lpush",
    "mcp__redis__rpush",
    "mcp__redis__lpop",
    "mcp__redis__rpop",
    "mcp__redis__lrange",
    "mcp__redis__llen",
    "mcp__redis__sadd",
    "mcp__redis__srem",
    "mcp__redis__smembers",
    "mcp__redis__zadd",
    "mcp__redis__zrange",
    "mcp__redis__zrem",
    "mcp__redis__json_set",
    "mcp__redis__json_get",
    "mcp__redis__json_del",
    "mcp__redis__xadd",
    "mcp__redis__xrange",
    "mcp__redis__xdel",
    "mcp__redis__publish",
    "mcp__redis__subscribe",
    "mcp__redis__unsubscribe",
    "mcp__redis__scan_keys",
    "mcp__redis__scan_all_keys",
    "mcp__redis__dbsize",
    "mcp__redis__info",
    "mcp__redis__client_list",
    "mcp__redis__set_vector_in_hash",
    "mcp__redis__get_vector_from_hash",
    "mcp__redis__create_vector_index_hash",
    "mcp__redis__vector_search_hash",
    "mcp__redis__get_indexes",
    "mcp__redis__get_index_info",
    "mcp__redis__get_indexed_keys_number",
    "mcp__redis__search_redis_documents",
    # Vibe Kanban tools
    "mcp__vibe_kanban__list_projects",
    "mcp__vibe_kanban__list_tasks",
    "mcp__vibe_kanban__create_task",
    "mcp__vibe_kanban__get_task",
    "mcp__vibe_kanban__update_task",
    "mcp__vibe_kanban__delete_task",
    "mcp__vibe_kanban__start_task_attempt",
    "mcp__vibe_kanban__get_context",
]


@dataclass
class AgentConfig:
    """Configuration for the Claude agent."""

    system_prompt: str = ""
    cwd: str | None = None
    permission_mode: str = "acceptEdits"
    model: str = "haiku"  # Use fast model by default
    mcp_servers: dict | None = None  # MCP server configurations
    allowed_tools: list[str] | None = None  # Pre-approved tools


@dataclass
class ClaudeAgent:
    """Claude Code agent wrapper."""

    config: AgentConfig
    _sessions: dict[str, str] = field(default_factory=dict)  # thread_id -> session_id

    async def respond(
        self,
        thread_id: str,
        message: str,
        context: list[tuple[str, str]] | None = None,
    ) -> str:
        """Generate a response using Claude Code agent.

        Args:
            thread_id: Slack thread identifier for session management
            message: The user's message
            context: Optional list of (role, content) tuples for context

        Returns:
            The agent's response text
        """
        # Import here to avoid import errors if claude-agent-sdk not installed
        from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient, TextBlock, AssistantMessage

        # Build the prompt with context
        prompt = message
        if context:
            context_str = "\n".join(
                f"{role}: {content}" for role, content in context
            )
            prompt = f"Previous conversation:\n{context_str}\n\nUser: {message}"

        # Combine default prompt with user-provided prompt
        system_prompt = DEFAULT_SYSTEM_PROMPT
        if self.config.system_prompt:
            system_prompt = f"{DEFAULT_SYSTEM_PROMPT}\n\n{self.config.system_prompt}"

        # Use configured allowed_tools or default MCP tools
        allowed_tools = self.config.allowed_tools or ALLOWED_MCP_TOOLS

        # Configure the agent
        options = ClaudeAgentOptions(
            system_prompt=system_prompt,
            cwd=self.config.cwd,
            permission_mode=self.config.permission_mode,  # type: ignore
            model=self.config.model,
            mcp_servers=self.config.mcp_servers or {},
            allowed_tools=allowed_tools,
        )

        # Check if we have an existing session for this thread
        session_id = self._sessions.get(thread_id)
        if session_id:
            options.resume = session_id

        # Run the agent
        response_text = ""

        async with ClaudeSDKClient(options=options) as client:
            await client.query(prompt)

            async for msg in client.receive_response():
                if isinstance(msg, AssistantMessage):
                    for block in msg.content:
                        if isinstance(block, TextBlock):
                            response_text += block.text

            # Get session ID for future resumption
            server_info = await client.get_server_info()
            if server_info and "session_id" in server_info:
                self._sessions[thread_id] = server_info["session_id"]

        return response_text.strip()

    async def respond_simple(self, message: str) -> str:
        """Simple one-shot response without thread tracking.

        Args:
            message: The user's message

        Returns:
            The agent's response text
        """
        from claude_agent_sdk import query, ClaudeAgentOptions, AssistantMessage, TextBlock

        # Combine default prompt with user-provided prompt
        system_prompt = DEFAULT_SYSTEM_PROMPT
        if self.config.system_prompt:
            system_prompt = f"{DEFAULT_SYSTEM_PROMPT}\n\n{self.config.system_prompt}"

        # Use configured allowed_tools or default MCP tools
        allowed_tools = self.config.allowed_tools or ALLOWED_MCP_TOOLS

        options = ClaudeAgentOptions(
            system_prompt=system_prompt,
            cwd=self.config.cwd,
            permission_mode=self.config.permission_mode,  # type: ignore
            model=self.config.model,
            mcp_servers=self.config.mcp_servers or {},
            allowed_tools=allowed_tools,
        )

        response_text = ""
        async for msg in query(prompt=message, options=options):
            if isinstance(msg, AssistantMessage):
                for block in msg.content:
                    if isinstance(block, TextBlock):
                        response_text += block.text

        return response_text.strip()
