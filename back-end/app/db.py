
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
    file_size   INTEGER NOT NULL DEFAULT 0,
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
    -- Reward model score and how many candidates it chose from (RLHF).
    reward       REAL,
    candidates   INTEGER NOT NULL DEFAULT 1,
    -- Share of hallucination checks passed (Gemini summaries only).
    grounding    REAL,
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
    aspects               TEXT NOT NULL DEFAULT '[]',
    comment               TEXT,
    created_at            TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS chat_messages (
    id           TEXT PRIMARY KEY,
    document_id  TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    role         TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content      TEXT NOT NULL,
    -- Passages of the document the answer was based on (JSON list).
    sources      TEXT NOT NULL DEFAULT '[]',
    -- Structured answer: direct answer, cited points, gaps (JSON).
    details      TEXT,
    engine       TEXT,
    -- Thumbs up (1) or down (-1) on an answer.
    rating       INTEGER CHECK (rating IN (-1, 1)),
    created_at   TEXT NOT NULL
);

-- (document_id, created_at) also serves the ordered and "latest" lookups.
DROP INDEX IF EXISTS idx_summaries_document;
DROP INDEX IF EXISTS idx_chat_document;
CREATE INDEX IF NOT EXISTS idx_summaries_document_created
    ON summaries(document_id, created_at);
CREATE INDEX IF NOT EXISTS idx_feedback_document ON feedback(document_id);
CREATE INDEX IF NOT EXISTS idx_feedback_created ON feedback(created_at);
CREATE INDEX IF NOT EXISTS idx_chat_document_created
    ON chat_messages(document_id, created_at);
"""


# Columns added after the first release, so existing databases get them too.
MIGRATIONS = [
    ("documents", "file_size", "INTEGER NOT NULL DEFAULT 0"),
    ("feedback", "aspects", "TEXT NOT NULL DEFAULT '[]'"),
    ("summaries", "reward", "REAL"),
    ("summaries", "candidates", "INTEGER NOT NULL DEFAULT 1"),
    ("summaries", "grounding", "REAL"),
    ("chat_messages", "details", "TEXT"),
]


def init_db() -> None:
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with get_connection() as conn:
        # Readers don't block the writer (and vice versa). Stored in the
        # database file, so setting it once is enough.
        conn.execute("PRAGMA journal_mode = WAL")
        conn.executescript(SCHEMA)

        for table, column, definition in MIGRATIONS:
            columns = {
                row["name"]
                for row in conn.execute(f"PRAGMA table_info({table})")
            }
            if column not in columns:
                conn.execute(
                    f"ALTER TABLE {table} ADD COLUMN {column} {definition}"
                )


@contextmanager
def get_connection():
    # Wait for a concurrent writer instead of failing with "database is locked".
    conn = sqlite3.connect(DATABASE_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    # Safe with WAL and much faster than the default FULL.
    conn.execute("PRAGMA synchronous = NORMAL")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
