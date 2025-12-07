# Agent Memory System via #memory Channel

## Overview

The #memory channel enables agents to collaborate on long-term memory. Agents can:
1. **Store memories** - Write learnings, facts, and context to the channel
2. **Retrieve memories** - Search for relevant memories using semantic search
3. **Share context** - Multiple agents can read and build on each other's memories

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Slack #memory Channel                        │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ [Agent A]: Learned: User prefers concise responses       │  │
│  │ [Agent B]: Fact: Project uses Python 3.11                │  │
│  │ [Agent A]: Context: Working on auth system refactor      │  │
│  └──────────────────────────────────────────────────────────┘  │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌───────────────────────────────────────────────────────────────┐
│                     Memory Processor                          │
│  1. Parse memory type (learned/fact/context/preference)       │
│  2. Generate embedding (text-embedding model)                 │
│  3. Store in Redis with vector + metadata                     │
└───────────────────────────┬───────────────────────────────────┘
                            │
                            ▼
┌───────────────────────────────────────────────────────────────┐
│                      Redis Stack                              │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │ Key: memory:{uuid}                                       │ │
│  │ Fields:                                                  │ │
│  │   - content: "User prefers concise responses"           │ │
│  │   - type: "preference"                                  │ │
│  │   - agent: "ai-chris"                                   │ │
│  │   - timestamp: "2025-12-07T15:00:00Z"                   │ │
│  │   - slack_ts: "1234567890.123456"                       │ │
│  │   - embedding: [0.1, 0.2, ...]  (vector)               │ │
│  └─────────────────────────────────────────────────────────┘ │
│                                                               │
│  Index: memory_vectors (HNSW, cosine similarity)             │
└───────────────────────────────────────────────────────────────┘
```

## Memory Types

| Type | Description | Example |
|------|-------------|---------|
| `learned` | Something the agent figured out | "Learned: The deploy script needs sudo" |
| `fact` | Objective information | "Fact: API rate limit is 100 req/min" |
| `preference` | User or project preferences | "Preference: Use TypeScript over JavaScript" |
| `context` | Current working context | "Context: Refactoring the auth module" |
| `decision` | A decision that was made | "Decision: Using PostgreSQL for the database" |

## Message Format

Agents write to #memory using a simple format:

```
[Type]: [Content]

Optional metadata:
- Tags: #auth #deployment
- Related: memory:{uuid}
```

Examples:
```
Learned: The CI pipeline fails if tests take > 10 minutes

Fact: Redis is running on port 6379 locally
Tags: #infrastructure #redis

Preference: Chris prefers bullet points over paragraphs

Context: Currently working on MCP server integration
Related: memory:abc123
```

## Redis Schema

### Memory Hash
```
Key: memory:{uuid}
Fields:
  content     - The memory text
  type        - learned|fact|preference|context|decision
  agent       - Which agent created it (e.g., "ai-chris")
  timestamp   - ISO 8601 timestamp
  slack_ts    - Slack message timestamp
  channel     - Slack channel ID
  tags        - Comma-separated tags
  related     - Related memory UUIDs
  embedding   - Vector embedding (stored separately)
```

### Vector Index
```
Index: memory_vectors
Type: HNSW
Prefix: memory:
Vector Field: embedding
Dimensions: 1536 (OpenAI ada-002) or configurable
Distance: COSINE
```

## API / Tools

### Writing Memories

The agent can write memories by:
1. Posting to #memory channel (human-readable)
2. Storing in Redis via MCP tools (structured)

```python
# Agent posts to Slack #memory
await client.post_message(
    channel=MEMORY_CHANNEL_ID,
    text="Learned: The deploy script requires AWS credentials in ~/.aws"
)

# Memory processor picks it up and stores in Redis
await store_memory(
    content="The deploy script requires AWS credentials in ~/.aws",
    memory_type="learned",
    agent="ai-chris",
    tags=["deployment", "aws"]
)
```

### Retrieving Memories

Agents can search memories:

```python
# Semantic search
memories = await search_memories(
    query="How do I deploy?",
    limit=5,
    types=["learned", "fact"],  # Optional filter
)

# By type
memories = await get_memories_by_type("preference", limit=10)

# Recent memories
memories = await get_recent_memories(hours=24, limit=20)
```

## Implementation Plan

### Phase 1: Basic Memory Storage
1. Monitor #memory channel for new messages
2. Parse memory type from message format
3. Store in Redis hash with metadata
4. No embeddings yet (keyword search only)

### Phase 2: Semantic Search
1. Add embedding generation (OpenAI or local model)
2. Create vector index in Redis
3. Implement similarity search
4. Add to agent's system prompt

### Phase 3: Agent Integration
1. Agents automatically query relevant memories before responding
2. Agents write learnings to #memory after conversations
3. Memory consolidation (merge similar memories)
4. Memory expiration (old context fades)

## Configuration

```python
MEMORY_CONFIG = {
    "channel_name": "memory",  # Slack channel name
    "redis_prefix": "memory:",
    "vector_index": "memory_vectors",
    "vector_dims": 1536,
    "embedding_model": "text-embedding-ada-002",  # or "local"
    "max_memories_per_query": 5,
    "memory_ttl_days": 30,  # Optional expiration
}
```

## Example Workflow

1. **User asks about deployment**
   ```
   User: How do I deploy the app?
   ```

2. **Agent searches memories**
   ```
   Query: "deployment" -> Finds:
   - "Learned: The deploy script requires AWS credentials"
   - "Fact: Deploy command is `./scripts/deploy.sh`"
   - "Decision: Using GitHub Actions for CI/CD"
   ```

3. **Agent responds with context**
   ```
   Agent: To deploy, run `./scripts/deploy.sh`. Make sure you have
   AWS credentials in ~/.aws first. We use GitHub Actions for CI/CD.
   ```

4. **Agent learns something new**
   ```
   User: Oh, you also need to set DEPLOY_ENV=production

   Agent: Got it! I'll remember that.
   [Posts to #memory]: Learned: Set DEPLOY_ENV=production before deploying
   ```
