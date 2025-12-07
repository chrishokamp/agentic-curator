"""Claude Code agent integration."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# Default system prompt with Slack-specific guidance
DEFAULT_SYSTEM_PROMPT = """You are a helpful AI assistant integrated with Slack.

## Slack API Guidelines

When working with Slack data:

1. **Timestamps**: Slack uses Unix timestamps with microseconds (e.g., "1234567890.123456")
   - To convert to human-readable: `datetime.fromtimestamp(float(ts))`
   - When querying history, use `oldest` parameter with these timestamp strings
   - Thread replies share the parent's `thread_ts`

2. **Channel IDs**: Start with C (public), G (private), D (DM), or W (enterprise)

3. **User IDs**: Start with U or W, format like "U0A1VME86F5"

4. **Rate Limits**: Be mindful of Slack API rate limits (Tier 2-4)
   - Tier 2: ~20 requests/min (posting)
   - Tier 3: ~50 requests/min (history)

5. **Pagination**: Use cursor-based pagination for large result sets

Be concise in Slack responses. Use threads to keep conversations organized.
"""

# Memory-aware prompt extension
MEMORY_PROMPT_EXTENSION = """
## Memory System

Before responding, consult `memory_cache.md` in your working directory for relevant context.

### Response Format

You MUST respond with a JSON object in the following format:

```json
{
  "slack_reply": "Your response to the user goes here",
  "memory_entries": [
    {
      "summary": "Brief one-line summary of the memory",
      "details": "Longer description with context",
      "status": "active",
      "task_type": "general",
      "should_persist": true
    }
  ]
}
```

### Memory Entry Guidelines

Only create memory entries when you discover durable facts or commitments:
- User preferences or settings
- Important decisions made
- Commitments or promises (tasks, deadlines)
- Key facts about projects or people
- Technical context worth remembering

Do NOT create memory entries for:
- Trivial or ephemeral information
- Already-known context from memory_cache.md
- General knowledge or common facts

### Memory Fields

- `summary`: One-line summary (required)
- `details`: Full context and details (optional)
- `status`: "active", "completed", "archived" (default: "active")
- `task_type`: "general", "task", "preference", "decision", "fact" (default: "general")
- `should_persist`: boolean - set to false if uncertain about durability

If no memories should be created, use an empty array: `"memory_entries": []`
"""


@dataclass
class AgentResponse:
    """Parsed response from the Claude agent."""

    slack_reply: str
    memory_entries: list[dict[str, Any]] = field(default_factory=list)
    raw_response: str = ""


def parse_agent_response(raw_response: str) -> AgentResponse:
    """Parse the agent's JSON response.

    Args:
        raw_response: Raw text response from Claude.

    Returns:
        Parsed AgentResponse object.
    """
    # Try to find JSON in the response
    json_match = re.search(r'\{[\s\S]*\}', raw_response)

    if json_match:
        try:
            data = json.loads(json_match.group())
            return AgentResponse(
                slack_reply=data.get("slack_reply", raw_response),
                memory_entries=data.get("memory_entries", []),
                raw_response=raw_response,
            )
        except json.JSONDecodeError:
            logger.debug("Failed to parse JSON response, using raw text")

    # Fallback: treat entire response as slack_reply
    return AgentResponse(
        slack_reply=raw_response,
        memory_entries=[],
        raw_response=raw_response,
    )


@dataclass
class AgentConfig:
    """Configuration for the Claude agent."""

    system_prompt: str = ""
    cwd: str | None = None
    permission_mode: str = "acceptEdits"
    model: str = "haiku"  # Use fast model by default


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
        from claude_agent_sdk import (
            AssistantMessage,
            ClaudeAgentOptions,
            ClaudeSDKClient,
            TextBlock,
        )

        # Build the prompt with context
        prompt = message
        if context:
            context_str = "\n".join(
                f"{role}: {content}" for role, content in context
            )
            prompt = f"Previous context:\n{context_str}\n\nCurrent message: {message}"

        # Configure the agent
        options = ClaudeAgentOptions(
            system_prompt=self.config.system_prompt or None,
            cwd=self.config.cwd,
            permission_mode=self.config.permission_mode,  # type: ignore
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
        from claude_agent_sdk import AssistantMessage, ClaudeAgentOptions, TextBlock, query

        # Combine default prompt with user-provided prompt
        system_prompt = DEFAULT_SYSTEM_PROMPT
        if self.config.system_prompt:
            system_prompt = f"{DEFAULT_SYSTEM_PROMPT}\n\n{self.config.system_prompt}"

        options = ClaudeAgentOptions(
            system_prompt=system_prompt,
            cwd=self.config.cwd,
            permission_mode=self.config.permission_mode,  # type: ignore
            model=self.config.model,
        )

        response_text = ""
        async for msg in query(prompt=message, options=options):
            if isinstance(msg, AssistantMessage):
                for block in msg.content:
                    if isinstance(block, TextBlock):
                        response_text += block.text

        return response_text.strip()

    async def respond_with_memory(self, message: str) -> AgentResponse:
        """Response with memory extraction for structured storage.

        This method includes the memory prompt extension and parses
        the response to extract memory entries.

        Args:
            message: The user's message

        Returns:
            AgentResponse with slack_reply and memory_entries
        """
        from claude_agent_sdk import AssistantMessage, ClaudeAgentOptions, TextBlock, query

        # Combine default prompt with memory extension and user-provided prompt
        system_prompt = DEFAULT_SYSTEM_PROMPT + MEMORY_PROMPT_EXTENSION
        if self.config.system_prompt:
            system_prompt = f"{system_prompt}\n\n{self.config.system_prompt}"

        options = ClaudeAgentOptions(
            system_prompt=system_prompt,
            cwd=self.config.cwd,
            permission_mode=self.config.permission_mode,  # type: ignore
            model=self.config.model,
        )

        response_text = ""
        async for msg in query(prompt=message, options=options):
            if isinstance(msg, AssistantMessage):
                for block in msg.content:
                    if isinstance(block, TextBlock):
                        response_text += block.text

        raw_response = response_text.strip()
        return parse_agent_response(raw_response)
