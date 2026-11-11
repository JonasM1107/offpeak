"""One GET helper for every source: timeout, and retry with backoff on 429 and 5xx."""

import time

import requests

from offpeak.config import MAX_RETRIES, REQUEST_TIMEOUT_S

RETRY_STATUS = {429, 500, 502, 503, 504}


def get(url: str, params: dict | None = None, *, sleep=time.sleep) -> requests.Response:
    """GET with retries. Returns the last response; the caller decides what a status means."""
    for attempt in range(MAX_RETRIES + 1):
        try:
            response = requests.get(url, params=params, timeout=REQUEST_TIMEOUT_S)
        except (requests.ConnectionError, requests.Timeout):
            if attempt == MAX_RETRIES:
                raise
        else:
            if response.status_code not in RETRY_STATUS or attempt == MAX_RETRIES:
                return response
        sleep(2 ** (attempt + 1))
    raise AssertionError("unreachable")
