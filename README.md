# DocSummarizer

**DocSummarizer** is an AI-powered web application that summarizes PDF, DOCX, and TXT documents and allows users to ask questions about their content. It uses Google Gemini for cloud-based summarization and chat, with optional local Hugging Face models as a fallback.

The application also includes source-grounding checks, document history, user feedback, and a lightweight reward model that learns from summary ratings and preferences.

## Features

- **Document Upload:** Upload PDF, DOCX, or TXT files up to 10 MB.
- **AI Summarization:** Generate short, medium, or detailed summaries.
- **Source Grounding:** Verify summary claims against the original document using extracted quotes and numerical checks.
- **Document Chat:** Ask questions and receive answers supported by relevant document passages.
- **Feedback and Reward Model:** Rate summaries and compare alternatives to improve candidate selection.
- **Summary Export:** Copy or download summaries as TXT files.
- **Document History:** View, reopen, and delete previously uploaded documents.
- **Feedback Dashboard:** View ratings, feedback statistics, and reward-model information.
- **Model Fallback:** Use local Hugging Face models when Gemini is unavailable or not configured.
- **REST API:** Access backend functionality through FastAPI.
- **Testing and CI/CD:** Automated backend tests, frontend linting, Docker builds, and deployment workflows.

## Architecture

```text
User Browser
     |
     v
Next.js Frontend (Port 3000)
     |
     v
Next.js API Proxy (/api/*)
     |
     v
FastAPI Backend (Port 8000)
     |
     +---- Document Extraction and Cleaning
     |
     +---- Gemini API / Local Models
     |
     +---- Grounding and Reward Model
     |
     +---- TF-IDF Retrieval for Document Chat
     |
     v
SQLite Database
(Documents, Summaries, Feedback, Chat)
```

The browser communicates with the Next.js application, which proxies API requests to FastAPI. This avoids requiring direct browser-to-backend CORS access during normal development.

## Technology Stack

| Component | Technologies |
|---|---|
| Frontend | Next.js 16, React 19 |
| Styling | Tailwind CSS 4 |
| Backend | Python 3.11+, FastAPI, Uvicorn, Pydantic |
| Cloud AI | Google Gemini API |
| Local AI | Hugging Face Transformers, PyTorch |
| Retrieval | scikit-learn, TF-IDF |
| Document Processing | PyMuPDF, python-docx |
| Reward Model | NumPy, linear scoring, Bradley–Terry preference learning |
| Database | SQLite |
| Testing | pytest, HTTPX, ESLint |
| Containerization | Docker, Docker Compose |
| CI/CD | GitHub Actions, GitHub Container Registry, Vercel |

## Project Structure

```text
document_summarization/
├── .github/
│   └── workflows/
│       ├── backend.yml
│       └── frontend.yml
│
├── back-end/
│   ├── app/
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── db.py
│   │   ├── api/
│   │   │   ├── documents.py
│   │   │   ├── summaries.py
│   │   │   ├── feedback.py
│   │   │   └── chat.py
│   │   ├── models/
│   │   │   └── schemas.py
│   │   └── services/
│   │       ├── document_parser.py
│   │       ├── preprocessing.py
│   │       ├── document_summariser.py
│   │       ├── gemini.py
│   │       ├── prompt.py
│   │       ├── reward_model.py
│   │       ├── chat.py
│   │       ├── documents.py
│   │       └── feedback.py
│   ├── tests/
│   ├── Dockerfile
│   ├── docker-compose.yml
│   ├── requirements.txt
│   ├── requirements-server.txt
│   └── .env.example
│
└── front-end/
    ├── app/
    │   ├── page.js
    │   ├── summary/
    │   ├── history/
    │   ├── feedback/
    │   └── api/
    │       └── [...path]/
    │           └── route.js
    ├── components/
    ├── lib/
    ├── package.json
    └── .env.example
```

## Requirements

- Python 3.11 or later
- Node.js 20.9 or later
- npm
- A Google Gemini API key (recommended)
- Docker (optional)

Get a Gemini API key from [Google AI Studio](https://aistudio.google.com/apikey).

## Installation and Setup

### 1. Configure the backend

Open a terminal in the project root:

```powershell
cd back-end
copy .env.example .env
```

Add your Gemini API key to `back-end/.env`:

```env
GEMINI_API_KEY=your_gemini_api_key
```

### 2. Install and run the backend

```powershell
cd back-end
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-server.txt
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

The server-only requirements install the Gemini backend without the larger local-model dependencies. To enable local Hugging Face models, install the full requirements instead:

```powershell
pip install -r requirements.txt
```

Backend API documentation: [http://localhost:8000/docs](http://localhost:8000/docs)

### 3. Configure and run the frontend

Open a second terminal:

```powershell
cd front-end
npm install
npm run dev
```

Open the application at [http://localhost:3000](http://localhost:3000).

If needed, configure `front-end/.env.local`:

```env
BACKEND_URL=http://127.0.0.1:8000
```

## Environment Variables

| Variable | Purpose |
|---|---|
| `GEMINI_API_KEY` | Enables Gemini API access |
| `GEMINI_MODEL` | Primary Gemini model |
| `GEMINI_FALLBACK_MODELS` | Alternative models for rate limits |
| `GEMINI_THINKING_LEVEL` | Gemini thinking level |
| `CHAT_ENGINE` | Selects `auto`, `gemini`, or `local` chat |
| `RLHF_CANDIDATES` | Number of summary candidates to compare |
| `DATABASE_PATH` | SQLite database location |
| `ALLOWED_ORIGINS` | Permitted direct API origins |
| `BACKEND_URL` | Backend address used by the Next.js proxy |
| `NEXT_PUBLIC_API_URL` | Optional direct backend URL for frontend requests |

See `back-end/.env.example` and `front-end/.env.example` for the supported configuration values and defaults.

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/documents/upload` | Upload and process a document |
| GET | `/api/documents` | List documents |
| GET | `/api/documents/{id}` | Retrieve a document and its summaries |
| DELETE | `/api/documents/{id}` | Delete a document and associated data |
| POST | `/api/summaries/generate` | Generate a summary |
| GET | `/api/summaries/{id}` | Retrieve a summary |
| POST | `/api/feedback` | Submit ratings or summary preferences |
| GET | `/api/feedback` | Retrieve recent feedback |
| GET | `/api/feedback/stats` | Retrieve feedback statistics |
| GET | `/api/feedback/reward-model` | Inspect reward-model status and weights |
| GET / POST / DELETE | `/api/chat/{document_id}` | Read, send, or clear document chat |
| PUT | `/api/chat/messages/{id}/rating` | Rate a chat response |
| GET | `/api/models` | List available models |
| GET | `/api/health` | Check backend health |

For complete request and response schemas, open [FastAPI Swagger UI](http://localhost:8000/docs).

## Summarization and Feedback Pipeline

1. **Extraction:** Extract text from PDF, DOCX, or TXT files.
2. **Preprocessing:** Normalize and clean the extracted text.
3. **Summarization:** Generate summaries using Gemini or local Hugging Face models.
4. **Grounding:** Check supported claims, quotes, and numbers against the original text.
5. **Candidate Selection:** Score multiple candidate summaries and select the highest-ranked result.
6. **Feedback Learning:** Use ratings and pairwise preferences to update the reward model.
7. **Document Chat:** Retrieve relevant passages using TF-IDF and generate document-based answers.

**Important:** Grounding checks reduce unsupported claims but do not guarantee that every summary or answer is completely free of hallucinations. Likewise, the reward model learns from feedback; it does not automatically fine-tune the underlying Gemini or Hugging Face language model.

## Running Tests

Backend tests:

```powershell
cd back-end
python -m pytest tests
```

Frontend linting:

```powershell
cd front-end
npm run lint
```

## Docker

To run the backend in Docker:

```powershell
cd back-end
docker compose up -d --build
docker compose logs -f api
```

Stop the container:

```powershell
docker compose down
```

The backend uses a persistent Docker volume for stored data. The default Docker image installs Gemini-related dependencies; local models require the corresponding configuration and additional dependencies.

## Deployment

- **Frontend:** Deploy to Vercel.
- **Backend:** Deploy with Docker or another Python-compatible hosting service.
- **Database:** SQLite is suitable for local development and small deployments. Consider PostgreSQL for larger or concurrent production workloads.
- **CI/CD:** Configure the GitHub Actions secrets required by the frontend deployment workflow and backend image publishing workflow.

## Limitations

- Maximum upload size: 10 MB.
- Scanned PDFs are not supported because OCR is not implemented.
- Local models may be slower, especially on CPU-only systems.
- Gemini usage depends on API availability, quotas, and model access.
- Grounding and reward-model scoring improve quality but do not guarantee factual correctness.

