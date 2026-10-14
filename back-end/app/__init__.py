
from pathlib import Path

from dotenv import load_dotenv


# Settings such as GEMINI_API_KEY can live in back-end/.env. Loaded here so
# they are in place before any module reads them.
load_dotenv(Path(__file__).resolve().parent.parent / ".env")
