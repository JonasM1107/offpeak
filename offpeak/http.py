"""One GET helper for every source: timeout, and retry with backoff on 429 and 5xx."""

import time

import requests

from offpeak.config import MAX_RETRIES, REQUEST_TIMEOUT_S

RETRY_STATUS = {429, 500, 502, 503, 504}
# How often to retry, and how long to wait for an answer. Jobs keep the defaults (four
# retries with waits of 2, 4, 8, 16 s; 30 s per answer): nobody waits for them. The app sets
# both lower (app/data.py), because a visitor is waiting for the page.
retries = MAX_RETRIES
timeout_s = REQUEST_TIMEOUT_S


def get(
    url: str, params: dict | None = None, *, sleep=time.sleep, timeout: float | None = None
) -> requests.Response:
    """GET with retries. Returns the last response; the caller decides what a status means.
    `timeout` overrides the usual wait for large requests (history, satellite data)."""
    for attempt in range(retries + 1):
        try:
            response = requests.get(url, params=params, timeout=timeout or timeout_s)
        except (requests.ConnectionError, requests.Timeout):
            if attempt == retries:
                raise
        else:
            if response.status_code not in RETRY_STATUS or attempt == retries:
                return response
        sleep(2 ** (attempt + 1))
    raise AssertionError("unreachable")
