# Document Summarization — Back-end

FastAPI service that extracts text from documents, cleans it, summarizes it with
Hugging Face models, and collects user feedback on the summaries.

## Pipeline

1. **Extraction** (`app/services/document_parser.py`): reads text from PDF (PyMuPDF), DOCX (including tables) and TXT files.
2. **Preprocessing** (`app/services/preprocessing.py`): normalizes Unicode, rejoins words hyphenated across lines, drops page-number lines, and merges layout line breaks into paragraphs.
3. **Summarization** (`app/services/document_summariser.py`): the summary length is a share of the document: `short` ≈ 10%, `medium` ≈ 20%, `detailed` ≈ 30%, with a minimum of about 25 words and a maximum of about 1,100 words. The text is split into chunks on paragraph boundaries, and each chunk gets its share of that length based on its own size. The chunk summaries become the summary's paragraphs.
   - `distilbart`: `sshleifer/distilbart-cnn-12-6` (default)
   - `flan-t5`: `google/flan-t5-base`

   Each model is downloaded and loaded the first time it is used.
4. **Feedback** (`app/services/feedback.py`): saves a 1–5 rating for one summary, or a preference (`a`, `b` or `tie`) between two summaries of the same document.

Data is stored in SQLite at `data/app.db`.

## Run

```bash
cd back-end
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0
```

`--host 0.0.0.0` lets the front-end reach the API when it is opened through the
machine's network address (e.g. `http://10.200.14.100:3000`), not only `localhost`.

Interactive docs: http://localhost:8000/docs

### Environment variables

| Variable          | Default                                       |
|-------------------|-----------------------------------------------|
| `DATABASE_PATH`   | `back-end/data/app.db`                        |
| `ALLOWED_ORIGINS` | `http://localhost:5173,http://localhost:3000` |

## Endpoints

| Method | Path                                   | Purpose                                     |
|--------|----------------------------------------|---------------------------------------------|
| POST   | `/api/documents/upload`                | Upload a file (form field `file`, max 10 MB) |
| GET    | `/api/documents`                       | Uploaded documents, newest first (History)  |
| GET    | `/api/documents/{id}`                  | Document text plus all of its summaries     |
| DELETE | `/api/documents/{id}`                  | Delete a document, its summaries and feedback |
| POST   | `/api/summaries/generate`              | Generate a summary                          |
| GET    | `/api/summaries/{id}`                  | Get one summary                             |
| POST   | `/api/feedback`                        | Save a rating or a comparison               |
| GET    | `/api/feedback`                        | Recent feedback with document names         |
| GET    | `/api/feedback/document/{id}`          | All feedback for a document                 |
| GET    | `/api/feedback/stats`                  | Average rating and win/loss counts per model |
| GET    | `/api/models`                          | Available models and whether each is loaded |
| GET    | `/api/health`                          | Health check                                |

### Examples

```json
POST /api/summaries/generate
{ "document_id": "…", "length": "short | medium | detailed", "model": "distilbart | flan-t5" }

POST /api/feedback   (rating)
{ "summary_id": "…", "rating": 4, "aspects": ["accuracy", "clarity", "coverage", "conciseness"], "comment": "optional" }

POST /api/feedback   (comparison)
{ "summary_a_id": "…", "summary_b_id": "…", "preferred": "a" }
```
