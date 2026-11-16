import pytest
import requests

from offpeak import http


class Reply:
    def __init__(self, status):
        self.status_code = status


def test_retries_follow_the_setting(monkeypatch):
    monkeypatch.setattr(http, "retries", http.MAX_RETRIES)  # the default, as in the jobs
    calls, waits = [], []
    monkeypatch.setattr(
        http.requests, "get", lambda url, params, timeout: calls.append(1) or Reply(429)
    )
    assert http.get("u", sleep=waits.append).status_code == 429  # the caller decides what 429 means
    assert len(calls) == http.MAX_RETRIES + 1 and waits == [2, 4, 8, 16]  # jobs: nobody waits

    calls.clear(), waits.clear()
    monkeypatch.setattr(http, "retries", 1)  # the app: a visitor is waiting
    http.get("u", sleep=waits.append)
    assert len(calls) == 2 and waits == [2]


def test_no_retry_after_success_and_errors_surface_after_the_last_try(monkeypatch):
    monkeypatch.setattr(http, "retries", 1)
    calls = []
    monkeypatch.setattr(
        http.requests, "get", lambda url, params, timeout: calls.append(1) or Reply(200)
    )
    assert http.get("u", sleep=lambda s: None).status_code == 200 and len(calls) == 1

    def down(url, params, timeout):
        raise requests.ConnectionError("down")

    monkeypatch.setattr(http.requests, "get", down)
    with pytest.raises(requests.ConnectionError):
        http.get("u", sleep=lambda s: None)
