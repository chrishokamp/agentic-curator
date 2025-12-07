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

## Redis Setup (Memory)

The agent uses Redis with vector search for persistent memory per user. This enables semantic search over past conversations.

### Quick Start

```bash
# Start Redis Stack (includes vector search)
docker compose up -d redis

# Verify it's running
docker compose ps
```

Redis will be available at `localhost:6379` and RedisInsight (web UI) at `localhost:8001`.

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
