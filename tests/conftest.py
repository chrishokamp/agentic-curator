"""Pytest fixtures for agentic-curator tests."""

import pytest


@pytest.fixture
def mock_slack_auth():
    """Mock Slack authentication credentials."""
    return {
        "token": "xoxc-1234567890-1234567890-1234567890-abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890ab",
        "cookie": "xoxd-test-cookie-value",
    }


@pytest.fixture
def mock_message():
    """Mock Slack message."""
    return {
        "ts": "1234567890.123456",
        "channel": "C12345",
        "user": "U12345",
        "text": "Hello @ai-test, can you help?",
        "thread_ts": None,
    }
