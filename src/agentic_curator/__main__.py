"""Main entry point for the Agentic Curator Slack agent."""

from __future__ import annotations

import asyncio
import getpass
import logging
import os
import sys
from argparse import ArgumentParser

from .agent import AgentConfig, ClaudeAgent
from .auth import load_auth
from .poller import MessagePoller
from .slack_client import SlackClient

# Configure logging - only our modules, not third-party
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
# Silence noisy third-party loggers
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("asyncio").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)


def get_startup_message(handle: str, user_name: str) -> str:
    """Generate the startup notification message."""
    return f"""🤖 *AI Agent Online*

Hi {user_name}! Your AI agent is now running.

*How to use:*
• Mention `@{handle}` in any channel to get my attention
• DM me directly for private conversations
• I'll respond in threads to keep conversations organized

*Capabilities:*
• Answer questions and have conversations
• Help with coding tasks (read, write, edit files)
• Run shell commands
• Search and analyze codebases

*Tips:*
• Be specific about what you need
• I work best with clear, focused requests
• All responses go to threads to avoid channel noise

Ready to help! 🚀"""


async def run_agent(
    handle: str,
    system_prompt: str | None = None,
    cwd: str | None = None,
    poll_interval: float = 5.0,
) -> None:
    """Run the Slack agent."""
    # Load authentication
    auth = load_auth()

    # Create Slack client
    async with SlackClient(auth) as client:
        # Verify authentication
        auth_info = await client.auth_test()
        user_name = auth_info["user"]
        user_id = auth_info["user_id"]
        logger.info(f"Connected to Slack as {user_name} in {auth_info['team']}")

        # Send startup DM to self
        startup_msg = get_startup_message(handle, user_name)
        try:
            await client.send_dm(user_id, startup_msg)
            logger.info("Sent startup notification DM")
        except Exception as e:
            logger.warning(f"Could not send startup DM: {e}")

        # Create Claude agent
        agent_config = AgentConfig(
            system_prompt=system_prompt or "",
            cwd=cwd,
        )
        agent = ClaudeAgent(config=agent_config)

        # Create message poller
        poller = MessagePoller(
            client=client,
            handle=handle,
            poll_interval=poll_interval,
        )

        logger.info(f"Starting agent with handle @{handle}")
        logger.info("Press Ctrl+C to stop")

        try:
            async for message in poller.start():
                logger.info(f"Processing message from {message.user}: {message.text[:100]}...")
                thread_ts = message.thread_ts or message.ts

                try:
                    # Send immediate acknowledgment
                    await client.post_message(
                        channel=message.channel,
                        text="⏳ Working on it...",
                        thread_ts=thread_ts,
                    )

                    # Generate response using Claude
                    response = await agent.respond_simple(message.text)

                    # Post response to thread
                    await client.post_message(
                        channel=message.channel,
                        text=response,
                        thread_ts=thread_ts,
                    )
                    logger.info(f"Responded to message in thread {thread_ts}")

                except Exception as e:
                    logger.error(f"Error processing message: {e}")
                    # Post error message to thread
                    await client.post_message(
                        channel=message.channel,
                        text=f"❌ Sorry, I encountered an error: {e}",
                        thread_ts=thread_ts,
                    )

        except KeyboardInterrupt:
            logger.info("Shutting down...")
            await poller.stop()


def main() -> None:
    """CLI entry point."""
    parser = ArgumentParser(description="Agentic Curator - Slack AI Agent")
    parser.add_argument(
        "--handle",
        default=f"ai-{getpass.getuser()}",
        help="Handle to respond to (default: ai-<username>)",
    )
    parser.add_argument(
        "--system-prompt",
        help="System prompt for the Claude agent",
    )
    parser.add_argument(
        "--cwd",
        help="Working directory for the Claude agent",
    )
    parser.add_argument(
        "--poll-interval",
        type=float,
        default=5.0,
        help="Poll interval in seconds (default: 5)",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging",
    )

    args = parser.parse_args()

    if args.debug:
        # Only enable debug for our modules
        logging.getLogger("agentic_curator").setLevel(logging.DEBUG)

    asyncio.run(
        run_agent(
            handle=args.handle,
            system_prompt=args.system_prompt,
            cwd=args.cwd,
            poll_interval=args.poll_interval,
        )
    )


if __name__ == "__main__":
    main()
