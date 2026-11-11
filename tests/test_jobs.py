from datetime import datetime
from unittest.mock import patch

from offpeak import db
from offpeak.jobs import ingest_prices, runner
from offpeak.markets.energy_charts import empty_prices, parse_prices


def test_price_job_stores_tomorrow_then_skips(engine, load_fixture, monkeypatch):
    tomorrow = parse_prices(load_fixture("prices_sample.json"))  # 10 Nov 2026
    monkeypatch.setattr(ingest_prices, "market_today", lambda: datetime(2026, 11, 9).date())
    monkeypatch.setattr(db, "database_url", lambda: "unused")
    monkeypatch.setattr(db, "get_engine", lambda url: engine)

    with patch.object(ingest_prices.energy_charts, "fetch_day_ahead", return_value=tomorrow):
        assert runner.run("ingest_prices", ingest_prices.ingest) == 0
    with patch.object(ingest_prices.energy_charts, "fetch_day_ahead") as fetch:
        assert runner.run("ingest_prices", ingest_prices.ingest) == 0
        fetch.assert_not_called()  # already stored: no API call

    runs = db.recent_job_runs(engine)
    assert runs["status"].tolist() == ["skipped", "ok"]
    assert runs["rows_written"].tolist() == [0, 96]


def test_price_job_before_publication_is_skipped_not_failed(engine, monkeypatch):
    monkeypatch.setattr(db, "database_url", lambda: "unused")
    monkeypatch.setattr(db, "get_engine", lambda url: engine)
    with patch.object(ingest_prices.energy_charts, "fetch_day_ahead", return_value=empty_prices()):
        assert runner.run("ingest_prices", ingest_prices.ingest) == 0
    assert db.recent_job_runs(engine)["status"].tolist() == ["skipped"]


def test_failure_is_logged_and_returns_error_code(engine, monkeypatch):
    monkeypatch.setattr(db, "database_url", lambda: "unused")
    monkeypatch.setattr(db, "get_engine", lambda url: engine)

    def boom(engine):
        raise RuntimeError("Energy-Charts HTTP 500")

    assert runner.run("ingest_prices", boom) == 1
    run = db.recent_job_runs(engine).iloc[0]
    assert run["status"] == "failed"
    assert "HTTP 500" in run["message"]


def test_without_database_url_the_job_does_nothing(monkeypatch):
    monkeypatch.setattr(db, "database_url", lambda: None)
    assert runner.run("ingest_prices", lambda engine: 1 / 0) == 0
