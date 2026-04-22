import os
from datetime import datetime, timedelta, timezone
from typing import Any

import requests


DEFAULT_BASE_URL = "https://215fbbb9u9.execute-api.us-east-1.amazonaws.com"
DEFAULT_QUERY = "ASX BHP CBA NAB RBA"
DEFAULT_SUBREDDIT = "ASX_Bets"
DEFAULT_LIMIT = 30
REQUEST_TIMEOUT = 20


def _enabled() -> bool:
    return os.getenv("USE_EXTERNAL_REDDIT_API", "false").lower() == "true"


def _base_url() -> str:
    return os.getenv("EXTERNAL_API_BASE_URL", DEFAULT_BASE_URL).rstrip("/")


def _extract_events(payload: dict[str, Any]) -> list[dict[str, Any]]:
    if isinstance(payload.get("events"), list):
        return payload["events"]
    data = payload.get("data")
    if isinstance(data, dict) and isinstance(data.get("events"), list):
        return data["events"]
    return []


def _login_token(base_url: str) -> str | None:
    email = os.getenv("EXTERNAL_API_TEST_EMAIL")
    password = os.getenv("EXTERNAL_API_TEST_PASSWORD")
    if not email or not password:
        return None

    response = requests.post(
        f"{base_url}/v1/auth/login",
        json={"email": email, "password": password},
        timeout=REQUEST_TIMEOUT,
    )
    response.raise_for_status()
    body = response.json()
    return body.get("token") or body.get("access_token")


def _to_iso_utc(value: Any) -> str:
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(float(value), tz=timezone.utc).isoformat()
    if isinstance(value, str) and value.strip():
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc).isoformat()
        except ValueError:
            pass
    return datetime.now(timezone.utc).isoformat()


def fetch_reddit_posts(
    query: str | None = None,
    subreddit: str | None = None,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    """
    Fetch Reddit posts from external API and normalise for this project.
    Returns [] when disabled, misconfigured, or remote API fails.
    """
    if not _enabled():
        return []

    try:
        base_url = _base_url()
        token = _login_token(base_url)
        if not token:
            return []

        q = query or os.getenv("EXTERNAL_API_ASX_QUERY", DEFAULT_QUERY)
        sr = subreddit or os.getenv("EXTERNAL_API_ASX_SUBREDDIT", DEFAULT_SUBREDDIT)
        max_items = limit or int(os.getenv("EXTERNAL_API_ASX_LIMIT", str(DEFAULT_LIMIT)))
        after_date = (datetime.now(timezone.utc) - timedelta(days=30)).strftime("%Y-%m-%d")

        response = requests.get(
            f"{base_url}/v1/post/search",
            params={"query": q, "subreddit": sr, "limit": max_items, "after": after_date},
            headers={"Authorization": f"Bearer {token}"},
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        events = _extract_events(response.json())
        if not events:
            fallback_response = requests.get(
                f"{base_url}/v1/post/search",
                params={"query": q, "subreddit": sr, "limit": max_items},
                headers={"Authorization": f"Bearer {token}"},
                timeout=REQUEST_TIMEOUT,
            )
            fallback_response.raise_for_status()
            events = _extract_events(fallback_response.json())

        posts = []
        for event in events:
            attrs = event.get("attributes", {}) if isinstance(event, dict) else {}
            if not isinstance(attrs, dict):
                continue
            title = str(attrs.get("title", "")).strip()
            body = str(attrs.get("selftext", "")).strip()
            if not title and not body:
                continue
            posts.append(
                {
                    "id": attrs.get("id"),
                    "title": title,
                    "body": body,
                    "author": attrs.get("author"),
                    "subreddit": attrs.get("subreddit"),
                    "score": attrs.get("score", 0),
                    "created_at": _to_iso_utc(attrs.get("created_utc")),
                    "data_source": "reddit_external_api",
                }
            )
        return posts
    except Exception:
        return []
