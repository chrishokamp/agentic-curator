"""Claude Code agent integration."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

logger = logging.getLogger(__name__)


@dataclass
class AgentConfig:
    """Configuration for the Claude agent."""

    system_prompt: str = ""
    cwd: str | None = None
    permission_mode: str = "acceptEdits"


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
        from claude_agent_sdk import query, ClaudeAgentOptions, AssistantMessage, TextBlock

        options = ClaudeAgentOptions(
            system_prompt=self.config.system_prompt or None,
            cwd=self.config.cwd,
            permission_mode=self.config.permission_mode,  # type: ignore
        )

        response_text = ""
        async for msg in query(prompt=message, options=options):
            if isinstance(msg, AssistantMessage):
                for block in msg.content:
                    if isinstance(block, TextBlock):
                        response_text += block.text

        return response_text.strip()
