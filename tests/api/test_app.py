"""Tests for FastAPI application factory."""

from __future__ import annotations

import os
import sqlite3
import tempfile
from pathlib import Path

from fastapi.testclient import TestClient
from unittest.mock import patch

from poker_analytics.app import create_app


def test_health_endpoint() -> None:
    client = TestClient(create_app())
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_metadata_endpoint() -> None:
    client = TestClient(create_app())
    response = client.get("/api/metadata")
    assert response.status_code == 200
    payload = response.json()
    assert payload["service"] == "Poker Analytics"
    assert payload["version"] == "0.1.0"


def test_flop_summary_endpoint() -> None:
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    db_path = Path(tmp.name)
    try:
        with sqlite3.connect(db_path) as conn:
            conn.executescript(
                """
                CREATE TABLE hands (hand_id TEXT PRIMARY KEY, board_flop TEXT);
                CREATE TABLE seats (hand_id TEXT, seat_no INTEGER, player_name TEXT, is_hero INTEGER);
                CREATE TABLE actions (hand_id TEXT, street TEXT, actor TEXT, action TEXT, amount REAL);

                INSERT INTO hands VALUES ('H1', 'Ah Kh Qh');
                INSERT INTO seats VALUES ('H1', 1, 'Hero', 1);
                INSERT INTO actions VALUES ('H1', 'flop', 'Hero', 'bet', 0.6);
                INSERT INTO actions VALUES ('H1', 'flop', 'Villain', 'fold', 0.0);
                """
            )
        os.environ["DRIVEHUD_DB_PATH"] = str(db_path)
        client = TestClient(create_app())
        response = client.get("/api/flop/summary")
        assert response.status_code == 200
        payload = response.json()
        assert payload["events"] == 1
        buckets = {item["key"]: item["count"] for item in payload["buckets"]}
        assert buckets["pct_60_80"] == 1
    finally:
        os.environ.pop("DRIVEHUD_DB_PATH", None)
        db_path.unlink(missing_ok=True)


@patch('poker_analytics.api.preflop.get_shove_range_payload')
def test_preflop_shove_ranges_endpoint(mock_payload) -> None:
    mock_payload.return_value = [{"id": "range"}]
    client = TestClient(create_app())
    response = client.get('/api/preflop/shove/ranges')
    assert response.status_code == 200
    assert response.json() == [{"id": "range"}]
    mock_payload.assert_called_once()


@patch('poker_analytics.api.preflop.get_equity_payload')
def test_preflop_shove_equity_endpoint(mock_payload) -> None:
    mock_payload.return_value = [{"id": "equity"}]
    client = TestClient(create_app())
    response = client.get('/api/preflop/shove/equity')
    assert response.status_code == 200
    assert response.json() == [{"id": "equity"}]
    mock_payload.assert_called_once()


@patch('poker_analytics.api.preflop.get_response_curve_payload')
def test_preflop_response_curves_endpoint(mock_payload) -> None:
    mock_payload.return_value = [{"id": "curve"}]
    client = TestClient(create_app())
    response = client.get('/api/preflop/response-curves')
    assert response.status_code == 200
    assert response.json() == [{"id": "curve"}]
    mock_payload.assert_called_once()
