
import os
import tempfile
from pathlib import Path

# Before any app import: a throwaway database, and a fake key so the Gemini
# code paths run (every Gemini call is mocked in the tests).
_tmp = tempfile.mkdtemp()
os.environ["DATABASE_PATH"] = str(Path(_tmp) / "test.db")
os.environ["GEMINI_API_KEY"] = "test-key"
os.environ["CHAT_ENGINE"] = "gemini"
os.environ["RLHF_CANDIDATES"] = "2"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402


DOCUMENT = """Solar power is growing fast worldwide. Panels convert sunlight into electricity using photovoltaic cells. Costs have dropped by about 90% over the last decade, making solar the cheapest source of new power in many countries.

However, solar output depends on weather and time of day. Batteries and grid upgrades are needed to store energy for the night. Governments offer subsidies to speed adoption, and China leads global manufacturing of panels.

Experts expect solar to supply a third of global electricity by 2050 if investment continues at the current pace. The report recommends doubling grid storage capacity before 2035."""


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def document(client):
    response = client.post(
        "/api/documents/upload",
        files={"file": ("solar.txt", DOCUMENT.encode())},
    )
    assert response.status_code == 201
    return response.json()
