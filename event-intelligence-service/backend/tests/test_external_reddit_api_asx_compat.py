import os
import statistics
import time
from pathlib import Path

import pytest
import requests
from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")

BASE_URL = os.getenv("EXTERNAL_API_BASE_URL", "https://215fbbb9u9.execute-api.us-east-1.amazonaws.com")
TEST_EMAIL = os.getenv("EXTERNAL_API_TEST_EMAIL")
TEST_PASSWORD = os.getenv("EXTERNAL_API_TEST_PASSWORD")

ASX_QUERY = os.getenv("EXTERNAL_API_ASX_QUERY", "ASX BHP CBA NAB RBA")
ASX_SUBREDDIT = os.getenv("EXTERNAL_API_ASX_SUBREDDIT", "ASX_Bets")
ASX_LIMIT = int(os.getenv("EXTERNAL_API_ASX_LIMIT", "10"))

MIN_POST_EVENTS = int(os.getenv("EXTERNAL_API_MIN_POST_EVENTS", "3"))
MIN_COMMENT_EVENTS = int(os.getenv("EXTERNAL_API_MIN_COMMENT_EVENTS", "3"))
MIN_RELEVANCE_RATIO = float(os.getenv("EXTERNAL_API_MIN_RELEVANCE_RATIO", "0.5"))
MAX_MEDIAN_LATENCY_SECONDS = float(os.getenv("EXTERNAL_API_MAX_MEDIAN_LATENCY_SECONDS", "4.0"))
MIN_STABILITY_SUCCESS_RATIO = float(os.getenv("EXTERNAL_API_MIN_STABILITY_SUCCESS_RATIO", "0.8"))


pytestmark = pytest.mark.skipif(
    not TEST_EMAIL or not TEST_PASSWORD,
    reason="Set EXTERNAL_API_TEST_EMAIL and EXTERNAL_API_TEST_PASSWORD to run ASX compatibility tests.",
)


def _login_token() -> str:
    response = requests.post(
        f"{BASE_URL}/v1/auth/login",
        json={"email": TEST_EMAIL, "password": TEST_PASSWORD},
        timeout=20,
    )
    response.raise_for_status()
    token = response.json().get("token") or response.json().get("access_token")
    assert token, "Login succeeded but no token/access_token was returned."
    return token


def _auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _response_data(payload: dict) -> dict:
    nested = payload.get("data")
    if isinstance(nested, dict):
        return nested
    return payload


def _events(payload: dict) -> list[dict]:
    data = _response_data(payload)
    events = data.get("events")
    return events if isinstance(events, list) else []


def _search_posts(headers: dict, query: str, subreddit: str | None, limit: int = ASX_LIMIT):
    params = {"query": query, "limit": limit}
    if subreddit:
        params["subreddit"] = subreddit
    start = time.perf_counter()
    response = requests.get(
        f"{BASE_URL}/v1/post/search",
        params=params,
        headers=headers,
        timeout=30,
    )
    latency = time.perf_counter() - start
    response.raise_for_status()
    payload = response.json()
    return payload, _events(payload), latency


def _get_comments(headers: dict, link_id: str, limit: int = 10):
    response = requests.get(
        f"{BASE_URL}/v1/post/comments",
        params={"link_id": link_id, "limit": limit, "parent_id": ""},
        headers=headers,
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    return payload, _events(payload)


def _has_keys(attributes: dict, required_keys: set[str]) -> bool:
    return required_keys.issubset(set(attributes.keys()))


def _is_asx_relevant(post_event: dict) -> bool:
    attrs = post_event.get("attributes", {})
    text = " ".join(
        [
            str(attrs.get("title", "")),
            str(attrs.get("selftext", "")),
            str(attrs.get("subreddit", "")),
        ]
    ).lower()
    keywords = [
        "asx",
        "australia",
        "australian",
        "rba",
        "bhp",
        "cba",
        "nab",
        "wbc",
        "anz",
        "rio",
        "woodside",
        "westpac",
    ]
    return any(keyword in text for keyword in keywords)


def _collect_asx_posts(headers: dict, target_count: int) -> list[dict]:
    scenarios = [
        (ASX_QUERY, ASX_SUBREDDIT),
        ("ASX 200 mining banks", "investing"),
        ("RBA interest rates inflation", "australia"),
    ]
    collected: list[dict] = []
    seen_ids: set[str] = set()
    for query, subreddit in scenarios:
        _, events, _ = _search_posts(headers, query, subreddit, limit=max(10, target_count))
        for event in events:
            event_id = str(event.get("attributes", {}).get("id", ""))
            dedupe_key = event_id or f"{event.get('event_type')}-{len(collected)}"
            if dedupe_key in seen_ids:
                continue
            seen_ids.add(dedupe_key)
            collected.append(event)
        if len(collected) >= target_count:
            break
    return collected


def test_asx_data_mapping_required_fields():
    token = _login_token()
    headers = _auth_headers(token)

    payload, post_events, _ = _search_posts(headers, ASX_QUERY, ASX_SUBREDDIT, ASX_LIMIT)
    envelope = _response_data(payload)

    for field in ("data_source", "dataset_type", "dataset_id", "time_object", "events"):
        assert field in envelope

    if len(post_events) < MIN_POST_EVENTS:
        post_events = _collect_asx_posts(headers, target_count=MIN_POST_EVENTS)

    assert len(post_events) >= MIN_POST_EVENTS, (
        f"Expected at least {MIN_POST_EVENTS} ASX post events, got {len(post_events)}."
    )

    required_post_keys = {"id", "title", "author", "created_utc", "score", "subreddit"}
    post_complete = [
        event
        for event in post_events
        if _has_keys(event.get("attributes", {}), required_post_keys)
    ]
    assert len(post_complete) >= max(1, len(post_events) // 2), (
        "Too many post events are missing required project fields "
        f"{sorted(required_post_keys)}."
    )

    first_link_id = post_complete[0]["attributes"]["id"] if post_complete else post_events[0].get("attributes", {}).get("id")
    assert first_link_id, "No usable post id found for comments test."

    _, comment_events = _get_comments(headers, first_link_id, limit=20)
    assert len(comment_events) >= MIN_COMMENT_EVENTS, (
        f"Expected at least {MIN_COMMENT_EVENTS} comment events, got {len(comment_events)}."
    )

    required_comment_keys = {"id", "author", "body", "created_utc", "score"}
    comment_complete = [
        event
        for event in comment_events
        if _has_keys(event.get("attributes", {}), required_comment_keys)
    ]
    assert len(comment_complete) >= max(1, len(comment_events) // 2), (
        "Too many comment events are missing required project fields "
        f"{sorted(required_comment_keys)}."
    )


def test_asx_quality_and_coverage():
    token = _login_token()
    headers = _auth_headers(token)

    scenarios = [
        ("ASX BHP CBA NAB RBA", "ASX_Bets"),
        ("RBA interest rates inflation", "australia"),
        ("ASX 200 mining banks", "investing"),
    ]

    all_events: list[dict] = []
    for query, subreddit in scenarios:
        _, events, _ = _search_posts(headers, query, subreddit, limit=10)
        all_events.extend(events)

    assert len(all_events) >= 10, f"Expected at least 10 AU-market related events, got {len(all_events)}."

    relevant_count = sum(1 for event in all_events if _is_asx_relevant(event))
    relevance_ratio = relevant_count / len(all_events)
    assert relevance_ratio >= MIN_RELEVANCE_RATIO, (
        f"Expected relevance ratio >= {MIN_RELEVANCE_RATIO:.2f}, got {relevance_ratio:.2f}."
    )


def test_asx_performance_and_stability():
    token = _login_token()
    headers = _auth_headers(token)

    latencies: list[float] = []
    success = 0
    attempts = 5
    for _ in range(attempts):
        try:
            _, events, latency = _search_posts(headers, ASX_QUERY, ASX_SUBREDDIT, ASX_LIMIT)
            latencies.append(latency)
            if isinstance(events, list):
                success += 1
        except requests.RequestException:
            continue

    success_ratio = success / attempts
    assert success_ratio >= MIN_STABILITY_SUCCESS_RATIO, (
        f"Expected success ratio >= {MIN_STABILITY_SUCCESS_RATIO:.2f}, got {success_ratio:.2f}."
    )
    assert latencies, "No successful requests; cannot evaluate latency."
    assert statistics.median(latencies) <= MAX_MEDIAN_LATENCY_SECONDS, (
        f"Median latency too high: {statistics.median(latencies):.2f}s > {MAX_MEDIAN_LATENCY_SECONDS:.2f}s."
    )


def test_invalid_token_is_rejected():
    invalid_headers = {"Authorization": "Bearer invalid-token-for-test"}
    response = requests.get(
        f"{BASE_URL}/v1/post/search",
        params={"query": "ASX", "subreddit": "ASX_Bets", "limit": 3},
        headers=invalid_headers,
        timeout=20,
    )
    assert response.status_code in (401, 403)
