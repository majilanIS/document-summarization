# Document Summarization — Back-end

FastAPI service that extracts text from documents, cleans it, summarizes it with
Hugging Face models, and collects user feedback on the summaries.

## Pipeline

1. **Extraction** (`app/services/document_parser.py`): reads text from PDF (PyMuPDF), DOCX (including tables) and TXT files.
2. **Preprocessing** (`app/services/preprocessing.py`): normalizes Unicode, rejoins words hyphenated across lines, drops page-number lines, and merges layout line breaks into paragraphs.
3. **Summarization** (`app/services/document_summariser.py`): the summary length is a share of the document: `short` ≈ 10%, `medium` ≈ 20%, `detailed` ≈ 30%.
   - `gemini` (default when `GEMINI_API_KEY` is set): the **whole document** goes to Google Gemini in one request, so the summary follows its overall argument and how the parts connect. Takes seconds.
   - `distilbart` (`sshleifer/distilbart-cnn-12-6`) and `flan-t5` (`google/flan-t5-base`): local models that only see ~900 tokens at a time. The text is split into chunks and each chunk summarized separately, so they miss the bigger picture and are slow on a CPU. They're used when there's no key, when Gemini fails, or for documents too long for Gemini.
4. **Grounding / hallucination control** (`app/services/prompt.py`), Gemini only:
   - *Analyse first*: the response schema makes Gemini fill in an analysis (document type, purpose, audience, main point, sections, key facts) before it writes any paragraph.
   - *Grounding rules* in every prompt: only the document, no outside knowledge, numbers exactly as written, keep the document's certainty, attribute claims correctly, and say when something isn't covered.
   - *Evidence*: every paragraph comes with verbatim quotes from the document.
   - *Verification in code*: quotes must occur in the document (ignoring case and punctuation), and every number in the summary must occur in it too. The share of checks passed is stored as `grounding`.
   - *Repair*: a summary that fails is sent back once with the problems listed, to be corrected against the document.
5. **RLHF** (`app/services/reward_model.py`): a reward model learned from feedback. Each summary is described by features (coverage of the main terms, support in the source, repetition, figures found in the source, ...). A linear model is fit to the star ratings (pointwise) and to preferences (Bradley–Terry pairwise loss, from comparisons and from differently-rated summaries of the same document), pulled toward sensible defaults until there are at least 3 feedback items. It retrains after every feedback and at startup. Generation is best-of-N: several candidates are generated, the best-grounded ones are kept, and the reward model picks among them. Locally the candidates are the beams of one beam search. Gemini returns several in one request where the model allows it; the current Flash models on a free key return one.
6. **Chat** (`app/services/chat.py`): questions about a document after its summary. Passages are ranked with TF-IDF over words and word pairs (scikit-learn). Gemini gets the whole document plus the conversation (so follow-ups like "why?" work) and answers in a schema: supporting quotes, whether the document covers the question, the answer. Only quotes found in the document are shown as sources, and an answer with figures that can't be verified gets a warning. Without Gemini, local `flan-t5` answers from the best passages. Answers can be rated 👍/👎.
7. **Feedback** (`app/services/feedback.py`): saves a 1–5 rating for one summary, or a preference (`a`, `b` or `tie`) between two summaries of the same document.

### Gemini quotas

Every Gemini call is retried briefly when Google reports overload (503), via `tenacity`. When the model is rate limited (429), the request moves straight to the next model in `GEMINI_FALLBACK_MODELS`, since quotas are per model. A free-tier key allows only a few requests per minute and per day for each model. When every model is out, summaries fall back to the local model.

Data is stored in SQLite at `data/app.db`.

## Performance

Summarizing runs the model locally, so speed depends on the machine.

- **Batching**: up to `BATCH_SIZE` (4) chunks go through the model in one call. On a 4-thread CPU this cut a Medium summary of a 3,300-word PDF from 276 s to 132 s, with identical output.
- **GPU**: used automatically when PyTorch detects an NVIDIA GPU (`torch.cuda.is_available()`). This is usually 10× faster or more; install the CUDA build of torch from pytorch.org.
- **Tried and rejected**: greedy decoding (`num_beams=1`) was slower here and gave worse summaries, and int8 dynamic quantization produced garbage text.
- One summary runs at a time per model. Requests that arrive together wait their turn.

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

They can also go in `back-end/.env`. Gemini and RLHF settings are typed and validated in `app/config.py` (pydantic-settings).

| Variable                 | Default                                       |
|--------------------------|-----------------------------------------------|
| `GEMINI_API_KEY`         | none (local models only)                      |
| `GEMINI_MODEL`           | `gemini-flash-latest`                         |
| `GEMINI_FALLBACK_MODELS` | `gemini-flash-lite-latest,gemini-3.5-flash`   |
| `GEMINI_THINKING_LEVEL`  | `low` (`minimal`, `low`, `medium`, `high`)    |
| `CHAT_ENGINE`            | `auto` (Gemini if a key is set), `gemini`, `local` |
| `RLHF_CANDIDATES`        | `3` candidates for best-of-N (1 turns it off) |
| `DATABASE_PATH`          | `back-end/data/app.db`                        |
| `ALLOWED_ORIGINS`        | `http://localhost:5173,http://localhost:3000` |

## Tests

```bash
python -m pytest tests
```

Gemini is mocked, so the tests need no key and use no quota.

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
| GET    | `/api/feedback/stats`                  | Average rating and win/loss counts per model, chat 👍/👎 |
| GET    | `/api/feedback/reward-model`           | Reward model status and learned weights (RLHF) |
| GET    | `/api/chat/{document_id}`              | Chat history for a document                 |
| POST   | `/api/chat/{document_id}`              | Ask a question `{ "message": "…" }`         |
| DELETE | `/api/chat/{document_id}`              | Clear the chat                              |
| PUT    | `/api/chat/messages/{id}/rating`       | Rate an answer `{ "rating": 1 \| -1 \| null }` |
| GET    | `/api/models`                          | Available models and whether each is loaded |
| GET    | `/api/health`                          | Health check                                |

### Examples

```json
POST /api/summaries/generate
{ "document_id": "…", "length": "short | medium | detailed", "model": "gemini | distilbart | flan-t5 (optional)" }

POST /api/feedback   (rating)
{ "summary_id": "…", "rating": 4, "aspects": ["accuracy", "clarity", "coverage", "conciseness"], "comment": "optional" }

POST /api/feedback   (comparison)
{ "summary_a_id": "…", "summary_b_id": "…", "preferred": "a" }
```
