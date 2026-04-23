import pytest
from fastapi import HTTPException

from app.services.auth import build_oauth_state, extract_bearer_token, parse_oauth_state

TEST_SECRET = "pulse-test-secret-32-chars-minimum!"
OTHER_SECRET = "other-pulse-secret-32-chars-minimum"


def test_extract_bearer_token_parses_authorization_header() -> None:
    assert extract_bearer_token("Bearer abc123") == "abc123"
    assert extract_bearer_token("Basic abc123") is None
    assert extract_bearer_token(None) is None


def test_oauth_state_round_trip_returns_email() -> None:
    token = build_oauth_state("user@example.com", TEST_SECRET)
    assert parse_oauth_state(token, TEST_SECRET) == "user@example.com"


def test_oauth_state_supports_alternate_purposes() -> None:
    token = build_oauth_state("user@example.com", TEST_SECRET, purpose="spotify-connect")
    assert parse_oauth_state(token, TEST_SECRET, purpose="spotify-connect") == "user@example.com"


def test_oauth_state_rejects_invalid_secret() -> None:
    token = build_oauth_state("user@example.com", TEST_SECRET)
    with pytest.raises(HTTPException):
        parse_oauth_state(token, OTHER_SECRET)


def test_oauth_state_rejects_wrong_purpose() -> None:
    token = build_oauth_state("user@example.com", TEST_SECRET, purpose="spotify-connect")
    with pytest.raises(HTTPException):
        parse_oauth_state(token, TEST_SECRET, purpose="reddit-connect")
