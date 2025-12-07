# Contributing to Agentic Curator

Thank you for your interest in contributing! We welcome contributions of all kinds - code, documentation, bug reports, and feature suggestions.

## Code of Conduct

Be respectful, inclusive, and constructive. We're building something great together.

## Getting Started

### Fork & Clone

```bash
# Fork the repository on GitHub, then:
git clone https://github.com/your-username/agentic-curator.git
cd agentic-curator
git remote add upstream https://github.com/yourusername/agentic-curator.git
```

### Setup Development Environment

```bash
# Install dependencies and dev tools
uv sync --extra dev

# Verify setup
uv run pytest tests/ -v
```

## Making Changes

### Create a Feature Branch

```bash
git checkout -b feature/your-feature-name
# or
git checkout -b fix/your-bug-fix
```

### Code Standards

We follow these practices:

- **Python 3.11+** - Use modern Python features
- **Type hints** - All functions should be annotated
- **Docstrings** - Use docstrings for modules, classes, and public methods
- **Tests** - Add tests for new functionality

### Before Committing

```bash
# Format code
uv run ruff format src/ tests/

# Lint
uv run ruff check src/ tests/ --fix

# Type check
uv run mypy src/

# Run tests
uv run pytest tests/ -v
```

### Example Workflow

```bash
# Make your changes
# ... edit files ...

# Test locally
uv run pytest tests/test_your_changes.py -v

# Format and lint
uv run ruff format . && uv run ruff check . --fix

# Type check
uv run mypy src/

# Commit with a clear message
git add .
git commit -m "feat: add support for custom handlers

- Allows users to define custom message handlers
- Includes tests and documentation
- Fixes #123"
```

## Submitting a Pull Request

1. **Ensure tests pass**: `uv run pytest tests/ -v`
2. **Verify code quality**: `uv run ruff check . --fix && uv run mypy src/`
3. **Push to your fork**: `git push origin feature/your-feature`
4. **Open a PR** with a clear description of changes
5. **Respond to reviews** and make requested changes

### PR Title Format

```
type(scope): description

Examples:
- feat(memory): add vector search optimization
- fix(poller): handle rate limiting correctly
- docs(readme): improve setup instructions
- test(agent): add coverage for edge cases
```

Types: `feat`, `fix`, `docs`, `test`, `refactor`, `perf`, `ci`

## Reporting Issues

Found a bug? Have a feature idea? Create an issue!

### Bug Reports

Please include:
- Python version (`python --version`)
- OS and environment details
- Steps to reproduce
- Actual vs expected behavior
- Error logs or stack traces

### Feature Requests

Include:
- Use case / motivation
- Proposed solution (if any)
- Any alternative approaches

## Documentation

### Adding/Updating Docs

- Docs go in the `/docs` directory
- Use Markdown format
- Include code examples where helpful
- Link to related documentation

### Example Doc Structure

```markdown
# Feature Title

## Overview
Brief description of what this is.

## Quick Start
```bash
# How to use it quickly
```

## Detailed Guide
More in-depth explanation.

### Configuration
Available options and settings.

## Examples
Real-world usage examples.

## Troubleshooting
Common issues and solutions.
```

## Testing

### Writing Tests

```python
import pytest
from agentic_curator.agent import Agent

def test_agent_initialization():
    """Test that Agent initializes correctly."""
    agent = Agent(handle="ai-test")
    assert agent.handle == "ai-test"

@pytest.mark.asyncio
async def test_message_processing():
    """Test async message processing."""
    agent = Agent(handle="ai-test")
    result = await agent.process_message("hello")
    assert result is not None
```

### Running Tests

```bash
# All tests
uv run pytest tests/ -v

# Specific test
uv run pytest tests/test_agent.py::test_agent_initialization -v

# With coverage
uv run pytest tests/ --cov=src/agentic_curator --cov-report=html

# Watch mode (requires pytest-watch)
uv run ptw tests/
```

## Commit Messages

Write clear, descriptive commit messages:

```
feat: add message scheduling support

- Allows agents to schedule messages for later delivery
- Includes new MessageScheduler class
- Adds comprehensive tests
- Updates documentation

Fixes #456
```

Guidelines:
- Use imperative mood ("add" not "adds")
- First line is concise (< 50 chars)
- Wrap body at 72 chars
- Reference issues/PRs with `Fixes #123`

## Code Review

All contributions require review. Reviewers will:
- Check for code quality and style
- Verify tests are adequate
- Ensure documentation is clear
- Suggest improvements

### Review Process

1. Submit PR
2. Automated checks run (tests, linting, etc.)
3. Maintainer reviews code
4. Address feedback and make changes
5. Approval and merge!

## Merging

Once approved, a maintainer will merge your PR. We typically:
- Squash commits for cleaner history
- Update CHANGELOG.md
- Release a new version if appropriate

## Questions?

- 💬 Check [GitHub Discussions](https://github.com/yourusername/agentic-curator/discussions)
- 📖 Read the [Documentation](/docs)
- 🐛 Review [Existing Issues](https://github.com/yourusername/agentic-curator/issues)

---

**Thanks for contributing!** 🙌
