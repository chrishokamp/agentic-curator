# Agentic Curator

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![Tests](https://github.com/yourusername/agentic-curator/actions/workflows/tests.yml/badge.svg)](https://github.com/yourusername/agentic-curator/actions)

A Slack AI agent powered by Claude Code. The agent connects to Slack using your browser credentials (no app installation required), monitors for messages, and responds using the Claude Agent SDK.

> **Perfect for**: Building intelligent Slack assistants, automating workflows, running code in response to Slack messages, and maintaining persistent memory across conversations.

## ✨ Features

- **No App Installation Required** - Uses your browser Slack credentials
- **Claude Code Integration** - Leverage the Claude Agent SDK for powerful AI responses
- **Persistent Memory** - Redis-powered vector search for semantic conversation history
- **Customizable Behavior** - Flexible system prompts and trigger handles
- **Thread-Aware** - Responds in conversation threads keeping context organized
- **Easy Setup** - Single command to get started with `uv sync`
- **Docker Ready** - Includes docker-compose for full stack (Redis + Agent)

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- [uv](https://github.com/astral-sh/uv) (Python package manager)
- Slack workspace access (browser-based)
- Optional: Docker for Redis

### Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/agentic-curator.git
cd agentic-curator

# Install dependencies with uv
uv sync

# Install dev dependencies (optional, for testing)
uv sync --extra dev
```

### Get Your Slack Credentials

The agent requires your Slack browser session credentials. **[Detailed Instructions →](docs/getting-credentials.md)**

#### Quick Method (Console)

1. Open Slack in your **browser** (not the desktop app)
2. Press `F12` → switch to **Console** tab
3. Get your token:
   ```javascript
   JSON.parse(localStorage.localConfig_v2).teams[document.location.pathname.match(/client\/([A-Z0-9]+)/)[1]].token
   ```
4. Get your cookie:
   ```javascript
   document.cookie.match(/d=(xoxd-[^;]+)/)[1]
   ```

### Run the Agent

```bash
# Option 1: With environment variables
export SLACK_TOKEN="xoxc-your-token-here"
export SLACK_COOKIE="xoxd-your-cookie-here"
uv run python -m agentic_curator

# Option 2: Interactive (you'll be prompted for credentials)
uv run python -m agentic_curator
```

That's it! The agent will start polling Slack for messages.

## 📖 Usage

### Basic Command Line Options

```bash
uv run python -m agentic_curator --help

Options:
  --handle TEXT             Handle to respond to (default: ai-<username>)
  --system-prompt TEXT      System prompt for the Claude agent
  --cwd TEXT                Working directory for agent execution
  --poll-interval FLOAT     Poll interval in seconds (default: 5.0)
  --debug                   Enable debug logging
```

### Examples

**Custom handle and behavior:**
```bash
uv run python -m agentic_curator \
  --handle "ai-curator" \
  --system-prompt "You are a helpful code reviewer. Analyze code and provide constructive feedback."
```

**High-performance polling:**
```bash
uv run python -m agentic_curator \
  --poll-interval 2.0 \
  --handle "ai-dev"
```

**With working directory for file operations:**
```bash
uv run python -m agentic_curator \
  --cwd "/path/to/project" \
  --handle "ai-build"
```

## 🏗️ Architecture

The agent follows a clean architecture pattern:

```
┌─────────────────────────────────────────────────────────────────┐
│                      Agentic Curator                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Slack Poller         Message Router      Claude Agent SDK     │
│  ┌──────────────┐     ┌──────────────┐    ┌──────────────────┐ │
│  │ Monitors for  │────▶│ Routes to    │───▶│ AI-powered      │ │
│  │ @mentions &   │     │ Claude Code  │    │ responses       │ │
│  │ DMs           │     │ Agent        │    │ & actions       │ │
│  └──────────────┘     └──────────────┘    └────────┬─────────┘ │
│                                                     │           │
│                          ┌────────────────────────────────┐     │
│                          │   Redis (Persistent Memory)    │     │
│                          │   • Conversation history       │     │
│                          │   • Vector embeddings          │     │
│                          │   • Semantic search            │     │
│                          └────────────────────────────────┘     │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Core Components

- **SlackPoller** - Continuously polls Slack API for new messages
- **MessageRouter** - Identifies triggers and routes messages to the agent
- **Claude Agent** - Powered by the Claude Agent SDK for intelligent responses
- **MemoryManager** - Redis-backed vector database for conversation context
- **AuthHandler** - Secure credential management for Slack authentication

## 💾 Memory & Persistence

The agent uses Redis with vector search to maintain persistent memory across conversations.

### Setup Redis

**With Docker (Recommended):**
```bash
# Start Redis Stack (includes vector search support)
docker compose up -d redis

# Verify it's running
docker compose ps

# Access RedisInsight UI at http://localhost:8001
```

**Manual Setup:**
```bash
# Install Redis Stack locally
# See: https://redis.io/docs/latest/operate/oss_and_stack/install/

# Set Redis URL
export REDIS_URL="redis://localhost:6379"
```

### How Memory Works

1. Conversations are stored as vector embeddings in Redis
2. User queries are converted to embeddings for semantic search
3. Relevant past conversations are retrieved and provided as context
4. The agent maintains contextual awareness across multiple interactions

### Memory Configuration

```bash
# Custom Redis URL
export REDIS_URL="redis://custom-host:6379/0"

# When using Docker Compose
export REDIS_URL="redis://redis:6379"
```

## 🐳 Docker Deployment

Run everything in containers:

```bash
# Build and start both Redis and the agent
docker compose up --build

# Or just Redis
docker compose up -d redis

# View logs
docker compose logs -f agentic-curator
```

See `docker-compose.yml` for configuration details.

## 🛠️ Development

### Running Tests

```bash
# Run all tests with verbose output
uv run pytest tests/ -v

# Run specific test file
uv run pytest tests/test_agent.py -v

# Run with coverage
uv run pytest tests/ --cov=src/agentic_curator
```

### Code Quality

```bash
# Lint and format code
uv run ruff check src/ tests/ --fix
uv run ruff format src/ tests/

# Type checking
uv run mypy src/

# All checks at once
uv run ruff check src/ tests/ && uv run mypy src/
```

### Project Structure

```
agentic-curator/
├── src/
│   └── agentic_curator/
│       ├── __main__.py           # Entry point
│       ├── agent.py              # Claude agent wrapper
│       ├── slack_client.py       # Slack API client
│       ├── poller.py             # Message polling logic
│       ├── auth.py               # Authentication
│       └── memory.py             # Memory/context management
├── tests/                        # Test suite
├── docs/                         # Documentation
├── docker-compose.yml            # Docker configuration
├── pyproject.toml               # Project metadata
└── README.md                    # This file
```

## 📋 Configuration

### System Prompt Examples

**Code Review Assistant:**
```bash
--system-prompt "You are an expert code reviewer. Analyze code for quality, security, and performance. Provide constructive feedback."
```

**Research Assistant:**
```bash
--system-prompt "You are a research assistant. Help users find information, summarize documents, and answer questions based on provided context."
```

**DevOps Helper:**
```bash
--system-prompt "You are a DevOps specialist. Help with infrastructure, deployment strategies, and system administration tasks."
```

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `SLACK_TOKEN` | Your Slack client token (xoxc-*) | - |
| `SLACK_COOKIE` | Your Slack session cookie (xoxd-*) | - |
| `REDIS_URL` | Redis connection string | redis://localhost:6379 |
| `LOG_LEVEL` | Logging level (DEBUG, INFO, WARNING) | INFO |

## 🔧 Troubleshooting

### "No token provided" error
```bash
# Make sure credentials are set
echo $SLACK_TOKEN
echo $SLACK_COOKIE

# Or pass them when prompted
uv run python -m agentic_curator
```

### "Client token requires cookie" error
The client token (xoxc-*) requires the session cookie. Ensure both are set:
```bash
export SLACK_TOKEN="xoxc-..."
export SLACK_COOKIE="xoxd-..."
```

### Messages not detected
1. ✅ Verify you're using the correct handle
2. ✅ Check the agent is running (`uv run python -m agentic_curator`)
3. ✅ Enable debug logging: `--debug`
4. ✅ Refresh your Slack token if older than a few days

### Rate limiting
If you hit Slack API rate limits, increase the polling interval:
```bash
uv run python -m agentic_curator --poll-interval 10
```

### Redis connection errors
```bash
# Verify Redis is running
docker compose ps

# Check connection
redis-cli -u $REDIS_URL ping
# Should return: PONG

# View Redis logs
docker compose logs redis
```

## 📚 Documentation

- [Getting Slack Credentials](docs/getting-credentials.md) - Detailed credential extraction
- [Architecture](docs/architecture.md) - Deep dive into the system design
- [API Reference](docs/api.md) - Complete API documentation
- [Contributing](CONTRIBUTING.md) - How to contribute
- [Changelog](CHANGELOG.md) - Version history

## 🤝 Contributing

We welcome contributions! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

### Quick Start for Contributors

```bash
# Fork and clone
git clone https://github.com/yourusername/agentic-curator.git
cd agentic-curator

# Create a feature branch
git checkout -b feature/your-feature

# Install dev dependencies
uv sync --extra dev

# Make your changes and test
uv run pytest tests/ -v

# Ensure code quality
uv run ruff check . --fix && uv run mypy src/

# Push and create a PR
git push origin feature/your-feature
```

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- Built with the [Claude Agent SDK](https://github.com/anthropics/python-sdk)
- Slack integration via [python-slack-sdk](https://github.com/slackapi/python-slack-sdk)
- Memory powered by [Redis Stack](https://redis.io/docs/latest/operate/oss_and_stack/)

## 🐛 Support

- **Issues**: [GitHub Issues](https://github.com/yourusername/agentic-curator/issues)
- **Discussions**: [GitHub Discussions](https://github.com/yourusername/agentic-curator/discussions)
- **Documentation**: [/docs](docs/) directory

---

<div align="center">

**[Report Bug](https://github.com/yourusername/agentic-curator/issues)** • **[Request Feature](https://github.com/yourusername/agentic-curator/issues)** • **[Contribute](CONTRIBUTING.md)**

</div>
