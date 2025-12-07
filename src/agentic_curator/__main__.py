"""Main entry point for the Agentic Curator Slack agent."""

from __future__ import annotations

import asyncio
import getpass
import logging
from argparse import ArgumentParser
from pathlib import Path

from .agent import AgentConfig, ClaudeAgent
from .auth import load_auth
from .memory import MemoryEntry, MemoryStore, generate_memory_cache
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
    enable_memory: bool = True,
    redis_url: str | None = None,
) -> None:
    """Run the Slack agent.

    Args:
        handle: The handle to respond to (e.g., "ai-chris").
        system_prompt: Optional system prompt for Claude.
        cwd: Working directory for Claude agent.
        poll_interval: Polling interval in seconds.
        enable_memory: Whether to enable Redis memory storage.
        redis_url: Redis URL (defaults to REDIS_URL env var).
    """
    # Load authentication
    auth = load_auth()

    # Resolve working directory
    work_dir = Path(cwd) if cwd else Path.cwd()
    memory_cache_path = work_dir / "memory_cache.md"

    # Initialize memory store if enabled
    memory_store: MemoryStore | None = None
    if enable_memory:
        try:
            effective_url = redis_url or "redis://localhost:6379"
            logger.debug(f"Connecting to Redis at {effective_url}")
            memory_store = MemoryStore(redis_url=redis_url)
            memory_store.ensure_index()
            logger.info(f"Memory store initialized (Redis: {effective_url})")
        except Exception as e:
            logger.warning(f"Could not initialize memory store: {e}")
            logger.debug(f"Full exception: {type(e).__name__}: {e}")
            logger.warning("Running without memory persistence")
            memory_store = None

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
            cwd=str(work_dir),
        )
        agent = ClaudeAgent(config=agent_config)

        # Create message poller
        poller = MessagePoller(
            client=client,
            handle=handle,
            poll_interval=poll_interval,
        )

        logger.info(f"Starting agent with handle @{handle}")
        if memory_store:
            logger.info("Memory storage enabled")
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

                    # Retrieve relevant memories and generate cache file
                    if memory_store:
                        try:
                            memories = memory_store.query(
                                text=message.text,
                                user_id=message.user,
                                top_k=5,
                            )
                            trigger_context = (
                                f"From user {message.user} in channel {message.channel}"
                            )
                            generate_memory_cache(
                                query_text=message.text,
                                memories=memories,
                                output_path=memory_cache_path,
                                trigger_context=trigger_context,
                            )
                            logger.debug(f"Generated memory cache with {len(memories)} entries")
                        except Exception as e:
                            logger.warning(f"Error retrieving memories: {e}")

                    # Generate response using Claude (with memory if enabled)
                    if memory_store:
                        response = await agent.respond_with_memory(message.text)
                        slack_reply = response.slack_reply

                        # Store new memories
                        if response.memory_entries:
                            entries_to_store = []
                            for entry_data in response.memory_entries:
                                if entry_data.get("should_persist", True):
                                    entry = MemoryEntry(
                                        summary=entry_data.get("summary", ""),
                                        details=entry_data.get("details", ""),
                                        user_id=message.user,
                                        channel_id=message.channel,
                                        thread_ts=thread_ts,
                                        source="conversation",
                                        status=entry_data.get("status", "active"),
                                        task_type=entry_data.get("task_type", "general"),
                                    )
                                    entries_to_store.append(entry)

                            if entries_to_store:
                                try:
                                    stored_ids = memory_store.upsert_batch(entries_to_store)
                                    logger.info(f"Stored {len(stored_ids)} new memories")
                                except Exception as e:
                                    logger.warning(f"Error storing memories: {e}")
                    else:
                        slack_reply = await agent.respond_simple(message.text)

                    # Post response to thread
                    await client.post_message(
                        channel=message.channel,
                        text=slack_reply,
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

        # Clean up memory cache file
        if memory_cache_path.exists():
            try:
                memory_cache_path.unlink()
            except Exception:
                pass


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
        "--no-memory",
        action="store_true",
        help="Disable Redis memory storage",
    )
    parser.add_argument(
        "--redis-url",
        help="Redis URL (default: REDIS_URL env var or redis://localhost:6379)",
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
            enable_memory=not args.no_memory,
            redis_url=args.redis_url,
        )
    )


if __name__ == "__main__":
    main()
