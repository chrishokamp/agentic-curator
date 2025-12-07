"""Main entry point for the Agentic Curator Slack agent."""

from __future__ import annotations

import asyncio
import getpass
import logging
import os
import re
import sys
from argparse import ArgumentParser
from pathlib import Path

from .agent import AgentConfig, ClaudeAgent
from .auth import load_auth
from .memory import MemoryStore, generate_memory_cache
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


# Default MCP server configurations
DEFAULT_MCP_SERVERS = {
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


# Pattern to match agent actions: [ACTION:TYPE key="value" ...]
ACTION_PATTERN = re.compile(
    r'\[ACTION:(\w+)\s+([^\]]+)\]',
    re.IGNORECASE
)


async def execute_agent_actions(
    response: str,
    client: SlackClient,
    source_channel: str,
    source_thread: str,
) -> tuple[str, list[str]]:
    """Parse and execute actions from agent response.

    Args:
        response: Agent's response text
        client: Slack client
        source_channel: Channel the request came from
        source_thread: Thread the request came from

    Returns:
        Tuple of (cleaned response, list of action results)
    """
    results = []
    cleaned = response

    for match in ACTION_PATTERN.finditer(response):
        action_type = match.group(1).upper()
        params_str = match.group(2)

        # Parse key="value" pairs
        params = {}
        for param_match in re.finditer(r'(\w+)="([^"]*)"', params_str):
            params[param_match.group(1).lower()] = param_match.group(2)

        logger.info(f"Executing action: {action_type} with params: {params}")

        try:
            if action_type == "DM":
                # Send DM to user
                user_name = params.get("user", "")
                message = params.get("message", "")

                if user_name and message:
                    user = await client.find_user_by_name(user_name)
                    if user:
                        await client.send_dm(user.id, message)
                        results.append(f"✓ Sent DM to {user.real_name}")
                        logger.info(f"Sent DM to {user.real_name} ({user.id})")
                    else:
                        results.append(f"✗ User '{user_name}' not found")
                        logger.warning(f"User not found: {user_name}")

            elif action_type == "POST":
                # Post to a channel
                channel = params.get("channel", "")
                message = params.get("message", "")

                if channel and message:
                    # Try to find channel by name
                    convs = await client.get_conversations(types="public_channel,private_channel")
                    target_channel = None
                    for conv in convs:
                        if conv.get("name", "").lower() == channel.lower():
                            target_channel = conv["id"]
                            break

                    if target_channel:
                        await client.post_message(channel=target_channel, text=message)
                        results.append(f"✓ Posted to #{channel}")
                        logger.info(f"Posted to #{channel}")
                    else:
                        results.append(f"✗ Channel '{channel}' not found")

            elif action_type == "REACT":
                # Add reaction to source message
                emoji = params.get("emoji", "").replace(":", "")
                if emoji:
                    await client.add_reaction(source_channel, source_thread, emoji)
                    results.append(f"✓ Added :{emoji}: reaction")

        except Exception as e:
            logger.error(f"Action {action_type} failed: {e}")
            results.append(f"✗ {action_type} failed: {e}")

        # Remove action from response
        cleaned = cleaned.replace(match.group(0), "").strip()

    return cleaned, results


async def check_and_post_new_memories(
    client: SlackClient,
    memory_channel_id: str,
    known_memories: set[str],
) -> set[str]:
    """Check Redis for new memories and post them to #memory channel.

    Args:
        client: Slack client
        memory_channel_id: Channel ID for #memory
        known_memories: Set of memory IDs we've already posted

    Returns:
        Updated set of known memory IDs
    """
    import subprocess

    try:
        # Get all memory keys from Redis
        result = subprocess.run(
            ["docker", "exec", "redis-stack", "redis-cli", "KEYS", "memory:*"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode != 0:
            return known_memories

        memory_keys = [k.strip() for k in result.stdout.strip().split("\n") if k.strip()]

        for key in memory_keys:
            if key in known_memories:
                continue

            # Get memory content
            result = subprocess.run(
                ["docker", "exec", "redis-stack", "redis-cli", "HGETALL", key],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode != 0:
                continue

            # Parse HGETALL output (alternating key/value)
            lines = result.stdout.strip().split("\n")
            memory_data = {}
            for i in range(0, len(lines) - 1, 2):
                memory_data[lines[i].strip()] = lines[i + 1].strip()

            if not memory_data.get("summary"):
                continue

            # Format and post to #memory
            summary = memory_data.get("summary", "")
            source = memory_data.get("source", "conversation")
            thread_ts = memory_data.get("thread_ts", "")
            channel_id = memory_data.get("channel_id", "")

            # Build message with link back to original thread
            msg = f"🧠 *{source}*: {summary}"
            if thread_ts and channel_id:
                # Slack deep link format
                msg += f"\n\n_Source: <https://slack.com/archives/{channel_id}/p{thread_ts.replace('.', '')}|original thread>_"

            try:
                await client.post_message(
                    channel=memory_channel_id,
                    text=msg,
                )
                logger.info(f"Posted memory to #memory: {key}")
                known_memories.add(key)
            except Exception as e:
                logger.warning(f"Could not post memory {key} to #memory: {e}")

    except Exception as e:
        logger.warning(f"Error checking for new memories: {e}")

    return known_memories


async def discover_memory_channel(client: SlackClient) -> tuple[str, str] | None:
    """Discover the #memory channel ID.

    Returns:
        Tuple of (channel_id, channel_name) or None if not found.
    """
    try:
        conversations = await client.get_conversations(types="public_channel,private_channel")
        for conv in conversations:
            if conv.get("name") == "memory":
                return conv["id"], conv["name"]
    except Exception as e:
        logger.warning(f"Could not discover memory channel: {e}")
    return None


async def run_agent(
    handle: str,
    system_prompt: str | None = None,
    cwd: str | None = None,
    poll_interval: float = 5.0,
    enable_memory: bool = True,
    redis_url: str | None = None,
    memory_channel: str | None = None,
) -> None:
    """Run the Slack agent.

    Args:
        handle: The handle to respond to (e.g., "ai-chris").
        system_prompt: Optional system prompt for Claude.
        cwd: Working directory for Claude agent.
        poll_interval: Polling interval in seconds.
        enable_memory: Whether to enable Redis memory storage.
        redis_url: Redis URL (defaults to REDIS_URL env var).
        memory_channel: Optional Slack channel ID for memory (default: auto-discover #memory).
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

        # Discover or use configured memory channel
        memory_channel_id = memory_channel
        memory_channel_name = "memory"
        if not memory_channel_id:
            result = await discover_memory_channel(client)
            if result:
                memory_channel_id, memory_channel_name = result
                logger.info(f"Discovered #memory channel: {memory_channel_id}")
            else:
                logger.warning("No #memory channel found - memory posting disabled")
        else:
            logger.info(f"Using configured memory channel: {memory_channel_id}")

        # Send startup DM to self
        startup_msg = get_startup_message(handle, user_name)
        try:
            await client.send_dm(user_id, startup_msg)
            logger.info("Sent startup notification DM")
        except Exception as e:
            logger.warning(f"Could not send startup DM: {e}")

        # Create Claude agent (memory channel info added per-message)
        agent_config = AgentConfig(
            system_prompt=system_prompt or "",
            cwd=str(work_dir),
            mcp_servers=DEFAULT_MCP_SERVERS,
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

        # Track conversation context per thread: thread_key -> list of (role, message)
        thread_context: dict[str, list[tuple[str, str]]] = {}

        # Track memories we've already posted to #memory channel
        known_memories: set[str] = set()
        # Initialize with existing memories so we don't re-post old ones
        if memory_channel_id:
            known_memories = await check_and_post_new_memories(client, memory_channel_id, set())
            logger.info(f"Found {len(known_memories)} existing memories in Redis")

        try:
            async for message in poller.start():
                logger.info(f"Processing message from {message.user}: {message.text[:100]}...")

                thread_ts = message.thread_ts or message.ts
                thread_key = f"{message.channel}:{thread_ts}"

                try:
                    # Send immediate acknowledgment
                    ack_response = await client.post_message(
                        channel=message.channel,
                        text="⏳ Working on it...",
                        thread_ts=thread_ts,
                    )

                    # Retrieve relevant memories and generate cache file
                    memories = []
                    if memory_store:
                        try:
                            memories = memory_store.query(
                                text=message.text,
                                top_k=5,
                            )
                            logger.info(f"Found {len(memories)} relevant memories")
                            for mem in memories:
                                logger.debug(f"  Memory: {mem.summary[:50]}... (score={mem.score:.2f})")
                            trigger_context = (
                                f"From user {message.user} in channel {message.channel}"
                            )
                            generate_memory_cache(
                                query_text=message.text,
                                memories=memories,
                                output_path=memory_cache_path,
                                trigger_context=trigger_context,
                            )
                        except Exception as e:
                            logger.warning(f"Error retrieving memories: {e}")
                            import traceback
                            logger.debug(traceback.format_exc())

                    # Build prompt with memory context if available
                    prompt = message.text
                    if memories:
                        memory_context = "\n".join([
                            f"- {m.summary} (relevance: {m.score:.0%})"
                            for m in memories[:3]  # Top 3 most relevant
                        ])
                        prompt = f"""Previous relevant context from our conversation history:
{memory_context}

Current message: {message.text}

Use the context above if relevant to your response."""
                        logger.info(f"Added {len(memories[:3])} memories to prompt")

                    # Generate response using Claude
                    response = await agent.respond_simple(prompt)

                    # Execute any actions in the response
                    cleaned_response, action_results = await execute_agent_actions(
                        response, client, message.channel, thread_ts
                    )

                    # Append action results to response if any
                    if action_results:
                        cleaned_response += "\n\n" + "\n".join(action_results)

                    # Store the message and response in memory
                    if memory_store:
                        try:
                            memory_id = memory_store.store_message(
                                text=message.text,
                                user_id=message.user,
                                channel_id=message.channel,
                                thread_ts=thread_ts,
                                response=cleaned_response,
                            )
                            logger.info(f"Stored message in memory: {memory_id}")
                        except Exception as e:
                            logger.warning(f"Error storing message: {e}")

                    # Post response to thread (with robot emoji prefix)
                    response_msg = await client.post_message(
                        channel=message.channel,
                        text=f"🤖 {cleaned_response}",
                        thread_ts=thread_ts,
                    )

                    # Track this thread for future replies
                    response_ts = response_msg.get("ts", thread_ts)
                    poller.track_thread(
                        channel=message.channel,
                        thread_ts=thread_ts,
                        last_ts=response_ts,
                    )

                    logger.info(f"Responded in thread {thread_ts}, tracking for replies (last_ts={response_ts})")
                    logger.info(f"Active threads: {len(poller._active_threads)}")

                    # Check for new memories and post to #memory channel
                    if memory_channel_id:
                        known_memories = await check_and_post_new_memories(
                            client, memory_channel_id, known_memories
                        )

                except Exception as e:
                    logger.error(f"Error processing message: {e}")
                    import traceback
                    traceback.print_exc()
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
    parser.add_argument(
        "--memory-channel",
        help="Slack channel ID for memory storage (default: auto-discover #memory)",
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
            memory_channel=args.memory_channel,
        )
    )


if __name__ == "__main__":
    main()
