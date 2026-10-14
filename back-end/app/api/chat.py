
from fastapi import APIRouter, HTTPException

from app.models.schemas import ChatMessageOut, ChatRating, ChatReply, ChatRequest
from app.services import chat, documents


router = APIRouter(prefix="/api/chat", tags=["chat"])


def _document_or_404(document_id: str) -> dict:
    document = documents.get_document(document_id)
    if document is None:
        raise HTTPException(404, "Document not found")
    return document


@router.get("/{document_id}", response_model=list[ChatMessageOut])
def get_messages(document_id: str):
    _document_or_404(document_id)
    return chat.list_messages(document_id)


# Plain `def`: the local model runs in FastAPI's thread pool.
@router.post("/{document_id}", response_model=ChatReply, status_code=201)
def send_message(document_id: str, request: ChatRequest):
    document = _document_or_404(document_id)
    question = request.message.strip()
    if not question:
        raise HTTPException(422, "Message is empty")

    summaries = documents.list_summaries(document_id)
    latest = summaries[-1]["text"] if summaries else None

    try:
        asked, answer = chat.ask(document, latest, question)
    except chat.ChatError as error:
        raise HTTPException(502, str(error))

    return {"question": asked, "answer": answer}


@router.delete("/{document_id}", status_code=204)
def clear_messages(document_id: str):
    _document_or_404(document_id)
    chat.clear_messages(document_id)


@router.put("/messages/{message_id}/rating", response_model=ChatMessageOut)
def rate_message(message_id: str, data: ChatRating):
    message = chat.rate_message(message_id, data.rating)
    if message is None:
        raise HTTPException(404, "Answer not found")
    return message
