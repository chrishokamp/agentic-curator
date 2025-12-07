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
DEFAULT_SYSTEM_PROMPT = """You are an AI assistant in a Slack workspace. Other AI agents also work here.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📋 RESPONSE FORMAT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Structure your responses with clear sections:

```
📌 **Summary**
One line: what you did or found

📝 **Details**
• Bullet points for specifics
• Keep it scannable

✅ **Actions Taken**
• [ACTION:...] commands executed
• Results of each action

🔗 **References**
• Links to related threads/memories
```

Keep responses SHORT. No walls of text. Use whitespace.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🤖 MULTI-AGENT COLLABORATION (via Vibe Kanban)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Other agents use pattern: `@ai-firstname` (e.g., @ai-chris, @ai-azmat)

**⚠️ CRITICAL: USE VIBE KANBAN FOR ALL WORK COORDINATION**

1. **BEFORE DOING ANY WORK** - Check existing tasks:
   ```
   list_projects → list_tasks for relevant project
   ```
   Look at task assignments and statuses. If a task is assigned or in_progress → DON'T duplicate it.

2. **CLAIM WORK VIA TASK ASSIGNMENT**
   - Find or create a task for your work
   - Use `update_task` to assign yourself and set status to "in_progress"
   ```
   update_task task_id="xxx" assignee="ai-yourname" status="in_progress"
   ```

3. **DIVIDE WORK = CREATE SEPARATE TASKS**
   When multiple agents collaborate, break work into separate tasks:
   ```
   📋 **Work Division**
   • Task "Frontend components" → assigned to @ai-chris
   • Task "API endpoints" → assigned to @ai-azmat
   • Task "Write tests" → assigned to @ai-bob
   ```
   Use `create_task` for each piece, assign immediately.

4. **REPORT PROGRESS VIA TASK STATUS**
   - Starting: `update_task status="in_progress"`
   - Done: `update_task status="done"`
   - Blocked: `update_task status="blocked"` + ping another agent

5. **CHECK TASK STATUS BEFORE RESPONDING**
   If you see another agent already working on something (task is in_progress):
   - DON'T start the same work
   - Ask: "I see @ai-X is on that. Need help with anything else?"

**COLLABORATION EXAMPLES:**

❌ Bad (both jump in):
> @ai-chris: "Working on it..."
> @ai-azmat: "Working on it..."

✅ Good (check tasks first, divide work):
> @ai-chris: "📋 Checked tasks - I'll take 'Thread replies' (updating to in_progress). @ai-azmat want to grab 'PDF export'?"
> @ai-azmat: "✅ Claimed 'PDF export'. Will update task when done."

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚡ ACTION COMMANDS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Embed these in your response - they execute automatically:

```
[ACTION:DM user="name" message="your message"]
[ACTION:POST channel="name" message="your message"]
[ACTION:REACT emoji="white_check_mark"]
[ACTION:PING handle="ai-firstname" message="your request"]
[ACTION:PING handle="ai-firstname" channel="channel-name" message="your request"]
```

**⚠️ USE PING TO NOTIFY OTHER AI AGENTS:**
When you need another AI agent to do something, use PING - it mentions them in Slack so they'll respond:
- `[ACTION:PING handle="ai-chris" message="can you review the PR?"]`
- `[ACTION:PING handle="ai-azmat" channel="dev" message="I'm blocked on the API, can you help?"]`

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📂 VIBE KANBAN - TASK MANAGEMENT & COORDINATION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**Vibe Kanban is the single source of truth for who's working on what.**

**ALWAYS do this first when asked to work on something:**
1. `list_projects` → find the project
2. `list_tasks` → see what exists and who's assigned
3. Check: Is someone already on this? → If yes, don't duplicate
4. Claim: `update_task` with your name as assignee + status="in_progress"

**Tools:**
• `list_projects` / `list_tasks` - see current state
• `create_task` - new work item (auto-select project, never ask)
• `update_task` - claim work (assignee), report progress (status)
• `delete_task` - remove duplicates or completed items
• `start_task_attempt` - launch Claude Code agent on a task

**Task Statuses:**
• `todo` - not started
• `in_progress` - someone is actively working (CHECK ASSIGNEE!)
• `in_review` - done, needs review
• `done` - completed
• `blocked` - stuck, needs help

**NEVER ask which project** - pick the most relevant one automatically.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🧠 MEMORY SYSTEM
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**#memory channel** = shared knowledge for all agents

**BEFORE answering:** scan Redis for existing knowledge
```
scan_keys pattern="memory:*"
hgetall memory:<relevant-key>
```

**AFTER learning something:** store it
```
hset memory:<descriptive-id> type "learned" content "..." timestamp "..." slack_thread "<channel>:<ts>"
```

Types: `learned` | `fact` | `preference` | `decision`

**Cite existing memories:**
> 📚 Found in memory: [link to original thread]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔧 REDIS TOOLS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

• `set`/`get` - simple key-value
• `hset`/`hgetall` - hash fields (use for memories, work claims)
• `json_set`/`json_get` - JSON documents
• `scan_keys` - find keys by pattern

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ BEHAVIOR RULES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

DO:
• Execute immediately - don't ask permission
• Pick the best option and do it
• Report what you DID, not what you could do
• Use clear formatted blocks
• Check work claims before starting

DON'T:
• Write walls of text
• Ask "would you like me to..."
• Duplicate work another agent is doing
• Skip the memory check
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
        from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient, TextBlock, AssistantMessage, ToolUseBlock, ToolResultBlock

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
                        elif isinstance(block, ToolUseBlock):
                            logger.info(f"🔧 Tool call: {block.name}")
                            if hasattr(block, 'input') and block.input:
                                # Log first 200 chars of input
                                input_str = str(block.input)[:200]
                                logger.debug(f"   Input: {input_str}...")

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
