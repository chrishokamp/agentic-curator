"""Tests for authentication module."""

import pytest

from agentic_curator.auth import AuthError, SlackAuth


class TestSlackAuth:
    """Tests for SlackAuth class."""

    def test_valid_client_token_with_cookie(self, mock_slack_auth):
        """Test creating auth with valid client token and cookie."""
        auth = SlackAuth(
            token=mock_slack_auth["token"],
            cookie=mock_slack_auth["cookie"],
        )
        assert auth.is_client_token
        assert auth.token == mock_slack_auth["token"]
        assert auth.cookie == mock_slack_auth["cookie"]

    def test_client_token_without_cookie_raises(self, mock_slack_auth):
        """Test that client token without cookie raises error."""
        with pytest.raises(AuthError, match="requires cookie"):
            SlackAuth(token=mock_slack_auth["token"], cookie="")

    def test_empty_token_raises(self):
        """Test that empty token raises error."""
        with pytest.raises(AuthError, match="No token"):
            SlackAuth(token="", cookie="xoxd-test")

    def test_bot_token_without_cookie(self):
        """Test that bot tokens don't require cookies."""
        auth = SlackAuth(token="xoxb-1234567890-abcdef", cookie="")
        assert not auth.is_client_token
        assert auth.token == "xoxb-1234567890-abcdef"

    def test_get_cookies_for_client_token(self, mock_slack_auth):
        """Test getting cookies for client token."""
        auth = SlackAuth(
            token=mock_slack_auth["token"],
            cookie=mock_slack_auth["cookie"],
        )
        cookies = auth.get_cookies()
        assert "d" in cookies
        assert "d-s" in cookies
        assert cookies["d"] == mock_slack_auth["cookie"]

    def test_get_cookies_for_bot_token(self):
        """Test that bot tokens return empty cookies."""
        auth = SlackAuth(token="xoxb-1234567890-abcdef", cookie="")
        cookies = auth.get_cookies()
        assert cookies == {}

    def test_get_headers(self, mock_slack_auth):
        """Test getting headers for API requests."""
        auth = SlackAuth(
            token=mock_slack_auth["token"],
            cookie=mock_slack_auth["cookie"],
        )
        headers = auth.get_headers()
        assert "Authorization" in headers
        assert headers["Authorization"] == f"Bearer {mock_slack_auth['token']}"
        assert "Cookie" in headers

    def test_is_url_safe(self):
        """Test URL safety check."""
        assert SlackAuth._is_url_safe("abc123")
        assert SlackAuth._is_url_safe("xoxd-ABC123")
        assert not SlackAuth._is_url_safe("test value")
        assert not SlackAuth._is_url_safe("test/value")
