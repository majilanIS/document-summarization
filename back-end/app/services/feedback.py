
import json
import uuid
from datetime import datetime, timezone

from app.db import get_connection
from app.models.schemas import FeedbackCreate
from app.services.documents import get_summary


def save_feedback(data: FeedbackCreate) -> dict:
    if data.summary_id is not None:
        summary = get_summary(data.summary_id)
        if summary is None:
            raise LookupError("Summary not found")
        document_id = summary["document_id"]

    else:
        summary_a = get_summary(data.summary_a_id)
        summary_b = get_summary(data.summary_b_id)
        if summary_a is None or summary_b is None:
            raise LookupError("Summary not found")
        if summary_a["document_id"] != summary_b["document_id"]:
            raise ValueError("Both summaries must belong to the same document")
        document_id = summary_a["document_id"]

    feedback = {
        "id": str(uuid.uuid4()),
        "document_id": document_id,
        "summary_id": data.summary_id,
        "rating": data.rating,
        "summary_a_id": data.summary_a_id,
        "summary_b_id": data.summary_b_id,
        "preferred": data.preferred,
        # Deduplicated, in a stable order.
        "aspects": sorted(set(data.aspects)),
        "comment": data.comment,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO feedback
                (id, document_id, summary_id, rating, summary_a_id,
                 summary_b_id, preferred, aspects, comment, created_at)
            VALUES
                (:id, :document_id, :summary_id, :rating, :summary_a_id,
                 :summary_b_id, :preferred, :aspects, :comment, :created_at)
            """,
            {**feedback, "aspects": json.dumps(feedback["aspects"])},
        )

    return feedback


def _row_to_feedback(row) -> dict:
    feedback = dict(row)
    feedback["aspects"] = json.loads(feedback["aspects"] or "[]")
    return feedback


def list_feedback(document_id: str) -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT * FROM feedback
            WHERE document_id = ?
            ORDER BY created_at
            """,
            (document_id,),
        ).fetchall()

    return [_row_to_feedback(r) for r in rows]


def list_recent_feedback(limit: int = 50) -> list[dict]:
    """Newest first, with the document name and rated summary details."""
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT f.*, d.filename, s.model, s.length
            FROM feedback f
            JOIN documents d ON d.id = f.document_id
            LEFT JOIN summaries s ON s.id = f.summary_id
            ORDER BY f.created_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

    return [_row_to_feedback(r) for r in rows]


def feedback_stats() -> dict:
    """Average rating and head-to-head results per model."""
    with get_connection() as conn:
        total = conn.execute("SELECT COUNT(*) FROM feedback").fetchone()[0]

        aspect_rows = conn.execute(
            "SELECT aspects FROM feedback WHERE aspects != '[]'"
        ).fetchall()

        ratings = conn.execute(
            """
            SELECT s.model, COUNT(*) AS n, AVG(f.rating) AS avg_rating
            FROM feedback f
            JOIN summaries s ON s.id = f.summary_id
            WHERE f.rating IS NOT NULL
            GROUP BY s.model
            """
        ).fetchall()

        comparisons = conn.execute(
            """
            SELECT a.model AS model_a, b.model AS model_b, f.preferred
            FROM feedback f
            JOIN summaries a ON a.id = f.summary_a_id
            JOIN summaries b ON b.id = f.summary_b_id
            WHERE f.preferred IS NOT NULL
            """
        ).fetchall()

    stats = {}

    def entry(model: str) -> dict:
        return stats.setdefault(model, {
            "model": model,
            "ratings": 0,
            "average_rating": None,
            "comparisons": 0,
            "wins": 0,
            "losses": 0,
            "ties": 0,
        })

    for row in ratings:
        e = entry(row["model"])
        e["ratings"] = row["n"]
        e["average_rating"] = round(row["avg_rating"], 2)

    for row in comparisons:
        # Same-model comparisons (e.g. short vs detailed) say nothing
        # about which model is better.
        if row["model_a"] == row["model_b"]:
            continue

        a, b = entry(row["model_a"]), entry(row["model_b"])
        a["comparisons"] += 1
        b["comparisons"] += 1

        if row["preferred"] == "tie":
            a["ties"] += 1
            b["ties"] += 1
        elif row["preferred"] == "a":
            a["wins"] += 1
            b["losses"] += 1
        else:
            b["wins"] += 1
            a["losses"] += 1

    aspects = {}
    for row in aspect_rows:
        for aspect in json.loads(row["aspects"]):
            aspects[aspect] = aspects.get(aspect, 0) + 1

    return {
        "total_feedback": total,
        "aspects": aspects,
        "models": sorted(stats.values(), key=lambda s: s["model"]),
    }
