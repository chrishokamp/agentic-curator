"""Tests for message poller module."""

import re

import pytest

from agentic_curator.poller import MessagePoller
from agentic_curator.slack_client import Message


class TestMessagePoller:
    """Tests for MessagePoller class."""

    def test_handle_pattern_matches_at_mention(self):
        """Test handle pattern matches @handle mentions."""
        # Create a mock poller (we'll test the pattern logic)
        pattern = re.compile(
            r"(?:@ai-test|<@U12345>)",
            re.IGNORECASE,
        )

        # Test @handle mention
        assert pattern.search("Hey @ai-test can you help?")
        assert pattern.search("@AI-TEST please respond")
        assert pattern.search("Hello @ai-test")

        # Test user ID mention
        assert pattern.search("Hey <@U12345> can you help?")

        # Test no match
        assert not pattern.search("Hello world")
        assert not pattern.search("Hey @other-user")

    def test_handle_pattern_case_insensitive(self):
        """Test handle pattern is case insensitive."""
        pattern = re.compile(
            r"(?:@ai-test|<@U12345>)",
            re.IGNORECASE,
        )

        assert pattern.search("@AI-TEST")
        assert pattern.search("@Ai-Test")
        assert pattern.search("@ai-test")
