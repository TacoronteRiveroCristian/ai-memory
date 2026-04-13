"""Add api-server/ to sys.path so tests can import ingest_* modules directly.

The api-server directory contains a hyphen and is not a valid Python package,
so tests load its modules as top-level imports after adjusting sys.path here.
This mirrors how server.py itself imports sibling modules (sensory_cortex,
myelination, etc.).
"""
import sys
from pathlib import Path

_API_SERVER = Path(__file__).resolve().parents[2] / "api-server"
if str(_API_SERVER) not in sys.path:
    sys.path.insert(0, str(_API_SERVER))
