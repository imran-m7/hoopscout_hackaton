"""
SQLite storage for REAL players and jobs (data/hoopscout.db - local only, never online).

Each player is one row with JSON columns. Simulated players are not stored: they are
regenerated from a fixed seed at startup, so they are the same every run.
"""
import json
import sqlite3
import threading

from . import config

_LOCK = threading.Lock()
_conn = None


def connect(path=None):
    global _conn
    with _LOCK:
        if _conn is not None:
            _conn.close()
        _conn = sqlite3.connect(str(path or config.DB_PATH), check_same_thread=False)
        _conn.executescript("""
            CREATE TABLE IF NOT EXISTS players (
                id TEXT PRIMARY KEY,
                record TEXT NOT NULL,          -- JSON: input (incl. private fields), analyses, scores...
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS jobs (
                job_id TEXT PRIMARY KEY,
                player_id TEXT NOT NULL,
                record TEXT NOT NULL,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
        """)
        _conn.commit()


def _ensure():
    if _conn is None:
        connect()


def save_player(rec: dict):
    _ensure()
    data = {k: v for k, v in rec.items() if k != "summary"}   # summary is recomputed
    with _LOCK:
        _conn.execute("INSERT OR REPLACE INTO players (id, record, updated_at) "
                      "VALUES (?, ?, CURRENT_TIMESTAMP)", (rec["id"], json.dumps(data)))
        _conn.commit()


def load_players():
    _ensure()
    with _LOCK:
        rows = _conn.execute("SELECT record FROM players").fetchall()
    return [json.loads(r[0]) for r in rows]


def save_job(job: dict):
    _ensure()
    with _LOCK:
        _conn.execute("INSERT OR REPLACE INTO jobs (job_id, player_id, record, updated_at) "
                      "VALUES (?, ?, ?, CURRENT_TIMESTAMP)",
                      (job["job_id"], job["player_id"], json.dumps(job)))
        _conn.commit()


def load_jobs():
    _ensure()
    with _LOCK:
        rows = _conn.execute("SELECT record FROM jobs").fetchall()
    return [json.loads(r[0]) for r in rows]
