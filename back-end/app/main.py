
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from app.api import documents, feedback, summaries
from app.db import init_db
from app.services.document_summariser import MODELS, is_loaded


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="Document Summarization API",
    version="0.1.0",
    lifespan=lifespan,
)

allowed_origins = os.getenv(
    "ALLOWED_ORIGINS",
    "http://localhost:5173,http://localhost:3000",
).split(",")

# Also allow the front-end when it is opened via 127.0.0.1 or the machine's
# local network address (e.g. http://10.200.14.100:3000), on any port.
LOCAL_ORIGIN_REGEX = (
    r"https?://("
    r"localhost|127\.0\.0\.1"
    r"|10\.\d{1,3}\.\d{1,3}\.\d{1,3}"
    r"|192\.168\.\d{1,3}\.\d{1,3}"
    r"|172\.(1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3}"
    r")(:\d+)?"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in allowed_origins if o.strip()],
    allow_origin_regex=os.getenv("ALLOWED_ORIGIN_REGEX", LOCAL_ORIGIN_REGEX),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(documents.router)
app.include_router(summaries.router)
app.include_router(feedback.router)


@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse(url="/docs")


@app.get("/api/health", tags=["system"])
def health():
    return {"status": "ok"}


@app.get("/api/models", tags=["system"])
def list_models():
    return [
        {"key": key, "name": config.name, "loaded": is_loaded(key)}
        for key, config in MODELS.items()
    ]
