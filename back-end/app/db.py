
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path


DATABASE_PATH = Path(
    os.getenv(
        "DATABASE_PATH",
        Path(__file__).resolve().parent.parent / "data" / "app.db",
    )
)

SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
    id          TEXT PRIMARY KEY,
    filename    TEXT NOT NULL,
    raw_text    TEXT NOT NULL,
    clean_text  TEXT NOT NULL,
    word_count  INTEGER NOT NULL,
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS summaries (
    id           TEXT PRIMARY KEY,
    document_id  TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    model        TEXT NOT NULL,
    length       TEXT NOT NULL,
    text         TEXT NOT NULL,
    duration_ms  INTEGER NOT NULL,
    created_at   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS feedback (
    id                    TEXT PRIMARY KEY,
    document_id           TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    summary_id            TEXT REFERENCES summaries(id) ON DELETE CASCADE,
    rating                INTEGER CHECK (rating BETWEEN 1 AND 5),
    summary_a_id          TEXT REFERENCES summaries(id) ON DELETE CASCADE,
    summary_b_id          TEXT REFERENCES summaries(id) ON DELETE CASCADE,
    preferred             TEXT CHECK (preferred IN ('a', 'b', 'tie')),
    comment               TEXT,
    created_at            TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_summaries_document ON summaries(document_id);
CREATE INDEX IF NOT EXISTS idx_feedback_document ON feedback(document_id);
"""


def init_db() -> None:
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with get_connection() as conn:
        conn.executescript(SCHEMA)


@contextmanager
def get_connection():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
