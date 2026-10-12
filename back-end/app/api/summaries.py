
from fastapi import APIRouter, HTTPException

from app.models.schemas import SummaryOut, SummaryRequest
from app.services import documents


router = APIRouter(prefix="/api/summaries", tags=["summaries"])


# A plain `def` endpoint runs in FastAPI's thread pool, so slow model
# inference does not block other requests.
@router.post("/generate", response_model=SummaryOut, status_code=201)
def generate_summary(request: SummaryRequest):
    document = documents.get_document(request.document_id)

    if document is None:
        raise HTTPException(404, "Document not found")

    try:
        return documents.create_summary(
            document,
            length=request.length,
            model_key=request.model,
        )
    except ValueError as error:
        raise HTTPException(422, str(error))


@router.get("/{summary_id}", response_model=SummaryOut)
def get_summary(summary_id: str):
    summary = documents.get_summary(summary_id)

    if summary is None:
        raise HTTPException(404, "Summary not found")

    return summary
