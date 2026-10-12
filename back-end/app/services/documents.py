
import time
import uuid
from datetime import datetime, timezone
from typing import Optional

from app.db import get_connection
from app.services.document_parser import extract_text
from app.services.document_summariser import summarize_document
from app.services.preprocessing import clean_text, word_count


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def create_document(filename: str, content: bytes) -> dict:
    raw_text = extract_text(filename, content)
    text = clean_text(raw_text)

    if not text:
        raise ValueError("No readable text left after cleaning.")

    document = {
        "id": str(uuid.uuid4()),
        "filename": filename,
        "file_size": len(content),
        "raw_text": raw_text,
        "clean_text": text,
        "word_count": word_count(text),
        "created_at": _now(),
    }

    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO documents
                (id, filename, file_size, raw_text, clean_text,
                 word_count, created_at)
            VALUES
                (:id, :filename, :file_size, :raw_text, :clean_text,
                 :word_count, :created_at)
            """,
            document,
        )

    return {**document, "char_count": len(text)}


def get_document(document_id: str) -> Optional[dict]:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM documents WHERE id = ?",
            (document_id,),
        ).fetchone()

    if row is None:
        return None

    document = dict(row)
    document["char_count"] = len(document["clean_text"])
    return document


def list_documents(limit: int = 50) -> list[dict]:
    """Newest first, without the full text."""
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT
                d.id, d.filename, d.file_size, d.word_count,
                LENGTH(d.clean_text) AS char_count, d.created_at,
                COUNT(s.id) AS summary_count,
                (SELECT id FROM summaries
                 WHERE document_id = d.id
                 ORDER BY created_at DESC LIMIT 1) AS latest_summary_id
            FROM documents d
            LEFT JOIN summaries s ON s.document_id = d.id
            GROUP BY d.id
            ORDER BY d.created_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

    return [dict(r) for r in rows]


def delete_document(document_id: str) -> bool:
    with get_connection() as conn:
        cursor = conn.execute(
            "DELETE FROM documents WHERE id = ?",
            (document_id,),
        )

    return cursor.rowcount > 0


def list_summaries(document_id: str) -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT * FROM summaries
            WHERE document_id = ?
            ORDER BY created_at
            """,
            (document_id,),
        ).fetchall()

    return [dict(r) for r in rows]


def get_summary(summary_id: str) -> Optional[dict]:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM summaries WHERE id = ?",
            (summary_id,),
        ).fetchone()

    return dict(row) if row else None


def create_summary(document: dict, length: str, model_key: str) -> dict:
    started = time.perf_counter()
    text = summarize_document(
        document["clean_text"],
        length=length,
        model_key=model_key,
    )
    duration_ms = int((time.perf_counter() - started) * 1000)

    summary = {
        "id": str(uuid.uuid4()),
        "document_id": document["id"],
        "model": model_key,
        "length": length,
        "text": text,
        "duration_ms": duration_ms,
        "created_at": _now(),
    }

    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO summaries
                (id, document_id, model, length, text, duration_ms, created_at)
            VALUES
                (:id, :document_id, :model, :length, :text, :duration_ms, :created_at)
            """,
            summary,
        )

    return summary
