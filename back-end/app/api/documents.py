
from fastapi import APIRouter, File, HTTPException, UploadFile

from app.models.schemas import DocumentOut, DocumentUploadOut
from app.services import documents


router = APIRouter(prefix="/api/documents", tags=["documents"])

MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB


@router.post("/upload", response_model=DocumentUploadOut, status_code=201)
def upload_document(file: UploadFile = File(...)):
    if not file.filename:
        raise HTTPException(400, "File name is missing")

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
