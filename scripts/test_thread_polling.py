#!/usr/bin/env python3
"""Test script to verify thread polling is working.

Run this alongside the main agent to verify thread replies are detected.
"""

import asyncio
import sys
sys.path.insert(0, "src")

from agentic_curator.auth import load_auth
from agentic_curator.slack_client import SlackClient
from agentic_curator.poller import MessagePoller


async def main():
    """Test thread polling."""
    auth = load_auth()

    async with SlackClient(auth) as client:
        await client.auth_test()
        print(f"Connected as {client.user_name} ({client.user_id})")

        poller = MessagePoller(
            client=client,
            handle="ai-chris",
            poll_interval=3.0,
        )

        # Simulate tracking a thread
        # You'll need to replace these with real values from your Slack
        test_channel = input("Enter channel ID (e.g., C123...): ").strip()
        test_thread = input("Enter thread_ts to monitor: ").strip()

        if test_channel and test_thread:
            poller.track_thread(test_channel, test_thread, last_ts=test_thread)
            print(f"\nTracking thread {test_thread} in channel {test_channel}")
            print("Active threads:", poller._active_threads)

            print("\nPolling for replies (Ctrl+C to stop)...")
            print("-" * 50)

            try:
                while True:
                    # Poll active threads
                    async for msg in poller._poll_active_threads():
                        print(f"\n🆕 NEW REPLY DETECTED!")
                        print(f"   User: {msg.user}")
                        print(f"   Text: {msg.text[:100]}")
                        print(f"   TS: {msg.ts}")
                        print(f"   Thread TS: {msg.thread_ts}")

                    await asyncio.sleep(3)
                    print(".", end="", flush=True)

            except KeyboardInterrupt:
                print("\nStopped.")
        else:
            print("No channel/thread specified. Exiting.")


if __name__ == "__main__":
    asyncio.run(main())
