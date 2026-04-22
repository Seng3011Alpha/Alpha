import os
import time
import uuid
from pathlib import Path

import pytest
import requests
from dotenv import load_dotenv


# Load project-level .env so pytest can read test credentials.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")

BASE_URL = os.getenv("EXTERNAL_API_BASE_URL", "https://215fbbb9u9.execute-api.us-east-1.amazonaws.com")
TEST_EMAIL = os.getenv("EXTERNAL_API_TEST_EMAIL")
TEST_PASSWORD = os.getenv("EXTERNAL_API_TEST_PASSWORD")
TEST_USERNAME = os.getenv("EXTERNAL_API_TEST_USERNAME")
TEST_QUERY = os.getenv("EXTERNAL_API_TEST_QUERY", "ukraine war")
TEST_SUBREDDIT = os.getenv("EXTERNAL_API_TEST_SUBREDDIT", "worldnews")


pytestmark = pytest.mark.skipif(
    not TEST_EMAIL or not TEST_PASSWORD,
    reason="Set EXTERNAL_API_TEST_EMAIL and EXTERNAL_API_TEST_PASSWORD to run live API smoke tests.",
)


def _unique_signup_identity() -> tuple[str, str]:
    suffix = f"{int(time.time())}-{uuid.uuid4().hex[:8]}"
    username = TEST_USERNAME or f"api-smoke-{suffix}"
    email = TEST_EMAIL or f"api-smoke-{suffix}@example.com"
    return username, email


def _signup_or_login() -> str:
    username, email = _unique_signup_identity()
    signup_payload = {"username": username, "email": email, "password": TEST_PASSWORD}

    signup_response = requests.post(
        f"{BASE_URL}/v1/auth/signup",
        json=signup_payload,
        timeout=20,
    )
    if signup_response.ok:
        token = signup_response.json().get("token") or signup_response.json().get("access_token")
        if token:
            return token

    login_response = requests.post(
        f"{BASE_URL}/v1/auth/login",
        json={"email": TEST_EMAIL, "password": TEST_PASSWORD},
        timeout=20,
    )
    login_response.raise_for_status()
    token = login_response.json().get("token") or login_response.json().get("access_token")
    assert token, "Login succeeded but no token/access_token was returned."
    return token


def _extract_events(payload: dict) -> list:
    if isinstance(payload.get("events"), list):
        return payload["events"]

    nested = payload.get("data")
    if isinstance(nested, dict) and isinstance(nested.get("events"), list):
        return nested["events"]

    return []


def test_external_api_end_to_end_smoke():
    token = _signup_or_login()
    headers = {"Authorization": f"Bearer {token}"}

    me_response = requests.get(f"{BASE_URL}/v1/auth/me", headers=headers, timeout=20)
    me_response.raise_for_status()
    me_data = me_response.json()
    assert isinstance(me_data, dict)

    search_response = requests.get(
        f"{BASE_URL}/v1/post/search",
        params={
            "query": TEST_QUERY,
            "subreddit": TEST_SUBREDDIT,
            "after": "2022-02-24",
            "limit": 5,
        },
        headers=headers,
        timeout=30,
    )
    search_response.raise_for_status()
    search_data = search_response.json()
    search_events = _extract_events(search_data)
    assert isinstance(search_events, list)

    if not search_events:
        pytest.skip("Search returned no events; skipping comments endpoint validation.")

    first_post = search_events[0]
    post_id = first_post.get("attributes", {}).get("id")
    assert post_id, "Expected first search event to contain attributes.id"

    comments_response = requests.get(
        f"{BASE_URL}/v1/post/comments",
        params={"link_id": post_id, "limit": 20, "parent_id": ""},
        headers=headers,
        timeout=30,
    )
    comments_response.raise_for_status()
    comments_data = comments_response.json()
    comments_events = _extract_events(comments_data)
    assert isinstance(comments_events, list)
