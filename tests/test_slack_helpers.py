"""Tests for low-level helpers in agent.utils.slack and multimodal dedupe."""

from __future__ import annotations

import hashlib
import hmac
import time

import pytest

from agent.utils.multimodal import dedupe_urls
from agent.utils.slack import (
    _extract_slack_user_name,
    _parse_ts,
    verify_slack_signature,
)


class TestParseTs:
    def test_parses_numeric_string(self) -> None:
        assert _parse_ts("1.5") == 1.5

    def test_parses_integer_string(self) -> None:
        assert _parse_ts("42") == 42.0

    def test_none_returns_zero(self) -> None:
        assert _parse_ts(None) == 0.0

    def test_empty_string_returns_zero(self) -> None:
        assert _parse_ts("") == 0.0

    def test_invalid_returns_zero(self) -> None:
        assert _parse_ts("not-a-number") == 0.0


class TestExtractSlackUserName:
    def test_prefers_profile_display_name(self) -> None:
        user = {
            "profile": {"display_name": "Alice", "real_name": "Alice Anderson"},
            "real_name": "Alice A",
            "name": "alice",
        }
        assert _extract_slack_user_name(user) == "Alice"

    def test_falls_back_to_profile_real_name(self) -> None:
        user = {
            "profile": {"display_name": "  ", "real_name": "Alice Anderson"},
            "name": "alice",
        }
        assert _extract_slack_user_name(user) == "Alice Anderson"

    def test_falls_back_to_top_level_real_name(self) -> None:
        user = {"profile": {}, "real_name": "Top Real", "name": "alice"}
        assert _extract_slack_user_name(user) == "Top Real"

    def test_falls_back_to_name(self) -> None:
        user = {"name": "alice"}
        assert _extract_slack_user_name(user) == "alice"

    def test_returns_unknown_when_empty(self) -> None:
        assert _extract_slack_user_name({}) == "unknown"

    def test_strips_whitespace(self) -> None:
        user = {"profile": {"display_name": "  Alice  "}}
        assert _extract_slack_user_name(user) == "Alice"


class TestVerifySlackSignature:
    @staticmethod
    def _sign(secret: str, timestamp: str, body: bytes) -> str:
        base = f"v0:{timestamp}:{body.decode('utf-8')}"
        digest = hmac.new(secret.encode("utf-8"), base.encode("utf-8"), hashlib.sha256).hexdigest()
        return f"v0={digest}"

    def test_valid_signature_accepted(self) -> None:
        secret = "shhh"
        timestamp = str(int(time.time()))
        body = b'{"event":"test"}'
        signature = self._sign(secret, timestamp, body)

        assert verify_slack_signature(body, timestamp, signature, secret) is True

    def test_invalid_signature_rejected(self) -> None:
        secret = "shhh"
        timestamp = str(int(time.time()))
        body = b'{"event":"test"}'

        assert verify_slack_signature(body, timestamp, "v0=deadbeef", secret) is False

    def test_empty_secret_rejects(self) -> None:
        timestamp = str(int(time.time()))
        signature = self._sign("anything", timestamp, b"{}")

        assert verify_slack_signature(b"{}", timestamp, signature, "") is False

    def test_expired_timestamp_rejected(self) -> None:
        secret = "shhh"
        stale = str(int(time.time()) - 10_000)
        body = b"{}"
        signature = self._sign(secret, stale, body)

        assert verify_slack_signature(body, stale, signature, secret) is False

    def test_missing_timestamp_rejected(self) -> None:
        assert verify_slack_signature(b"{}", "", "v0=abc", "secret") is False

    def test_missing_signature_rejected(self) -> None:
        assert verify_slack_signature(b"{}", "1", "", "secret") is False

    def test_non_integer_timestamp_rejected(self) -> None:
        assert verify_slack_signature(b"{}", "not-a-ts", "v0=abc", "secret") is False

    def test_custom_max_age(self) -> None:
        secret = "shhh"
        timestamp = str(int(time.time()) - 60)
        body = b"{}"
        signature = self._sign(secret, timestamp, body)

        assert (
            verify_slack_signature(body, timestamp, signature, secret, max_age_seconds=10) is False
        )
        assert (
            verify_slack_signature(body, timestamp, signature, secret, max_age_seconds=120) is True
        )


class TestDedupeUrls:
    def test_preserves_order(self) -> None:
        assert dedupe_urls(["a", "b", "c"]) == ["a", "b", "c"]

    def test_removes_duplicates_preserving_first(self) -> None:
        assert dedupe_urls(["a", "b", "a", "c", "b"]) == ["a", "b", "c"]

    def test_empty_list(self) -> None:
        assert dedupe_urls([]) == []

    def test_all_duplicates(self) -> None:
        assert dedupe_urls(["x", "x", "x"]) == ["x"]


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("1.0", 1.0),
        ("1730900000.123456", 1730900000.123456),
        ("0", 0.0),
    ],
)
def test_parse_ts_parametrized(raw: str, expected: float) -> None:
    assert _parse_ts(raw) == expected
