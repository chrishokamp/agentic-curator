"""Slack authentication using token + cookie (slackdump approach)."""

from __future__ import annotations

import os
import re
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING
from urllib.parse import quote

if TYPE_CHECKING:
    pass

# Token patterns from slackdump
CLIENT_TOKEN_RE = re.compile(r"xoxc-[0-9]+-[0-9]+-[0-9]+-[0-9a-z]{64}")
COOKIE_RE = re.compile(r"xoxd-[A-Za-z0-9%/+=]+")


class AuthError(Exception):
    """Authentication error."""


@dataclass
class SlackAuth:
    """Slack authentication credentials."""

    token: str
    cookie: str

    def __post_init__(self) -> None:
        """Validate credentials on creation."""
        if not self.token:
            raise AuthError("No token provided")
        if self.is_client_token and not self.cookie:
            raise AuthError("Client token (xoxc-*) requires cookie (xoxd-*)")

    @property
    def is_client_token(self) -> bool:
        """Check if token is a client token requiring cookies."""
        return bool(CLIENT_TOKEN_RE.match(self.token))

    @classmethod
    def from_env(cls) -> SlackAuth:
        """Create auth from environment variables."""
        token = os.environ.get("SLACK_TOKEN", "")
        cookie = os.environ.get("SLACK_COOKIE", "")
        return cls(token=token, cookie=cookie)

    @classmethod
    def from_interactive(cls) -> SlackAuth:
        """Create auth from interactive CLI input."""
        print("Slack Authentication")
        print("=" * 40)
        print("\nTo get your credentials:")
        print("1. Open Slack in your browser (not desktop app)")
        print("2. Open DevTools (F12) → Network tab")
        print("3. Filter by 'api' and click any request")
        print("4. In Request headers, find 'cookie' header")
        print("5. Copy the value after 'd=' (starts with xoxd-)")
        print("6. In Request payload, find 'token'")
        print("7. Copy the token value (starts with xoxc-)")
        print()

        token = input("Slack token (xoxc-...): ").strip()
        cookie = input("Slack cookie (xoxd-...): ").strip()

        return cls(token=token, cookie=cookie)

    def get_cookies(self) -> dict[str, str]:
        """Get cookies dict for HTTP requests."""
        if not self.is_client_token:
            return {}

        # URL-encode cookie if needed (following slackdump)
        cookie_value = self.cookie
        if not self._is_url_safe(cookie_value):
            cookie_value = quote(cookie_value, safe="")

        return {
            "d": cookie_value,
            "d-s": str(int(time.time()) - 10),
        }

    def get_headers(self) -> dict[str, str]:
        """Get headers for Slack API requests."""
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json; charset=utf-8",
        }
        if self.is_client_token:
            # For client tokens, include cookie in header
            cookies = self.get_cookies()
            cookie_str = "; ".join(f"{k}={v}" for k, v in cookies.items())
            headers["Cookie"] = cookie_str
        return headers

    @staticmethod
    def _is_url_safe(s: str) -> bool:
        """Check if string is URL-safe."""
        return bool(re.match(r"^[-._~%a-zA-Z0-9]+$", s))


def load_auth() -> SlackAuth:
    """Load authentication from environment or interactive input."""
    token = os.environ.get("SLACK_TOKEN")
    cookie = os.environ.get("SLACK_COOKIE")

    if token and cookie:
        return SlackAuth(token=token, cookie=cookie)

    return SlackAuth.from_interactive()
