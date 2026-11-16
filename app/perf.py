"""How long the server takes to build each page, for the Account page.

Kept in memory (the last 20 runs per page) while the app process runs. It separates the
time our code needs from the time the browser and Streamlit Cloud add around it.
"""

import time
from collections import defaultdict, deque
from contextlib import contextmanager

_runs: dict[str, deque] = defaultdict(lambda: deque(maxlen=20))


@contextmanager
def timed(page: str):
    start = time.perf_counter()
    try:
        yield
    finally:
        _runs[page].append(time.perf_counter() - start)


def summary() -> list[dict]:
    """Per page: runs measured, the latest and the median time in seconds."""
    out = []
    for page, runs in sorted(_runs.items()):
        ordered = sorted(runs)
        out.append(
            {
                "page": page,
                "runs": len(runs),
                "last_s": round(runs[-1], 2),
                "median_s": round(ordered[len(ordered) // 2], 2),
            }
        )
    return out
