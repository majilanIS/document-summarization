
from fastapi import APIRouter, HTTPException, Query

from app.models.schemas import (
    FeedbackCreate,
    FeedbackListItem,
    FeedbackOut,
    FeedbackStats,
)
from app.services import documents, feedback


router = APIRouter(prefix="/api/feedback", tags=["feedback"])


@router.post("", response_model=FeedbackOut, status_code=201)
def create_feedback(data: FeedbackCreate):
    try:
        return feedback.save_feedback(data)
    except LookupError as error:
        raise HTTPException(404, str(error))
    except ValueError as error:
        raise HTTPException(422, str(error))


@router.get("", response_model=list[FeedbackListItem])
def get_recent_feedback(limit: int = Query(50, ge=1, le=200)):
    return feedback.list_recent_feedback(limit)


@router.get("/stats", response_model=FeedbackStats)
def get_stats():
    return feedback.feedback_stats()


@router.get("/document/{document_id}", response_model=list[FeedbackOut])
def get_document_feedback(document_id: str):
    if documents.get_document(document_id) is None:
        raise HTTPException(404, "Document not found")

    return feedback.list_feedback(document_id)
