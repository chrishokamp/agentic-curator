#!/usr/bin/env python3
"""Quick script to check what's in Redis."""

import redis

# Don't decode responses since embedding is binary
r = redis.Redis(host="localhost", port=6379, decode_responses=False)

print("=== Redis Memory Check ===\n")

# Check connection
try:
    r.ping()
    print("✓ Connected to Redis\n")
except Exception as e:
    print(f"✗ Could not connect to Redis: {e}")
    exit(1)

# List all memory keys
keys = r.keys(b"memory:*")
print(f"Found {len(keys)} memory entries:\n")

for key in keys[:10]:  # Show first 10
    print(f"  - {key.decode()}")
    # Get the hash data
    data = r.hgetall(key)
    if data:
        summary = data.get(b'summary', b'N/A').decode('utf-8', errors='ignore')[:60]
        user_id = data.get(b'user_id', b'N/A').decode('utf-8', errors='ignore')
        has_embedding = b'embedding' in data
        embedding_size = len(data.get(b'embedding', b'')) if has_embedding else 0
        print(f"    summary: {summary}...")
        print(f"    user_id: {user_id}")
        print(f"    has embedding: {has_embedding} ({embedding_size} bytes)")
    print()

# Check if index exists
try:
    info = r.execute_command("FT.INFO", "agent_memory")
    print(f"✓ Index 'agent_memory' exists")
    # Find num_docs in the info
    for i, item in enumerate(info):
        if item == b"num_docs":
            print(f"  Documents indexed: {info[i+1]}")
            break
except Exception as e:
    print(f"✗ Index issue: {e}")

# Try a simple search
print("\n=== Testing Vector Search ===")
try:
    from agentic_curator.memory import MemoryStore
    store = MemoryStore()
    store.ensure_index()

    results = store.query("list perfect numbers", top_k=5)
    print(f"Query 'list perfect numbers' returned {len(results)} results:")
    for r in results:
        print(f"  - {r.summary[:50]}... (score={r.score:.2f})")
except Exception as e:
    print(f"Search error: {e}")
    import traceback
    traceback.print_exc()
