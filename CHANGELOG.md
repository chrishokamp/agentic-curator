# Changelog

All notable changes to Agentic Curator will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Initial public release of Agentic Curator
- Slack message polling and response system
- Claude Agent SDK integration
- Redis-based persistent memory with vector search
- Docker support with docker-compose
- Comprehensive documentation and examples

### Changed
- Project restructured for open source release
- Documentation updated for public audiences

### Security
- Added environment variable handling for credentials
- Implemented token rotation support

## [0.1.0] - 2024-12-07

### Added
- Initial project setup
- Core agent functionality
- Slack integration
- Redis memory system
- Basic tests and CI/CD
- Development documentation

### Features

#### Message Handling
- Mention-based triggering (`@agent-name`)
- Direct message support
- Thread-aware responses
- Context preservation

#### Agent Capabilities
- Claude Code integration
- File execution support
- Custom system prompts
- Configurable handles

#### Memory System
- Vector embedding storage
- Semantic search
- Conversation history
- User-specific memory

### Documentation
- README with quick start
- Architecture documentation
- Credential extraction guide
- API reference
- Troubleshooting guide

---

## Changelog Guidelines

### Format

Use these sections when appropriate:

- **Added** - New features
- **Changed** - Changes to existing functionality
- **Deprecated** - Features marked for removal
- **Removed** - Removed features
- **Fixed** - Bug fixes
- **Security** - Security vulnerability fixes

### Release Process

1. Update CHANGELOG.md with unreleased changes
2. Move changes to a versioned section
3. Update version in `pyproject.toml`
4. Create git tag: `git tag v0.1.0`
5. Create release on GitHub with changelog excerpt

### Version Format

Use [Semantic Versioning](https://semver.org/):
- MAJOR version for incompatible API changes
- MINOR version for backwards-compatible new features
- PATCH version for backwards-compatible bug fixes

### Examples

```markdown
## [1.2.0] - 2024-12-15

### Added
- Support for scheduled messages
- New MessageScheduler class
- Configuration file support

### Fixed
- Rate limiting bug that caused message loss (#123)
- Memory search optimization for large datasets

### Changed
- Updated Redis connection pooling strategy

### Deprecated
- `Agent.respond()` method in favor of `Agent.execute()`
```

## Tags and Links

Format for unreleased and releases:
```markdown
[Unreleased]: https://github.com/yourusername/agentic-curator/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/yourusername/agentic-curator/releases/tag/v0.1.0
```
