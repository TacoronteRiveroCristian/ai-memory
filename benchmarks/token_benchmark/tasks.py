"""Benchmark tasks for measuring Claude Code token savings with AI Memory MCP."""

from __future__ import annotations

from typing import Any


TASK_CATEGORIES = {
    "onboarding": "New to a project, need context",
    "cross_project": "Search across multiple projects",
    "debugging": "Debug with historical context",
    "decisions": "Understand past decisions and patterns",
    "consolidation": "Summarize and analyze portfolio state",
    "working_memory": "Task tracking and session continuity",
}

BENCHMARK_TASKS: list[dict[str, Any]] = [
    # ── Onboarding (3) ──────────────────────────────────────────────
    {
        "id": "T01",
        "category": "onboarding",
        "title": "Project overview",
        "prompt": (
            "I'm new to the bench-ems-fotovoltaica project. Give me a summary of "
            "its architecture, key decisions, and any known issues I should be aware of."
        ),
        "project": "bench-ems-fotovoltaica",
        "expected_mcp_tools": ["get_project_context", "search_memory"],
        "difficulty": "simple",
    },
    {
        "id": "T02",
        "category": "onboarding",
        "title": "Resume interrupted work",
        "prompt": (
            "I was working on the bench-react-dashboard project yesterday. What was "
            "I doing, what decisions were made, and what follow-ups are pending?"
        ),
        "project": "bench-react-dashboard",
        "expected_mcp_tools": ["get_project_context", "list_active_tasks"],
        "difficulty": "medium",
    },
    {
        "id": "T03",
        "category": "onboarding",
        "title": "Understand domain",
        "prompt": (
            "I need to understand how the bench-data-pipeline-etl project handles "
            "data quality. What are the QA/QC patterns used, what errors have been "
            "encountered, and what's the current approach?"
        ),
        "project": "bench-data-pipeline-etl",
        "expected_mcp_tools": ["search_memory", "get_project_context"],
        "difficulty": "medium",
    },
    # ── Cross-Project Search (3) ────────────────────────────────────
    {
        "id": "T04",
        "category": "cross_project",
        "title": "Shared patterns",
        "prompt": (
            "Which projects use condition monitoring and anomaly detection? I want "
            "to understand the shared methodology across the energy portfolio."
        ),
        "project": None,
        "expected_mcp_tools": ["search_memory"],
        "difficulty": "complex",
    },
    {
        "id": "T05",
        "category": "cross_project",
        "title": "Bridge discovery",
        "prompt": (
            "I'm working on bench-scada-hibrido-solar-bess. What other projects are "
            "related to it and why? Are there shared patterns or decisions I should "
            "know about?"
        ),
        "project": "bench-scada-hibrido-solar-bess",
        "expected_mcp_tools": ["get_project_context", "search_memory"],
        "difficulty": "medium",
    },
    {
        "id": "T06",
        "category": "cross_project",
        "title": "Technology reuse",
        "prompt": (
            "I need to implement rate limiting in the bench-mobile-app-flutter "
            "project. Have we solved this in other projects? Show me relevant "
            "patterns and decisions."
        ),
        "project": "bench-mobile-app-flutter",
        "expected_mcp_tools": ["search_memory"],
        "difficulty": "complex",
    },
    # ── Debugging with Context (3) ──────────────────────────────────
    {
        "id": "T07",
        "category": "debugging",
        "title": "Known error lookup",
        "prompt": (
            "I'm seeing inverted reactive power signs between the EMS and PPC. Has "
            "this happened before? What was the solution?"
        ),
        "project": "bench-ems-fotovoltaica",
        "expected_mcp_tools": ["search_memory"],
        "difficulty": "simple",
    },
    {
        "id": "T08",
        "category": "debugging",
        "title": "Cross-project error pattern",
        "prompt": (
            "We're getting timestamp misalignment issues in the "
            "bench-parque-eolico-scada project. Have similar timing problems been "
            "solved in other projects?"
        ),
        "project": "bench-parque-eolico-scada",
        "expected_mcp_tools": ["search_memory"],
        "difficulty": "complex",
    },
    {
        "id": "T09",
        "category": "debugging",
        "title": "Debug with architecture context",
        "prompt": (
            "The bench-api-gateway-auth is returning 429 errors under normal load. "
            "What do we know about the rate limiting architecture and any past "
            "issues with it?"
        ),
        "project": "bench-api-gateway-auth",
        "expected_mcp_tools": ["get_project_context", "search_memory"],
        "difficulty": "medium",
    },
    # ── Decisions and Patterns (2) ──────────────────────────────────
    {
        "id": "T10",
        "category": "decisions",
        "title": "Decision archaeology",
        "prompt": (
            "Why did we choose 1-minute sampling for the EMS telemetry pipeline? "
            "What alternatives were considered?"
        ),
        "project": "bench-ems-fotovoltaica",
        "expected_mcp_tools": ["search_memory", "get_project_context"],
        "difficulty": "simple",
    },
    {
        "id": "T11",
        "category": "decisions",
        "title": "Pattern consistency",
        "prompt": (
            "I want to add a new data validation step to bench-ml-model-serving. "
            "What validation patterns do we use across the software projects? Are "
            "there conventions I should follow?"
        ),
        "project": "bench-ml-model-serving",
        "expected_mcp_tools": ["search_memory"],
        "difficulty": "complex",
    },
    # ── Consolidation (2) ───────────────────────────────────────────
    {
        "id": "T12",
        "category": "consolidation",
        "title": "Portfolio status",
        "prompt": (
            "Give me a status summary of all energy projects: what's the current "
            "state of each, what are the pending follow-ups, and what cross-project "
            "dependencies exist?"
        ),
        "project": None,
        "expected_mcp_tools": ["get_project_context", "list_active_tasks"],
        "difficulty": "complex",
    },
    {
        "id": "T13",
        "category": "consolidation",
        "title": "Knowledge gap analysis",
        "prompt": (
            "Looking at the bench-gestion-curtailment project, what knowledge might "
            "be missing? What do related projects know that this project should also "
            "capture?"
        ),
        "project": "bench-gestion-curtailment",
        "expected_mcp_tools": ["get_project_context", "search_memory"],
        "difficulty": "complex",
    },
    # ── Working Memory / Tasks (2) ──────────────────────────────────
    {
        "id": "T14",
        "category": "working_memory",
        "title": "Task prioritization",
        "prompt": (
            "What are all the pending tasks across the bench-infra-terraform-k8s "
            "and bench-event-driven-microservices projects? Which ones are blocked "
            "or have dependencies?"
        ),
        "project": None,
        "expected_mcp_tools": ["list_active_tasks"],
        "difficulty": "medium",
    },
    {
        "id": "T15",
        "category": "working_memory",
        "title": "Session continuity",
        "prompt": (
            "I'm starting a new session on bench-parque-eolico-scada. Load my "
            "context: what happened in the last session, what's pending, and what "
            "should I focus on?"
        ),
        "project": "bench-parque-eolico-scada",
        "expected_mcp_tools": ["get_project_context"],
        "difficulty": "medium",
    },
]


def get_tasks_by_category(category: str) -> list[dict[str, Any]]:
    return [t for t in BENCHMARK_TASKS if t["category"] == category]


def get_task_by_id(task_id: str) -> dict[str, Any] | None:
    return next((t for t in BENCHMARK_TASKS if t["id"] == task_id), None)
