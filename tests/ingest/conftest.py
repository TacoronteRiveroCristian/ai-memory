"""Add api-server/ to sys.path so tests can import ingest_* modules directly.

The api-server directory contains a hyphen and is not a valid Python package,
so tests load its modules as top-level imports after adjusting sys.path here.
This mirrors how server.py itself imports sibling modules (sensory_cortex,
myelination, etc.).
"""
import sys
from pathlib import Path

import pytest

_API_SERVER = Path(__file__).resolve().parents[2] / "api-server"
if str(_API_SERVER) not in sys.path:
    sys.path.insert(0, str(_API_SERVER))


# Override the autouse fixture from the root conftest so that pure unit tests
# in this directory do not require a running API server or MEMORY_API_KEY.
@pytest.fixture(autouse=True)
def require_test_mode():  # type: ignore[override]
    """No-op override: ingest unit tests are fully offline."""
    yield
