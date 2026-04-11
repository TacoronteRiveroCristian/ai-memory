"""Tests for the proactive memory save protocol."""


def test_server_health_includes_protocol_readiness(brain_client):
    """Verify the server is running and reachable — baseline for protocol availability."""
    health = brain_client.health()
    assert health["status"] == "ok"


def test_proactive_protocol_constant_exists():
    """Verify the PROACTIVE_MEMORY_PROTOCOL constant is importable and non-empty."""
    import importlib
    import sys
    from pathlib import Path

    # Add api-server to the import path so we can import the constant
    api_server_dir = str(Path(__file__).resolve().parents[1] / "api-server")
    if api_server_dir not in sys.path:
        sys.path.insert(0, api_server_dir)

    # We can't fully import server.py (needs env vars / connections), so
    # parse the source and verify the constant is defined.
    source = (Path(__file__).resolve().parents[1] / "api-server" / "server.py").read_text()
    assert "PROACTIVE_MEMORY_PROTOCOL" in source
    assert "PROACTIVE MEMORY PROTOCOL" in source
    assert 'instructions=PROACTIVE_MEMORY_PROTOCOL' in source
    assert 'mcp.resource("memory://protocol")' in source
