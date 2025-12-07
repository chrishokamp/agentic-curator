# Agentic Curator - Slack AI Agent

## Project Overview

A Slack agent that personifies the user with a configurable handle (default: `@ai-<username>`). The agent connects to Slack using user-provided token and cookie credentials (no Slack app installation required), polls for new messages, and responds using a Claude Code agent.

## Quick Start

```bash
# Install dependencies
uv sync

# Run tests
uv run pytest tests/

# Start the agent (interactive credential input)
uv run python -m agentic_curator

# Start with environment variables
SLACK_TOKEN=xoxc-... SLACK_COOKIE=xoxd-... uv run python -m agentic_curator
```

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Agentic Curator                             │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌─────────────┐    ┌──────────────┐    ┌─────────────────────┐   │
│  │   Slack     │    │   Message    │    │   Claude Code       │   │
│  │   Poller    │───▶│   Router     │───▶│   Agent             │   │
│  │  (API Poll) │    │              │    │   (SDK Client)      │   │
│  └─────────────┘    └──────────────┘    └─────────────────────┘   │
│         │                  │                      │                │
│         ▼                  ▼                      ▼                │
│  ┌─────────────┐    ┌──────────────┐    ┌─────────────────────┐   │
│  │   Auth      │    │   Thread     │    │   Response          │   │
│  │   Module    │    │   Manager    │    │   Formatter         │   │
│  └─────────────┘    └──────────────┘    └─────────────────────┘   │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

## Key Components

### 1. Authentication (`src/agentic_curator/auth/`)
- **SlackAuth**: Handles token + cookie authentication
- Supports environment variables: `SLACK_TOKEN`, `SLACK_COOKIE`
- Supports interactive CLI input
- Token format: `xoxc-*` (client token) + `xoxd-*` (session cookie)

### 2. Slack Poller (`src/agentic_curator/slack/`)
- **SlackClient**: Wraps slack-sdk for API calls with cookie auth
- **MessagePoller**: Polls conversations for new messages
- Monitors: DMs and channels where user is a member
- Tracks last-seen timestamps to fetch only new messages

### 3. Message Router (`src/agentic_curator/router/`)
- **MessageRouter**: Determines if agent should respond
- Trigger conditions:
  - Direct mention of handle (`@ai-<username>`)
  - DM to the user
  - Relevant to agent's configured job (LLM-based decision)
- Thread tracking for conversation context

### 4. Claude Agent (`src/agentic_curator/agent/`)
- **ClaudeAgent**: Wraps claude-agent-sdk-python
- Configurable system prompt for different jobs
- All Claude Code tools available
- Thread-scoped conversations

### 5. Configuration (`src/agentic_curator/config/`)
- **AgentConfig**: YAML/env-based configuration
- Configurable: handle, system prompt, response behavior, poll interval

## Configuration

```yaml
# config.yaml
slack:
  handle: "ai-chris"  # Defaults to ai-<system_username>
  poll_interval_seconds: 5

agent:
  system_prompt: |
    You are a helpful assistant that curates knowledge...
  respond_to_all_relevant: true  # Respond even without mention if relevant

claude:
  permission_mode: "acceptEdits"
  cwd: "/path/to/workspace"
```

## Development

```bash
# Lint and format
uv run ruff check src/ tests/ --fix
uv run ruff format src/ tests/

# Type checking
uv run mypy src/

# Run all tests
uv run pytest tests/ -v

# Run specific test
uv run pytest tests/test_auth.py -v
```

## File Structure

```
agentic-curator/
├── pyproject.toml          # Project config, dependencies
├── README.md               # User documentation
├── claude.md               # This file - dev documentation
├── working-notes/          # Implementation notes
│   ├── architecture.md     # Detailed architecture decisions
│   ├── slack-api.md        # Slack API notes
│   └── testing.md          # Testing strategy
├── src/
│   └── agentic_curator/
│       ├── __init__.py
│       ├── __main__.py     # CLI entry point
│       ├── auth/           # Slack authentication
│       │   ├── __init__.py
│       │   └── slack_auth.py
│       ├── slack/          # Slack client and polling
│       │   ├── __init__.py
│       │   ├── client.py
│       │   └── poller.py
│       ├── router/         # Message routing logic
│       │   ├── __init__.py
│       │   └── message_router.py
│       ├── agent/          # Claude Code agent
│       │   ├── __init__.py
│       │   └── claude_agent.py
│       └── config/         # Configuration management
│           ├── __init__.py
│           └── settings.py
└── tests/
    ├── __init__.py
    ├── conftest.py         # Pytest fixtures
    ├── test_auth.py
    ├── test_slack.py
    ├── test_router.py
    └── test_agent.py
```

## Key Implementation Notes

### Slack Authentication (from slackdump analysis)
- Client tokens (`xoxc-*`) require session cookie (`d=xoxd-*`)
- Cookie must be URL-safe encoded
- Need both `d` and `d-s` (timestamp) cookies
- HTTP client must include cookies with every request
- Use same approach as slackdump: `NewValueAuth(token, cookie)`

### Polling Strategy
- Use `conversations.list` to get user's channels/DMs
- Use `conversations.history` with `oldest` param to get new messages
- Track last-seen timestamp per conversation
- Poll interval configurable (default: 5 seconds)
- Rate limiting: Slack Tier 3 = ~50 requests/minute

### Thread Management
- All responses go to threads (per user requirement)
- Thread identified by `thread_ts` field
- Maintain conversation context per thread
- Use `ClaudeSDKClient` for stateful conversations within thread

### Response Behavior
- Default: Only respond to explicit handle mentions
- Configurable: Respond to any relevant message (LLM decides relevance)
- Always respond in thread of the triggering message
- Use `chat.postMessage` with `thread_ts` to reply
