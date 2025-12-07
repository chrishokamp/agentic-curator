"""Tests for Slack client module."""

import pytest

from agentic_curator.slack_client import Message


class TestMessage:
    """Tests for Message class."""

    def test_message_basic(self):
        """Test creating a basic message."""
        msg = Message(
            ts="1234567890.123456",
            channel="C12345",
            user="U12345",
            text="Hello world",
        )
        assert msg.ts == "1234567890.123456"
        assert msg.channel == "C12345"
        assert msg.user == "U12345"
        assert msg.text == "Hello world"
        assert msg.thread_ts is None

    def test_message_is_thread_parent(self):
        """Test identifying thread parent messages."""
        msg = Message(
            ts="1234567890.123456",
            channel="C12345",
            user="U12345",
            text="Thread parent",
            reply_count=5,
        )
        assert msg.is_thread_parent
        assert not msg.is_thread_reply

    def test_message_is_thread_reply(self):
        """Test identifying thread reply messages."""
        msg = Message(
            ts="1234567890.123457",
            channel="C12345",
            user="U12345",
            text="Thread reply",
            thread_ts="1234567890.123456",
        )
        assert not msg.is_thread_parent
        assert msg.is_thread_reply

    def test_message_not_thread(self):
        """Test identifying non-threaded messages."""
        msg = Message(
            ts="1234567890.123456",
            channel="C12345",
            user="U12345",
            text="Regular message",
        )
        assert not msg.is_thread_parent
        assert not msg.is_thread_reply
