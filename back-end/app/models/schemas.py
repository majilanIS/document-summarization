
from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field, model_validator


SummaryLength = Literal["short", "medium", "detailed"]
ModelKey = Literal["gemini", "distilbart", "flan-t5"]
Aspect = Literal["accuracy", "clarity", "coverage", "conciseness"]


class SummaryOut(BaseModel):
    id: str
    document_id: str
    model: str
    length: str
    text: str
    duration_ms: int
    # Reward model score, and how many candidates it was chosen from.
    reward: Optional[float] = None
    candidates: int = 1
    # Share of hallucination checks passed, 0..1 (Gemini summaries only).
    grounding: Optional[float] = None
    created_at: datetime


class DocumentUploadOut(BaseModel):
    id: str
    filename: str
    file_size: int
    word_count: int
    char_count: int
    preview: str
    created_at: datetime


class DocumentOut(BaseModel):
    id: str
    filename: str
    file_size: int
    word_count: int
    char_count: int
    text: str
    created_at: datetime
    summaries: list[SummaryOut]


class DocumentListItem(BaseModel):
    id: str
    filename: str
    file_size: int
    word_count: int
    char_count: int
    created_at: datetime
    summary_count: int
    latest_summary_id: Optional[str]


class SummaryRequest(BaseModel):
    document_id: str
    length: SummaryLength = "medium"
    # None: Gemini when GEMINI_API_KEY is set, otherwise distilbart.
    model: Optional[ModelKey] = None


class FeedbackCreate(BaseModel):
    """Either rate one summary (summary_id + rating) or compare two
    (summary_a_id + summary_b_id + preferred)."""

    summary_id: Optional[str] = None
    rating: Optional[int] = Field(default=None, ge=1, le=5)

    summary_a_id: Optional[str] = None
    summary_b_id: Optional[str] = None
    preferred: Optional[Literal["a", "b", "tie"]] = None

    # What the user liked about the summary.
    aspects: list[Aspect] = Field(default_factory=list)
    comment: Optional[str] = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def check_kind(self):
        is_rating = self.summary_id is not None or self.rating is not None
        is_comparison = any(
            v is not None
            for v in (self.summary_a_id, self.summary_b_id, self.preferred)
        )

        if is_rating == is_comparison:
            raise ValueError(
                "Send either summary_id + rating, or "
                "summary_a_id + summary_b_id + preferred"
            )

        if is_rating and (self.summary_id is None or self.rating is None):
            raise ValueError("A rating needs both summary_id and rating")

        if is_comparison:
            if None in (self.summary_a_id, self.summary_b_id, self.preferred):
                raise ValueError(
                    "A comparison needs summary_a_id, summary_b_id "
                    "and preferred"
                )
            if self.summary_a_id == self.summary_b_id:
                raise ValueError("Compare two different summaries")

        return self


class FeedbackOut(BaseModel):
    id: str
    document_id: str
    summary_id: Optional[str]
    rating: Optional[int]
    summary_a_id: Optional[str]
    summary_b_id: Optional[str]
    preferred: Optional[str]
    aspects: list[str]
    comment: Optional[str]
    created_at: datetime


class FeedbackListItem(FeedbackOut):
    filename: str
    # Model and length of the rated summary (rating feedback only).
    model: Optional[str]
    length: Optional[str]


class ModelStats(BaseModel):
    model: str
    ratings: int
    average_rating: Optional[float]
    comparisons: int
    wins: int
    losses: int
    ties: int


class FeedbackStats(BaseModel):
    total_feedback: int
    # How many times each aspect was ticked.
    aspects: dict[str, int]
    models: list[ModelStats]
    # Thumbs up / down on chat answers.
    chat_helpful: int
    chat_unhelpful: int


class RewardWeight(BaseModel):
    feature: str
    weight: float
    prior: float


class RewardModelStatus(BaseModel):
    # "prior" until there is enough feedback, then "learned".
    mode: Literal["prior", "learned"]
    ratings: int
    pairs: int
    min_feedback: int
    candidates: int
    trained_at: Optional[datetime]
    weights: list[RewardWeight]


class ChatSource(BaseModel):
    # quote: verified verbatim quote the answer's points cite by number;
    # document / summary: retrieved passage the answer may be based on.
    kind: Literal["quote", "document", "summary"]
    text: str


class ChatPoint(BaseModel):
    # May start with a **bold** key term.
    text: str
    # 1-based number of the source that supports it.
    source: Optional[int]


class ChatDetails(BaseModel):
    """Structured form of a Gemini answer."""

    direct_answer: str
    points: list[ChatPoint]
    not_covered: Optional[str]
    # Figures in the answer could not be found in the document.
    unverified: bool


class ChatMessageOut(BaseModel):
    id: str
    document_id: str
    role: Literal["user", "assistant"]
    # Plain-text answer (always set; the only form for local answers).
    content: str
    sources: list[ChatSource]
    details: Optional[ChatDetails] = None
    engine: Optional[str]
    rating: Optional[int]
    created_at: datetime


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)


class ChatReply(BaseModel):
    question: ChatMessageOut
    answer: ChatMessageOut


class ChatRating(BaseModel):
    # 1 = helpful, -1 = not helpful, null = remove the rating.
    rating: Optional[Literal[-1, 1]]
