# DocSummarizer

Upload a document (PDF, DOCX or TXT), get an AI-generated summary at the length
you choose, and rate how helpful it was.

| Part | Stack | Folder | Runs on |
|------|-------|--------|---------|
| Front-end | Next.js 16, React 19, Tailwind CSS 4 | [`front-end/`](front-end/) | http://localhost:3000 |
| Back-end | Python, FastAPI, Hugging Face Transformers, SQLite | [`back-end/`](back-end/) | http://localhost:8000 |

## How it works

```
Browser (Next.js)                        FastAPI back-end
─────────────────                        ────────────────
1. Upload screen ── POST /api/documents/upload ──▶ extract text (PDF/DOCX/TXT)
                                                   clean text → save to SQLite
2. Processing     ── POST /api/summaries/generate ─▶ split into chunks → summarize
   screen                                          each → combine → save
3. Result screen  ── GET  /api/documents/{id} ───▶ document + its summaries
   + feedback     ── POST /api/feedback ─────────▶ save rating + liked aspects
```

1. **Upload**: drag and drop or browse for a file (max 10 MB) and pick a length.
   The length scales with the document: Short is about 10% of the text, Medium
   about 20%, Detailed about 30%. A 1,000-word article gives a ~200-word Medium
   summary, and a 5,000-word paper gives about 1,000 words.
2. **Processing**: shows progress through extracting text, generating the
   summary and finalizing.
3. **Result**: shows the summary organized as **Key points**, one numbered part per
   section of the document with its sentences as bullets, or as **Paragraphs**.
   It also shows word counts, the percentage of the original and reading time,
   plus Download (.txt) and Copy in the same layout, buttons to try another
   length, and a feedback form (1–5 stars and what you liked: accuracy, clarity,
   coverage, conciseness). Ratings train a reward model (RLHF) that picks the
   best candidate for future summaries.
4. **Chat**: below the summary, ask questions about the document. Answers come
   from the document, with the verified passages they're based on, and can be
   rated 👍/👎.

With a `GEMINI_API_KEY` in `back-end/.env`, Gemini reads the whole document at
once and every summary and answer is checked against it for hallucinations
(see [`back-end/readme.md`](back-end/readme.md)). Without a key, local models
are used.
5. **History**: every uploaded document; open one again or delete it.
6. **Feedback**: total feedback, average rating, most-liked aspects, the reward model's learned weights, and recent
   ratings.

## Running it

You need **Python 3.11+** and **Node.js 20+**. Use two terminals.

**Terminal 1: back-end**

```powershell
cd back-end
python -m venv .venv               # first time only
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt    # first time only (installs torch, ~1 GB)
uvicorn app.main:app --reload --host 0.0.0.0
```

The API docs are at http://localhost:8000/docs.

**Terminal 2: front-end**

```powershell
cd front-end
npm install                        # first time only
npm run dev
```

Open http://localhost:3000.

> The first summary downloads the model (~1 GB) from Hugging Face and is
> slow. After that, generation time grows with the summary's length: a short
> article takes seconds, and a Detailed summary of a long paper can take several
> minutes on a CPU.

## Project structure

```
back-end/
  app/
    main.py                  FastAPI app, CORS, routers
    db.py                    SQLite schema + migrations (data/app.db)
    api/                     HTTP endpoints
      documents.py           upload, list, get, delete
      summaries.py           generate, get
      feedback.py            submit, list, stats
    models/schemas.py        request/response models (Pydantic)
    services/
      document_parser.py     text extraction: PDF (PyMuPDF), DOCX, TXT
      preprocessing.py       text cleaning: Unicode, hyphenation, page numbers
      document_summariser.py summarization: distilbart / flan-t5, chunking
      documents.py           storing documents and summaries
      feedback.py            storing feedback, statistics

front-end/
  app/                       routes: / (upload), /summary, /history, /feedback
  components/
    UploadFlow.js            upload + processing screens
    SummaryView.js           result screen
    FeedbackForm.js          star rating + aspects
    HistoryList.js           History page
    FeedbackOverview.js      Feedback page
    Sidebar.js, ui.js, icons.js
  lib/
    api.js                   all calls to the back-end
    format.js                file checks, sizes, dates, lengths
```

## Configuration

| Setting | Where | Default |
|---------|-------|---------|
| `NEXT_PUBLIC_API_URL` | `front-end/.env.local` | port 8000 on the same host the page was opened from |
| `DATABASE_PATH` | back-end environment | `back-end/data/app.db` |
| `ALLOWED_ORIGINS` | back-end environment | `http://localhost:5173,http://localhost:3000` (plus any localhost / LAN origin) |

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| Red "Can't reach the backend" banner | Start the back-end, with `--host 0.0.0.0` if you open the site by IP address |
| Page loads but buttons do nothing | You opened it from an address not listed in `allowedDevOrigins` in `front-end/next.config.mjs`. Add it and restart `npm run dev` |
| "No readable text found. The PDF may be scanned." | The PDF contains only images; OCR is not supported |
| `{"detail": "Not Found"}` | Wrong URL. API routes start with `/api/`; `/` redirects to `/docs` |
