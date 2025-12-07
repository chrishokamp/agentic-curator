# MCP Server Integration

The Agentic Curator agent integrates with external MCP (Model Context Protocol) servers to extend its capabilities. This document describes the configured servers and their available tools.

## Prerequisites

### Redis Stack
```bash
# Start Redis Stack with vector search support
docker run -d --name redis-stack -p 6379:6379 -p 8001:8001 redis/redis-stack:latest
```

### Vibe Kanban (optional)
```bash
# Run vibe-kanban locally for the UI
npx vibe-kanban
```

## Configured MCP Servers

### 1. Redis MCP Server (`mcp__redis__*`)

Provides full Redis data structure support including vector search for semantic operations.

#### String Operations
| Tool | Description | Parameters |
|------|-------------|------------|
| `set` | Set a string value with optional expiration | `key`, `value`, `expiration?` |
| `get` | Get a string value | `key` |

#### Hash Operations
| Tool | Description | Parameters |
|------|-------------|------------|
| `hset` | Set a hash field | `name`, `key`, `value`, `expire_seconds?` |
| `hget` | Get a hash field | `name`, `key` |
| `hdel` | Delete a hash field | `name`, `key` |
| `hgetall` | Get all fields in a hash | `name` |
| `hexists` | Check if field exists | `name`, `key` |

#### Vector Operations (for Semantic Search)
| Tool | Description | Parameters |
|------|-------------|------------|
| `set_vector_in_hash` | Store a vector embedding | `name`, `vector` (list of floats), `vector_field?` |
| `get_vector_from_hash` | Retrieve a vector | `name`, `vector_field?` |
| `create_vector_index_hash` | Create a vector similarity index | `index_name`, `prefix`, `vector_field?`, `dim?` (default 1536), `distance_metric?` (COSINE/L2/IP) |
| `vector_search_hash` | KNN similarity search | `query_vector`, `index_name`, `vector_field`, `k`, `return_fields?` |

#### Index Management
| Tool | Description | Parameters |
|------|-------------|------------|
| `get_indexes` | List all indexes | - |
| `get_index_info` | Get index schema/metadata | `index_name` |
| `get_indexed_keys_number` | Count indexed keys | `index_name` |

#### List Operations
| Tool | Description | Parameters |
|------|-------------|------------|
| `lpush` | Push to left of list | `name`, `value`, `expire?` |
| `rpush` | Push to right of list | `name`, `value`, `expire?` |
| `lpop` | Pop from left | `name` |
| `rpop` | Pop from right | `name` |
| `lrange` | Get range of elements | `name`, `start`, `stop` |
| `llen` | Get list length | `name` |

#### Set Operations
| Tool | Description | Parameters |
|------|-------------|------------|
| `sadd` | Add to set | `name`, `value`, `expire_seconds?` |
| `srem` | Remove from set | `name`, `value` |
| `smembers` | Get all members | `name` |

#### Sorted Set Operations
| Tool | Description | Parameters |
|------|-------------|------------|
| `zadd` | Add with score | `key`, `score`, `member`, `expiration?` |
| `zrange` | Get range by index | `key`, `start`, `end`, `with_scores?` |
| `zrem` | Remove member | `key`, `member` |

#### JSON Operations
| Tool | Description | Parameters |
|------|-------------|------------|
| `json_set` | Set JSON at path | `name`, `path`, `value`, `expire_seconds?` |
| `json_get` | Get JSON at path | `name`, `path?` |
| `json_del` | Delete JSON at path | `name`, `path?` |

#### Stream Operations
| Tool | Description | Parameters |
|------|-------------|------------|
| `xadd` | Add to stream | `key`, `fields` (dict), `expiration?` |
| `xrange` | Read from stream | `key`, `count?` |
| `xdel` | Delete from stream | `key`, `entry_id` |

#### Pub/Sub
| Tool | Description | Parameters |
|------|-------------|------------|
| `publish` | Publish message | `channel`, `message` |
| `subscribe` | Subscribe to channel | `channel` |
| `unsubscribe` | Unsubscribe | `channel` |

#### Key Management
| Tool | Description | Parameters |
|------|-------------|------------|
| `delete` | Delete a key | `key` |
| `type` | Get key type | `key` |
| `expire` | Set expiration | `name`, `expire_seconds` |
| `rename` | Rename key | `old_key`, `new_key` |
| `scan_keys` | Scan keys with pattern | `pattern?`, `count?`, `cursor?` |
| `scan_all_keys` | Scan all matching keys | `pattern?`, `batch_size?` |

#### Server Management
| Tool | Description | Parameters |
|------|-------------|------------|
| `dbsize` | Get key count | - |
| `info` | Get server info | `section?` |
| `client_list` | List connected clients | - |

#### Documentation
| Tool | Description | Parameters |
|------|-------------|------------|
| `search_redis_documents` | Search Redis docs | `question` |

---

### 2. Vibe Kanban MCP Server (`mcp__vibe_kanban__*`)

Task and project management for orchestrating AI coding agents.

#### Project Operations
| Tool | Description | Parameters |
|------|-------------|------------|
| `list_projects` | List all projects | - |

#### Task Operations
| Tool | Description | Parameters |
|------|-------------|------------|
| `list_tasks` | List tasks in project | `project_id`, `status?`, `limit?` |
| `create_task` | Create a new task | `project_id`, `title`, `description?` |
| `get_task` | Get task details | `task_id` |
| `update_task` | Update task | `task_id`, `title?`, `description?`, `status?` |
| `delete_task` | Delete a task | `task_id` |

#### Task Execution
| Tool | Description | Parameters |
|------|-------------|------------|
| `start_task_attempt` | Start work on a task | `task_id`, `executor`, `base_branch`, `variant?` |
| `get_context` | Get current task context | - |

**Supported Executors:** Claude Code, Amp, Gemini, Codex, OpenCode, Cursor Agent, Qwen Code, Copilot, Droid

---

## Semantic Search with Embeddings

To perform semantic search, you need to:

1. **Generate embeddings** for your content (using an embedding model)
2. **Store vectors** in Redis using `set_vector_in_hash`
3. **Create an index** using `create_vector_index_hash`
4. **Search** using `vector_search_hash`

### Example Workflow

```python
# 1. Create a vector index for documents
# Uses HNSW algorithm, 1536 dimensions (OpenAI ada-002), COSINE similarity
await agent.query("""
Create a vector index called 'documents' with:
- prefix: 'doc:'
- dimensions: 1536
- distance metric: COSINE
""")

# 2. Store document with embedding
# The embedding would be generated by an embedding model
await agent.query("""
Store a vector in hash 'doc:readme' with the embedding [0.1, 0.2, ...]
and also set field 'content' to 'This is the readme content'
""")

# 3. Search for similar documents
await agent.query("""
Search the 'documents' index for vectors similar to [0.1, 0.2, ...]
Return top 5 results with their 'content' field
""")
```

### Embedding Dimensions by Model
| Model | Dimensions |
|-------|------------|
| OpenAI text-embedding-ada-002 | 1536 |
| OpenAI text-embedding-3-small | 1536 |
| OpenAI text-embedding-3-large | 3072 |
| Voyage voyage-2 | 1024 |
| Cohere embed-english-v3.0 | 1024 |

---

## Configuration

MCP servers are configured in `src/agentic_curator/__main__.py`:

```python
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
```

### Custom Redis URL

For remote Redis or Redis with authentication:
```python
"--url", "redis://user:password@hostname:6379/0"
# or for TLS
"--url", "rediss://user:password@hostname:6379/0"
```

---

## Testing

Run the Redis MCP tests:
```bash
# Ensure Redis is running first
docker run -d --name redis-stack -p 6379:6379 redis/redis-stack:latest

# Run tests
uv run pytest tests/test_redis_mcp.py -v

# Or run the smoke test directly
uv run python tests/test_redis_mcp.py
```
