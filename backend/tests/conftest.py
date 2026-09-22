"""
backend/tests/conftest.py
=========================
pytest fixtures shared across all backend tests.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# Ensure project root and backend/ are on sys.path so imports resolve.
# ---------------------------------------------------------------------------
_TESTS_DIR = Path(__file__).resolve().parent          # backend/tests/
_BACKEND_DIR = _TESTS_DIR.parent                      # backend/
_PROJECT_ROOT = _BACKEND_DIR.parent                   # LANDSYNC/

for _p in (_PROJECT_ROOT, _BACKEND_DIR):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

# Import after path setup
from main import app  # noqa: E402


@pytest.fixture(scope="session")
def client() -> TestClient:
    """FastAPI test client — shared across the entire test session.

    The lifespan startup event (which pre-loads sample data) fires when
    the TestClient context is entered for the first time.
    """
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="session")
def sample_data_dir() -> Path:
    """Return the path to data/sample/ so tests can reference GeoJSON files."""
    return _PROJECT_ROOT / "data" / "sample"
