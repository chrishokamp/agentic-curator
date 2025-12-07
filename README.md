# Agentic Curator

A Slack AI agent powered by Claude Code. The agent connects to Slack using your browser credentials (no app installation required), monitors for messages, and responds using a Claude Code agent.

## Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/agentic-curator.git
cd agentic-curator

# Install with uv
uv sync

# Install dev dependencies (for testing)
uv sync --extra dev
```

## Getting Your Slack Credentials

The agent uses your Slack browser session credentials (token + cookie). No Slack app installation required.

**[→ Detailed Instructions](docs/getting-credentials.md)**

### Get Token (Console Script)

1. Open Slack in your **browser** (not desktop app)
2. Press `F12` → **Console** tab
3. Paste and run:

```javascript
JSON.parse(localStorage.localConfig_v2).teams[document.location.pathname.match(/client\/([A-Z0-9]+)/)[1]].token
```

### Get Cookie

In the same Console, run:
```javascript
document.cookie.match(/d=(xoxd-[^;]+)/)[1]
```

Copy both values and set as environment variables.

## Usage

### With Environment Variables

```bash
export SLACK_TOKEN="xoxc-your-token-here"
export SLACK_COOKIE="xoxd-your-cookie-here"

uv run python -m agentic_curator
```

### With Interactive Input

```bash
uv run python -m agentic_curator
# You will be prompted for token and cookie
```

### Command Line Options

```bash
uv run python -m agentic_curator --help

Options:
  --handle TEXT         Handle to respond to (default: ai-<username>)
  --system-prompt TEXT  System prompt for the Claude agent
  --cwd TEXT            Working directory for the Claude agent
  --poll-interval FLOAT Poll interval in seconds (default: 5)
  --no-memory           Disable Redis memory storage
  --redis-url TEXT      Redis URL (default: redis://localhost:6379)
  --memory-channel TEXT Slack channel ID for memory posting
  --personality TEXT    Agent personality (default, angry, kind, obsequious, argumentative)
  --debug               Enable debug logging
```

### Example with Custom Prompt

```bash
uv run python -m agentic_curator \
  --handle "ai-curator" \
  --system-prompt "You are a knowledge curator. Help users find and organize information." \
  --cwd "/path/to/workspace"
```

## How It Works

1. **Authentication**: Uses your Slack browser credentials (token + cookie) to connect as you
2. **Polling**: Periodically checks for new messages in your conversations
3. **Trigger**: Responds when:
   - Someone mentions your handle (e.g., `@ai-chris`)
   - Someone DMs you directly
4. **Response**: Uses Claude Code agent to generate responses, posted to the same thread

## Configuration

### Handle
By default, the agent responds to `@ai-<your-username>`. Customize with `--handle`:

```bash
uv run python -m agentic_curator --handle "my-ai-assistant"
```

### System Prompt
Customize the agent's behavior with a system prompt:

```bash
uv run python -m agentic_curator --system-prompt "You are a helpful coding assistant."
```

### Personality
Give your agent some personality with the `--personality` flag:

```bash
# Default: helpful and productive (no flag needed)
uv run python -m agentic_curator

# Grumpy but competent
uv run python -m agentic_curator --personality angry

# Warm and supportive
uv run python -m agentic_curator --personality kind

# Excessively eager to please
uv run python -m agentic_curator --personality obsequious

# Contrarian devil's advocate
uv run python -m agentic_curator --personality argumentative
```

**Available Personalities:**

| Personality | Description |
|-------------|-------------|
| `default` | Helpful，productive, professional and friendly |
| `angry` | Perpetually frustrated, gets things done with visible annoyance |
| `kind` | Warm, caring, supportive, celebrates wins |
| `obsequious` | Excessively eager to please, deferential, apologetic |
| `argumentative` | Contrarian, challenges assumptions, Socratic method |

You can combine personality with a custom system prompt - the personality sets the tone while your prompt adds specific instructions:

```bash
uv run python -m agentic_curator \
  --personality kind \
  --system-prompt "You specialize in Python code reviews."
```

## Redis Setup (Memory)

The agent uses Redis with vector search for persistent memory per user. This enables semantic search over past conversations, so the agent can recall relevant context from previous interactions.

### What Redis Does

- **Stores conversation history** per user with metadata (channel, thread, timestamps)
- **Vector embeddings** using sentence-transformers for semantic similarity
- **Fast retrieval** of relevant past conversations when responding to new messages

### Quick Start

```bash
# Start Redis Stack (includes vector search)
docker compose up -d redis

# Verify it's running
docker compose ps
```

Redis will be available at:
- **Redis**: `localhost:6379`
- **RedisInsight (built-in)**: `localhost:8001`

### Environment Variables

```bash
export REDIS_URL="redis://localhost:6379"
```

When running the agent with Docker, use:
```bash
export REDIS_URL="redis://redis:6379"
```

### Running Everything with Docker

```bash
# Start Redis + run the agent
docker compose up --build
```

### Observability with RedisInsight

RedisInsight provides a GUI for monitoring and debugging Redis data, including vector indexes.

```bash
# Run RedisInsight (standalone)
docker run -d --name redisinsight -p 5540:5540 redis/redisinsight:latest
```

Then open http://localhost:5540 and connect to Redis:

| Setting | Value |
|---------|-------|
| Host | `host.docker.internal` |
| Port | `6379` |
| Name | `local-redis` (optional) |

> **Note**: Use `host.docker.internal` instead of `localhost` because RedisInsight runs in a container and needs to reach Redis on your host machine.

Once connected, you can:
- Browse stored memories under the `memory:*` keys
- Inspect the `agent_memory` vector index
- Monitor real-time commands
- Debug search queries

## Vibe Kanban Integration

The agent includes integration with [vibe-kanban](https://www.npmjs.com/package/vibe-kanban) for task management via MCP (Model Context Protocol). This allows the agent to manage projects and tasks directly through Slack.

### What is Vibe Kanban?

Vibe Kanban is an MCP server that provides a persistent kanban-style task management system. It's ideal for tracking work items, managing projects, and organizing tasks during development sessions.

### How It Works

The agent automatically starts the vibe-kanban MCP server when running. You can interact with it by asking the agent to:

- **List projects**: "Show me all my projects"
- **Create projects**: "Create a new project called 'Backend Refactor'"
- **Create tasks**: "Add a task 'Fix authentication bug' to the Backend Refactor project"
- **Update task status**: "Mark the auth bug task as completed"
- **Start work sessions (attempts)**: "Start working on the API optimization task"

### Available MCP Tools

The vibe-kanban server provides these tools to the agent:

| Tool | Description |
|------|-------------|
| `list_projects` | List all projects |
| `create_project` | Create a new project with name and description |
| `get_project` | Get project details and its tasks |
| `create_task` | Create a task within a project |
| `update_task` | Update task status, priority, or details |
| `delete_task` | Remove a task |
| `start_attempt` | Begin a work session on a task |
| `complete_attempt` | Mark a work session as complete |

### Example Workflow

```
User: @ai-chris create a project called "API Migration" with description "Migrate REST API to GraphQL"
Agent: Created project "API Migration" (ID: proj_abc123)

User: @ai-chris add a task "Set up GraphQL schema" to API Migration, high priority
Agent: Created task "Set up GraphQL schema" with high priority in API Migration

User: @ai-chris start working on the GraphQL schema task
Agent: Started attempt on "Set up GraphQL schema". Timer running.

User: @ai-chris I finished the schema, mark it complete
Agent: Completed attempt. Task "Set up GraphQL schema" marked as done.
```

### Data Persistence

Vibe-kanban stores data in `~/.vibe-kanban/` by default. Projects and tasks persist across agent restarts.

### Configuration

The vibe-kanban MCP server is configured in `__main__.py`:

```python
DEFAULT_MCP_SERVERS = {
    "vibe_kanban": {
        "command": "npx",
        "args": ["-y", "vibe-kanban@latest", "--mcp"],
    },
    # ... other servers
}
```

To use a specific version or custom path:

```python
"vibe_kanban": {
    "command": "npx",
    "args": ["-y", "vibe-kanban@1.0.0", "--mcp", "--data-dir", "/custom/path"],
},
```

### Requirements

- Node.js 18+ (for npx)
- The agent will automatically download vibe-kanban on first use

## Development

```bash
# Run tests
uv run pytest tests/ -v

# Lint and format
uv run ruff check src/ tests/ --fix
uv run ruff format src/ tests/

# Type check
uv run mypy src/
```

## Architecture

```
┌──────────────────────────────────────────────────────────────────────────┐
│                            Agentic Curator                               │
├──────────────────────────────────────────────────────────────────────────┤
│  ┌─────────────┐    ┌──────────────┐    ┌─────────────────────┐         │
│  │   Slack     │    │   Message    │    │   Claude Code       │         │
│  │   Poller    │───▶│   Router     │───▶│   Agent             │         │
│  │  (API Poll) │    │              │    │   (SDK Client)      │         │
│  └─────────────┘    └──────────────┘    └──────────┬──────────┘         │
│                                                     │                    │
│                                          ┌──────────▼──────────┐         │
│                                          │   Redis (Memory)    │         │
│                                          │   Vector Search     │         │
│                                          └─────────────────────┘         │
└──────────────────────────────────────────────────────────────────────────┘
```

## Troubleshooting

### "No token provided" error
Make sure you've set the `SLACK_TOKEN` environment variable or provide it when prompted.

### "Client token requires cookie" error
Client tokens (xoxc-*) require the session cookie. Make sure you've also set `SLACK_COOKIE`.

### Messages not being detected
- Check that you're mentioning the correct handle
- Ensure the token/cookie are valid (try refreshing from browser)
- Enable debug logging with `--debug` to see what's happening

### Rate limiting
If you see rate limit errors, increase the poll interval:
```bash
uv run python -m agentic_curator --poll-interval 10
```

## License

MIT
