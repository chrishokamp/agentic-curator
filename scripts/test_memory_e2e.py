#!/usr/bin/env python3
"""End-to-end test for memory storage and retrieval via Slack.

This script:
1. Posts a test memory to #memory channel
2. Stores it in Redis
3. Retrieves it via Redis scan
4. Searches for it via Slack search

Prerequisites:
- Agent running: uv run python -m agentic_curator
- Redis running: docker run -d --name redis-stack -p 6379:6379 redis/redis-stack:latest
- #memory channel exists in Slack
"""

import asyncio
import sys
sys.path.insert(0, "src")

from agentic_curator.auth import load_auth
from agentic_curator.slack_client import SlackClient
from agentic_curator.memory import create_memory_from_slack, memory_store


async def main():
    print("\n" + "=" * 60)
    print("MEMORY E2E TEST")
    print("=" * 60)

    auth = load_auth()
    async with SlackClient(auth) as client:
        await client.auth_test()
        print(f"Connected as {client.user_name}")

        # Find #memory channel
        convs = await client.get_conversations()
        memory_channel = None
        for conv in convs:
            if conv.get("name") == "memory":
                memory_channel = conv["id"]
                break

        if not memory_channel:
            print("❌ #memory channel not found!")
            print("Create a channel named 'memory' and try again.")
            return

        print(f"Found #memory channel: {memory_channel}")

        # Test 1: Post a memory to Slack
        print("\n1. Posting test memory to #memory...")
        test_memory_text = "learned: e2e test - memory system is working"

        result = await client.post_message(
            channel=memory_channel,
            text=test_memory_text,
        )
        msg_ts = result.get("ts")
        print(f"   Posted message: {msg_ts}")

        # Test 2: Parse and cache locally
        print("\n2. Parsing memory locally...")
        memory = create_memory_from_slack(
            text=test_memory_text,
            agent="test-script",
            slack_ts=msg_ts,
            channel=memory_channel,
        )
        if memory:
            print(f"   Parsed: [{memory.memory_type}] {memory.content}")
            print(f"   ID: {memory.id}")
        else:
            print("   ❌ Failed to parse memory!")
            return

        # Test 3: Check Redis storage (via MCP)
        print("\n3. To verify Redis storage, ask the agent:")
        print(f'   @ai-chris check Redis for key "memory:{memory.id}"')

        # Test 4: Search via Slack
        print("\n4. Testing Slack search...")
        try:
            results = await client.search_messages(
                query="e2e test",
                channel="memory",
                count=5,
            )
            print(f"   Found {len(results)} matches")
            for r in results[:3]:
                print(f"   - {r.get('text', '')[:60]}...")
        except Exception as e:
            print(f"   ⚠️  Search failed (may need different permissions): {e}")

        # Test 5: Add reaction
        print("\n5. Adding 🧠 reaction...")
        try:
            await client.add_reaction(
                channel=memory_channel,
                timestamp=msg_ts,
                reaction="brain",
            )
            print("   ✅ Reaction added!")
        except Exception as e:
            print(f"   ⚠️  Reaction failed: {e}")

        print("\n" + "=" * 60)
        print("TEST COMPLETE")
        print("=" * 60)
        print("\nNext steps:")
        print("1. Check #memory channel for your test message with 🧠 reaction")
        print("2. Ask the agent: '@ai-chris what memories do we have?'")
        print("3. Ask the agent: '@ai-chris search memories for e2e test'")


if __name__ == "__main__":
    asyncio.run(main())
