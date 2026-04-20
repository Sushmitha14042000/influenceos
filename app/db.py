from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any, Iterable

DB_PATH = Path("data/automation.db")


def get_conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    conn = get_conn()
    try:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS import_batches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_file TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS devices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                device_id TEXT NOT NULL UNIQUE,
                platform TEXT NOT NULL,
                model TEXT,
                os_version TEXT,
                appium_server_url TEXT NOT NULL,
                status TEXT NOT NULL,
                last_seen_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS appium_servers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                device_id TEXT NOT NULL,
                host TEXT NOT NULL,
                port INTEGER NOT NULL,
                pid INTEGER,
                status TEXT NOT NULL,
                started_at TEXT NOT NULL,
                stopped_at TEXT,
                UNIQUE(device_id),
                FOREIGN KEY(device_id) REFERENCES devices(device_id)
            );

            CREATE TABLE IF NOT EXISTS profiles (
                account_id TEXT PRIMARY KEY,
                name TEXT,
                email TEXT,
                phone TEXT,
                birthday TEXT,
                location TEXT,
                role TEXT,
                favorites_json TEXT
            );

            CREATE TABLE IF NOT EXISTS jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                batch_id INTEGER NOT NULL,
                account_id TEXT NOT NULL,
                device_id TEXT NOT NULL,
                post_url TEXT NOT NULL,
                intent TEXT NOT NULL,
                sentiment_tag TEXT NOT NULL,
                comment_template TEXT,
                priority INTEGER NOT NULL,
                description TEXT,
                status TEXT NOT NULL,
                error_message TEXT,
                created_at TEXT NOT NULL,
                started_at TEXT,
                finished_at TEXT,
                evidence_path TEXT,
                FOREIGN KEY(batch_id) REFERENCES import_batches(id)
            );

            CREATE TABLE IF NOT EXISTS planned_steps (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id INTEGER NOT NULL,
                step_order INTEGER NOT NULL,
                action TEXT NOT NULL,
                value TEXT,
                min_wait_ms INTEGER NOT NULL,
                max_wait_ms INTEGER NOT NULL,
                FOREIGN KEY(job_id) REFERENCES jobs(id)
            );

            CREATE TABLE IF NOT EXISTS run_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id INTEGER NOT NULL,
                level TEXT NOT NULL,
                message TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(job_id) REFERENCES jobs(id)
            );

            CREATE TABLE IF NOT EXISTS insights (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id INTEGER,
                post_id TEXT,
                event TEXT,
                views INTEGER,
                likes INTEGER,
                comments INTEGER,
                timestamp TEXT
            );
            """
        )
        conn.commit()
    finally:
        conn.close()


def execute(query: str, params: Iterable[Any] | None = None) -> None:
    conn = get_conn()
    try:
        conn.execute(query, tuple(params or []))
        conn.commit()
    finally:
        conn.close()


def execute_many(query: str, rows: list[tuple[Any, ...]]) -> None:
    conn = get_conn()
    try:
        conn.executemany(query, rows)
        conn.commit()
    finally:
        conn.close()


def fetch_all(query: str, params: Iterable[Any] | None = None) -> list[sqlite3.Row]:
    conn = get_conn()
    try:
        cursor = conn.execute(query, tuple(params or []))
        return cursor.fetchall()
    finally:
        conn.close()


def fetch_one(query: str, params: Iterable[Any] | None = None) -> sqlite3.Row | None:
    conn = get_conn()
    try:
        cursor = conn.execute(query, tuple(params or []))
        return cursor.fetchone()
    finally:
        conn.close()
