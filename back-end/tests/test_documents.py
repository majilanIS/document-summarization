
from app.api.documents import MAX_UPLOAD_BYTES
from app.db import get_connection


def test_upload_over_limit_is_rejected(client):
    response = client.post(
        "/api/documents/upload",
        files={"file": ("big.txt", b"a " * (MAX_UPLOAD_BYTES // 2 + 1))},
    )
    assert response.status_code == 413


def test_get_document_returns_text_and_counts(client, document):
    response = client.get(f"/api/documents/{document['id']}")
    assert response.status_code == 200
    body = response.json()
    assert body["char_count"] == len(body["text"])
    assert body["word_count"] == document["word_count"]


def test_database_uses_wal(client):
    with get_connection() as conn:
        assert conn.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
