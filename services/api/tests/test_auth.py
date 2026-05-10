import pytest
from fastapi import HTTPException
from fastapi.responses import Response

from app.api.routes import (
    REDDIT_RETIRED_MESSAGE,
    reddit_connect_callback,
    reddit_connect_start,
    reddit_mock_connect,
    taste_reddit_export_apply,
    taste_reddit_export_preview,
)
from app.core.config import Settings
from app.services.auth import (
    build_oauth_state,
    build_pulse_session_token,
    extract_bearer_token,
    parse_oauth_state,
    parse_pulse_session_token,
    set_pulse_session_cookie,
)

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


def test_oauth_state_allows_empty_subjects_when_not_required() -> None:
    token = build_oauth_state(None, TEST_SECRET, purpose="spotify-connect")
    assert parse_oauth_state(token, TEST_SECRET, purpose="spotify-connect", required_sub=False) is None


def test_oauth_state_rejects_invalid_secret() -> None:
    token = build_oauth_state("user@example.com", TEST_SECRET)
    with pytest.raises(HTTPException):
        parse_oauth_state(token, OTHER_SECRET)


def test_oauth_state_rejects_wrong_purpose() -> None:
    token = build_oauth_state("user@example.com", TEST_SECRET, purpose="spotify-connect")
    with pytest.raises(HTTPException):
        parse_oauth_state(token, TEST_SECRET, purpose="reddit-connect")


def test_pulse_session_round_trip_returns_user_id() -> None:
    token = build_pulse_session_token("user-id-123", TEST_SECRET)
    assert parse_pulse_session_token(token, TEST_SECRET) == "user-id-123"


def test_pulse_session_cookie_uses_none_for_cross_origin_https() -> None:
    response = Response()
    settings = Settings(
        web_app_url="https://pulse-app.duckdns.org",
        api_base_url="https://pulse-api.duckdns.org",
        oauth_state_secret=TEST_SECRET,
    )

    set_pulse_session_cookie(response, "user-id-123", settings)

    assert "SameSite=none" in response.headers["set-cookie"]


def test_pulse_session_cookie_stays_lax_for_localhost() -> None:
    response = Response()
    settings = Settings(
        web_app_url="http://localhost:3000",
        api_base_url="http://localhost:8000",
        oauth_state_secret=TEST_SECRET,
    )

    set_pulse_session_cookie(response, "user-id-123", settings)

    assert "SameSite=lax" in response.headers["set-cookie"]


async def test_reddit_product_routes_are_retired() -> None:
    retired_routes = [
        reddit_connect_start(),
        reddit_connect_callback(request=None),
        reddit_mock_connect(),
        taste_reddit_export_preview(request=None),
        taste_reddit_export_apply(request=None),
    ]

    for route_call in retired_routes:
        with pytest.raises(HTTPException) as exc_info:
            await route_call

        assert exc_info.value.status_code == 410
        assert exc_info.value.detail == REDDIT_RETIRED_MESSAGE
