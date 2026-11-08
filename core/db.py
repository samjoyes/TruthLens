"""SQLite database layer for persisting analyses."""

import sqlite3
from contextlib import contextmanager
from typing import Any, Generator, Optional

from core.config import DB_PATH
from core.schemas import AnalysisResult


@contextmanager
def get_db_connection(db_path: Optional[str] = None) -> Generator[sqlite3.Connection, None, None]:
    """Context manager for SQLite connections with row factory and auto-commit."""
    target_path = db_path or DB_PATH
    conn = sqlite3.connect(target_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db(db_path: Optional[str] = None) -> None:
    """Initialize the SQLite database schema if it doesn't exist."""
    schema_sql = """
    CREATE TABLE IF NOT EXISTS analyses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        input_type TEXT NOT NULL,
        headline TEXT NOT NULL,
        source_url TEXT,
        verdict TEXT NOT NULL,
        confidence INTEGER NOT NULL,
        credibility INTEGER NOT NULL,
        result_json TEXT NOT NULL
    );
    """
    with get_db_connection(db_path) as conn:
        conn.execute(schema_sql)


def save_analysis(
    input_type: str,
    headline: str,
    source_url: Optional[str],
    result: AnalysisResult,
    db_path: Optional[str] = None,
) -> int:
    """Persist an analysis result in SQLite using parameterized queries."""
    insert_sql = """
    INSERT INTO analyses (
        input_type,
        headline,
        source_url,
        verdict,
        confidence,
        credibility,
        result_json
    ) VALUES (?, ?, ?, ?, ?, ?, ?);
    """
    result_json = result.model_dump_json()
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            insert_sql,
            (
                input_type,
                headline,
                source_url,
                result.verdict,
                result.confidence,
                result.credibility_score,
                result_json,
            ),
        )
        return int(cursor.lastrowid)


def list_history(limit: int = 50, db_path: Optional[str] = None) -> list[dict[str, Any]]:
    """Retrieve historical analyses ordered by newest first."""
    select_sql = """
    SELECT id, created_at, input_type, headline, source_url, verdict, confidence, credibility, result_json
    FROM analyses
    ORDER BY id DESC
    LIMIT ?;
    """
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(select_sql, (limit,))
        rows = cursor.fetchall()
        return [dict(row) for row in rows]


def get_analysis(analysis_id: int, db_path: Optional[str] = None) -> Optional[dict[str, Any]]:
    """Fetch a single analysis record by ID and parse the stored JSON."""
    select_sql = """
    SELECT id, created_at, input_type, headline, source_url, verdict, confidence, credibility, result_json
    FROM analyses
    WHERE id = ?;
    """
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(select_sql, (analysis_id,))
        row = cursor.fetchone()
        if not row:
            return None

        record = dict(row)
        record["result"] = AnalysisResult.model_validate_json(record["result_json"])
        return record


def delete_analysis(analysis_id: int, db_path: Optional[str] = None) -> bool:
    """Delete an analysis record by ID. Returns True if a record was removed."""
    delete_sql = "DELETE FROM analyses WHERE id = ?;"
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(delete_sql, (analysis_id,))
        return cursor.rowcount > 0
