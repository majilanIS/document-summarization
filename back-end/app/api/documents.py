
from fastapi import APIRouter, File, HTTPException, Query, UploadFile

from app.models.schemas import (
    DocumentListItem,
    DocumentOut,
    DocumentUploadOut,
)
from app.services import documents


router = APIRouter(prefix="/api/documents", tags=["documents"])

MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB


@router.post("/upload", response_model=DocumentUploadOut, status_code=201)
def upload_document(file: UploadFile = File(...)):
    if not file.filename:
        raise HTTPException(400, "File name is missing")

    # Reject before reading when the size is already known.
    if file.size is not None and file.size > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "File is larger than 10 MB")

    content = file.file.read(MAX_UPLOAD_BYTES + 1)

    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "File is larger than 10 MB")

    try:
        document = documents.create_document(file.filename, content)
    except ValueError as error:
        raise HTTPException(422, str(error))

    return {
        **document,
        "preview": document["clean_text"][:500],
    }


@router.get("", response_model=list[DocumentListItem])
def list_documents(limit: int = Query(50, ge=1, le=200)):
    return documents.list_documents(limit)


@router.delete("/{document_id}", status_code=204)
def delete_document(document_id: str):
    if not documents.delete_document(document_id):
        raise HTTPException(404, "Document not found")


@router.get("/{document_id}", response_model=DocumentOut)
def get_document(document_id: str):
    document = documents.get_document(document_id)

    if document is None:
        raise HTTPException(404, "Document not found")

    return {
        **document,
        "text": document["clean_text"],
        "summaries": documents.list_summaries(document_id),
    }
