import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "app"))
import perf  # noqa: E402


def test_timings_keep_the_last_runs_per_page(monkeypatch):
    monkeypatch.setattr(perf, "_runs", perf.defaultdict(lambda: perf.deque(maxlen=20)))
    for _ in range(25):
        with perf.timed("Power"):
            pass
    (row,) = perf.summary()
    assert row["page"] == "Power" and row["runs"] == 20 and row["last_s"] >= 0
