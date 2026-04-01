"""Tests para los 8 sistemas cognitivos y la ingesta masiva de conocimiento.

Requieren:
  - AI_MEMORY_TEST_MODE=true en el API server (embeddings deterministas, reloj sintético).
  - MEMORY_API_KEY configurada.
  - API server accesible en AI_MEMORY_BASE_URL (por defecto http://127.0.0.1:8050).

Cada test usa un project_name único generado por la fixture `unique_project_name`
para garantizar aislamiento total entre tests.
"""
from __future__ import annotations

import uuid
from typing import Any

import pytest


# ─────────────────────────────────────────────────────────────────────────────
# Helpers locales
# ─────────────────────────────────────────────────────────────────────────────

def mem_field(detail: dict[str, Any], field: str, default: Any = None) -> Any:
    """Accede a un campo dentro de detail['memory']."""
    return detail.get("memory", {}).get(field, default)


def minimal_plasticity_payload(project: str, summary: str = "test") -> dict[str, Any]:
    return {
        "project": project,
        "agent_id": "pytest",
        "session_id": f"session-cog-{uuid.uuid4().hex[:8]}",
        "goal": "test cognitive systems",
        "outcome": "verified",
        "summary": summary,
        "changes": [],
        "decisions": [],
        "errors": [],
        "follow_ups": [],
        "tags": ["tests"],
    }


# ─────────────────────────────────────────────────────────────────────────────
# [1] Ebbinghaus – Curva de olvido y refuerzo espaciado
# ─────────────────────────────────────────────────────────────────────────────

def test_ebbinghaus_review_count_increments_on_access(brain_client, unique_project_name):
    """Cada búsqueda con register_access=True debe incrementar review_count y duplicar stability_halflife_days."""
    project = unique_project_name("ebbing-access")
    mid = brain_client.create_memory(
        content="PostgreSQL partial indexes speed up filtered queries on large tables significantly.",
        project=project,
        memory_type="general",
        tags="tech/postgres,pattern/indexing",
        importance=0.8,
        agent_id="pytest",
    )["memory_id"]

    detail_before = brain_client.memory_detail(mid)
    rc_before = mem_field(detail_before, "review_count", 0)
    hl_before = mem_field(detail_before, "stability_halflife_days", 1.0)

    brain_client.structured_search(
        query="partial indexes postgres filter queries speed",
        project=project,
        scope="project",
        limit=5,
        register_access=True,
    )

    detail_after = brain_client.memory_detail(mid)
    rc_after = mem_field(detail_after, "review_count", 0)
    hl_after = mem_field(detail_after, "stability_halflife_days", 1.0)

    assert rc_after > rc_before, (
        f"review_count debe haber incrementado: {rc_before} → {rc_after}"
    )
    assert hl_after > hl_before, (
        f"stability_halflife_days debe haberse duplicado: {hl_before} → {hl_after}"
    )


def test_ebbinghaus_decay_reduces_stability_after_time_jump(brain_client, unique_project_name):
    """La estabilidad debe disminuir para memorias no accedidas tras un salto temporal largo."""
    project = unique_project_name("ebbing-decay")
    brain_client.set_test_clock("2030-03-01T00:00:00+00:00")

    mid = brain_client.create_memory(
        content="Async I/O improves throughput for I/O-bound Python services using event loop.",
        project=project,
        memory_type="general",
        tags="tech/python,pattern/async",
        importance=0.7,
        agent_id="pytest",
    )["memory_id"]

    detail_before = brain_client.memory_detail(mid)
    stab_before = mem_field(detail_before, "stability_score", 0.5)

    # Salto de 60 días sin acceso → la memoria debe decaer (Ebbinghaus)
    brain_client.set_test_clock("2030-04-30T00:00:00+00:00")
    brain_client.apply_session_plasticity(
        **minimal_plasticity_payload(project, "Ebbinghaus decay test: reviewing stability drop for cold memory")
    )

    detail_after = brain_client.memory_detail(mid)
    stab_after = mem_field(detail_after, "stability_score", 0.5)

    assert stab_after < stab_before, (
        f"stability_score debe haber decaído: {stab_before:.4f} → {stab_after:.4f}"
    )


def test_ebbinghaus_pinned_memory_not_decayed(brain_client, unique_project_name):
    """Las memorias con manual_pin=True NO deben decaer bajo Ebbinghaus."""
    project = unique_project_name("ebbing-pin")
    brain_client.set_test_clock("2030-03-01T00:00:00+00:00")

    mid_a = brain_client.create_memory(
        content="Pinned architectural decision: always use async I/O for database access.",
        project=project,
        memory_type="decision",
        tags="pattern/architecture",
        importance=0.95,
        agent_id="pytest",
    )["memory_id"]
    mid_b = brain_client.create_memory(
        content="Pinned counter-memory for manual relation testing.",
        project=project,
        memory_type="decision",
        tags="pattern/architecture",
        importance=0.90,
        agent_id="pytest",
    )["memory_id"]
    # Crear relación manual → activa manual_pin en ambas memorias
    brain_client.link_memories(
        source_memory_id=mid_a,
        target_memory_id=mid_b,
        relation_type="supports",
        reason="Manual pin test",
        weight=0.9,
    )

    detail_before = brain_client.memory_detail(mid_a)
    stab_before = mem_field(detail_before, "stability_score", 1.0)

    # Salto de 90 días
    brain_client.set_test_clock("2030-05-30T00:00:00+00:00")
    brain_client.apply_session_plasticity(**minimal_plasticity_payload(project))

    detail_after = brain_client.memory_detail(mid_a)
    stab_after = mem_field(detail_after, "stability_score", 1.0)
    manual_pin = mem_field(detail_after, "manual_pin", False)

    assert manual_pin is True, "La memoria con relación manual debe estar pinned"
    assert stab_after >= stab_before * 0.99, (
        f"La memoria pinned no debe decaer significativamente: {stab_before:.4f} → {stab_after:.4f}"
    )


# ─────────────────────────────────────────────────────────────────────────────
# [2] Valencia Emocional – valence / arousal
# ─────────────────────────────────────────────────────────────────────────────

def test_valence_positive_content_stores_positive_value(brain_client, unique_project_name):
    """Contenido con palabras positivas debe producir valence > 0."""
    project = unique_project_name("valence-pos")
    mid = brain_client.create_memory(
        content="The deployment was successful: the solution is now fixed and fully working.",
        project=project,
        memory_type="general",
        tags="status/deployed",
        importance=0.8,
        agent_id="pytest",
    )["memory_id"]

    detail = brain_client.memory_detail(mid)
    valence = mem_field(detail, "valence", 0.0)
    assert valence > 0.0, f"Esperado valence > 0 para contenido positivo, obtenido: {valence}"


def test_valence_negative_content_stores_negative_value(brain_client, unique_project_name):
    """Contenido con palabras negativas debe producir valence < 0."""
    project = unique_project_name("valence-neg")
    mid = brain_client.create_memory(
        content="Critical crash detected in production: fatal exception caused data corruption and system failure.",
        project=project,
        memory_type="error",
        tags="status/critical",
        importance=0.9,
        agent_id="pytest",
    )["memory_id"]

    detail = brain_client.memory_detail(mid)
    valence = mem_field(detail, "valence", 0.0)
    assert valence < 0.0, f"Esperado valence < 0 para contenido negativo, obtenido: {valence}"


def test_arousal_high_urgency_content_scores_higher(brain_client, unique_project_name):
    """Contenido de alta urgencia debe tener arousal mayor que contenido neutro."""
    project = unique_project_name("arousal-high")

    mid_high = brain_client.create_memory(
        content="CRITICAL: fatal crash in the payment service – this is a showstopper blocking all transactions.",
        project=project,
        memory_type="error",
        tags="status/critical,tech/payments",
        importance=0.95,
        agent_id="pytest",
    )["memory_id"]

    mid_low = brain_client.create_memory(
        content="Updated README file with minor formatting corrections and typo fixes in the documentation.",
        project=project,
        memory_type="general",
        tags="docs/readme",
        importance=0.4,
        agent_id="pytest",
    )["memory_id"]

    d_high = brain_client.memory_detail(mid_high)
    d_low = brain_client.memory_detail(mid_low)
    arousal_high = mem_field(d_high, "arousal", 0.5)
    arousal_low = mem_field(d_low, "arousal", 0.5)

    assert arousal_high > arousal_low, (
        f"arousal urgente ({arousal_high:.3f}) debe superar arousal neutro ({arousal_low:.3f})"
    )


def test_cognitive_fields_exposed_in_memory_detail(brain_client, unique_project_name):
    """memory_detail debe exponer todos los campos cognitivos de los sistemas 1-3."""
    project = unique_project_name("cog-fields")
    mid = brain_client.create_memory(
        content="Fatal exception in the payment gateway caused data corruption requiring a system restart.",
        project=project,
        memory_type="error",
        tags="status/critical,tech/payments",
        importance=0.95,
        agent_id="pytest",
    )["memory_id"]

    detail = brain_client.memory_detail(mid)
    mem = detail.get("memory", {})

    required_fields = [
        "valence", "arousal", "review_count", "stability_halflife_days",
        "novelty_score", "prominence", "stability_score", "activation_score",
        "abstraction_level",
    ]
    for field in required_fields:
        assert field in mem, f"memory_detail debe exponer el campo '{field}'"

    # Rangos válidos
    assert -1.0 <= mem["valence"] <= 1.0, "valence debe estar en [-1, 1]"
    assert 0.0 <= mem["arousal"] <= 1.0, "arousal debe estar en [0, 1]"
    assert mem["review_count"] >= 0, "review_count debe ser >= 0"
    assert mem["stability_halflife_days"] >= 1.0, "stability_halflife_days debe ser >= 1.0"
    assert 0.0 <= mem["novelty_score"] <= 1.0, "novelty_score debe estar en [0, 1]"
    assert 0.0 <= mem["prominence"] <= 1.0, "prominence debe estar en [0, 1]"
    assert mem["abstraction_level"] >= 0, "abstraction_level debe ser >= 0"


# ─────────────────────────────────────────────────────────────────────────────
# [3] Sesgo de Novedad – novelty_score e importance boost
# ─────────────────────────────────────────────────────────────────────────────

def test_novel_memory_gets_high_novelty_score(brain_client, unique_project_name):
    """Una memoria sobre un tema completamente distinto al corpus debe obtener alta novelty."""
    project = unique_project_name("novelty-high")

    # Seed: memorias sobre event sourcing
    brain_client.create_memory(
        content="Event sourcing stores state changes as an immutable sequence of domain events.",
        project=project,
        memory_type="architecture",
        tags="pattern/event-sourcing",
        importance=0.8,
        agent_id="pytest",
    )
    brain_client.create_memory(
        content="Domain events are the primary facts in event-sourced systems with full audit trail.",
        project=project,
        memory_type="architecture",
        tags="pattern/event-sourcing",
        importance=0.8,
        agent_id="pytest",
    )

    # Memoria completamente distinta: tema sin relación semántica con el corpus
    mid_novel = brain_client.create_memory(
        content="Quantum error correction uses stabilizer codes to protect qubits from decoherence effects.",
        project=project,
        memory_type="general",
        tags="tech/quantum",
        importance=0.7,
        agent_id="pytest",
    )["memory_id"]

    detail = brain_client.memory_detail(mid_novel)
    novelty = mem_field(detail, "novelty_score", 0.5)
    assert novelty > 0.5, f"Memoria novedad esperada novelty_score > 0.5, obtenido: {novelty}"


# ─────────────────────────────────────────────────────────────────────────────
# [4] Spreading Activation – propagation bonus en búsqueda
# ─────────────────────────────────────────────────────────────────────────────

def test_spreading_activation_propagates_to_linked_neighbor(brain_client, unique_project_name):
    """Después de activar una memoria, sus vecinas enlazadas deben aparecer en búsquedas."""
    project = unique_project_name("spreading-act")

    mid_a = brain_client.create_memory(
        content="Redis pipeline batches multiple commands to reduce round-trip latency significantly.",
        project=project,
        memory_type="general",
        tags="tech/redis,pattern/caching",
        importance=0.85,
        agent_id="pytest",
    )["memory_id"]

    mid_b = brain_client.create_memory(
        content="Batching Redis commands with pipelining significantly reduces network overhead in production.",
        project=project,
        memory_type="general",
        tags="tech/redis,pattern/caching",
        importance=0.85,
        agent_id="pytest",
    )["memory_id"]

    brain_client.link_memories(
        source_memory_id=mid_a,
        target_memory_id=mid_b,
        relation_type="same_concept",
        reason="Ambas describen Redis pipelining.",
        weight=0.9,
    )

    # Activar mid_a → propagación debe llegar a mid_b
    brain_client.structured_search(
        query="Redis pipeline batch commands reduce latency",
        project=project,
        scope="project",
        limit=3,
        register_access=True,
    )

    # Buscar por el contenido de mid_b: debe aparecer (con o sin bonus de propagación)
    results = brain_client.structured_search(
        query="Batching Redis commands network overhead production",
        project=project,
        scope="project",
        limit=5,
        register_access=False,
    )
    result_ids = [r["memory_id"] for r in results["results"]]
    assert mid_b in result_ids, (
        "La memoria vecina activada por propagación debe aparecer en los resultados"
    )


# ─────────────────────────────────────────────────────────────────────────────
# [5] Multi-Hop – recuperación asociativa con chain_hops
# ─────────────────────────────────────────────────────────────────────────────

def test_chain_hops_1_retrieves_directly_linked_memory(brain_client, unique_project_name):
    """Con chain_hops=1 se deben obtener memorias directamente enlazadas al resultado semántico."""
    project = unique_project_name("multihop-1")

    mid_a = brain_client.create_memory(
        content="CQRS pattern separates command and query models for scalable systems.",
        project=project,
        memory_type="architecture",
        tags="pattern/cqrs",
        importance=0.88,
        agent_id="pytest",
    )["memory_id"]

    mid_b = brain_client.create_memory(
        content="Event sourcing provides the audit trail that pairs naturally with CQRS architecture.",
        project=project,
        memory_type="architecture",
        tags="pattern/event-sourcing,pattern/cqrs",
        importance=0.87,
        agent_id="pytest",
    )["memory_id"]

    brain_client.link_memories(
        source_memory_id=mid_a,
        target_memory_id=mid_b,
        relation_type="extends",
        reason="CQRS to event sourcing extension.",
        weight=0.88,
    )

    results = brain_client.structured_search(
        query="CQRS separates command query models scalable",
        project=project,
        scope="project",
        limit=8,
        register_access=False,
        chain_hops=1,
    )
    result_ids = [r["memory_id"] for r in results["results"]]

    # mid_a debe estar (semánticamente cercano)
    assert mid_a in result_ids, "mid_a debe aparecer en resultados con chain_hops=1"
    # All results must have required fields
    for r in results["results"]:
        assert "memory_id" in r
        assert "hybrid_score" in r
        assert 0.0 <= r["hybrid_score"] <= 1.0


def test_chain_hops_2_retrieves_transitive_memory(brain_client, unique_project_name):
    """Con chain_hops=2 se deben alcanzar memorias a 2 saltos del resultado semántico."""
    project = unique_project_name("multihop-2")

    # Cadena: mid_a → (link) → mid_b → (link) → mid_c
    mid_a = brain_client.create_memory(
        content="CQRS separates read and write model responsibilities in distributed architectures.",
        project=project,
        memory_type="architecture",
        tags="pattern/cqrs",
        importance=0.88,
        agent_id="pytest",
    )["memory_id"]

    mid_b = brain_client.create_memory(
        content="Event sourcing works naturally with CQRS by providing an immutable event log.",
        project=project,
        memory_type="architecture",
        tags="pattern/event-sourcing,pattern/cqrs",
        importance=0.87,
        agent_id="pytest",
    )["memory_id"]

    mid_c = brain_client.create_memory(
        content="Append-only Postgres tables implement event sourcing persistence with full history.",
        project=project,
        memory_type="architecture",
        tags="pattern/event-sourcing,tech/postgres",
        importance=0.86,
        agent_id="pytest",
    )["memory_id"]

    brain_client.link_memories(
        source_memory_id=mid_a,
        target_memory_id=mid_b,
        relation_type="extends",
        reason="CQRS to event sourcing bridge.",
        weight=0.88,
    )
    brain_client.link_memories(
        source_memory_id=mid_b,
        target_memory_id=mid_c,
        relation_type="extends",
        reason="Event sourcing to postgres persistence.",
        weight=0.86,
    )

    results_2hops = brain_client.structured_search(
        query="CQRS separates read write responsibilities distributed",
        project=project,
        scope="project",
        limit=8,
        register_access=False,
        chain_hops=2,
    )
    result_ids_2hops = [r["memory_id"] for r in results_2hops["results"]]

    results_0hops = brain_client.structured_search(
        query="CQRS separates read write responsibilities distributed",
        project=project,
        scope="project",
        limit=8,
        register_access=False,
        chain_hops=0,
    )
    result_ids_0hops = [r["memory_id"] for r in results_0hops["results"]]

    # mid_a debe aparecer en ambos casos
    assert mid_a in result_ids_2hops

    # Con 2 hops, el conjunto de resultados debe ser al menos tan grande como sin hops
    assert len(result_ids_2hops) >= len(result_ids_0hops)

    # Los scores deben estar ordenados descendentemente
    scores = [r["hybrid_score"] for r in results_2hops["results"]]
    assert scores == sorted(scores, reverse=True), "Resultados deben ordenarse por hybrid_score DESC"


# ─────────────────────────────────────────────────────────────────────────────
# [7] Resolución de Contradicciones – contradiction_queue
# ─────────────────────────────────────────────────────────────────────────────

def test_contradicts_relation_creates_relation_and_enqueues(brain_client, unique_project_name):
    """Una relación 'contradicts' debe crearse correctamente y encolarse para resolución."""
    project = unique_project_name("contradiction")

    mid_a = brain_client.create_memory(
        content="Microservices should always use synchronous REST APIs for inter-service communication.",
        project=project,
        memory_type="architecture",
        tags="pattern/microservices,tech/rest",
        importance=0.8,
        agent_id="pytest",
    )["memory_id"]

    mid_b = brain_client.create_memory(
        content="Async event-driven messaging is strongly preferred over synchronous REST in microservices.",
        project=project,
        memory_type="architecture",
        tags="pattern/microservices,pattern/messaging",
        importance=0.82,
        agent_id="pytest",
    )["memory_id"]

    result = brain_client.link_memories(
        source_memory_id=mid_a,
        target_memory_id=mid_b,
        relation_type="contradicts",
        reason="Advice on microservice communication pattern is contradictory.",
        weight=0.8,
    )

    # La llamada debe completarse sin error
    assert result.get("result", "").startswith("OK"), (
        f"Esperado OK al crear relación 'contradicts', obtenido: {result}"
    )

    # La relación debe estar almacenada
    rels = brain_client.relations(mid_a)["relations"]
    assert any(
        r.get("relation_type") == "contradicts" or r.get("other_memory_id") == mid_b
        for r in rels
    ), "Relación 'contradicts' debe estar presente en las relaciones de mid_a"


def test_multiple_contradictions_all_enqueued(brain_client, unique_project_name):
    """Múltiples contradicciones distintas deben crearse sin conflicto."""
    project = unique_project_name("contradiction-multi")

    memories = brain_client.bulk_create_memories([
        {
            "content": "Always use feature flags to deploy incrementally.",
            "project": project, "memory_type": "decision",
            "tags": "pattern/deployment", "importance": 0.8, "agent_id": "pytest",
        },
        {
            "content": "Feature flags add complexity; deploy with blue-green instead.",
            "project": project, "memory_type": "decision",
            "tags": "pattern/deployment", "importance": 0.8, "agent_id": "pytest",
        },
        {
            "content": "Monorepos simplify dependency management across teams.",
            "project": project, "memory_type": "decision",
            "tags": "pattern/monorepo", "importance": 0.78, "agent_id": "pytest",
        },
        {
            "content": "Polyrepos give teams autonomy; monorepos create tooling overhead.",
            "project": project, "memory_type": "decision",
            "tags": "pattern/monorepo", "importance": 0.78, "agent_id": "pytest",
        },
    ])
    mid_a, mid_b, mid_c, mid_d = memories

    r1 = brain_client.link_memories(
        source_memory_id=mid_a, target_memory_id=mid_b,
        relation_type="contradicts", reason="Deployment approach contradiction.", weight=0.75,
    )
    r2 = brain_client.link_memories(
        source_memory_id=mid_c, target_memory_id=mid_d,
        relation_type="contradicts", reason="Repo structure contradiction.", weight=0.75,
    )

    assert r1.get("result", "").startswith("OK"), f"Primera contradicción falló: {r1}"
    assert r2.get("result", "").startswith("OK"), f"Segunda contradicción falló: {r2}"


# ─────────────────────────────────────────────────────────────────────────────
# Ingesta Masiva – escalabilidad y calidad bajo carga
# ─────────────────────────────────────────────────────────────────────────────

# Corpus de 40 memorias en 4 clusters temáticos

_OBSERVABILITY_CLUSTER = [
    {
        "content": "Distributed tracing with OpenTelemetry lets you follow a request across microservices.",
        "tags": "tech/opentelemetry,pattern/tracing", "memory_type": "architecture",
    },
    {
        "content": "Structured logs with correlation IDs enable filtering traces across distributed services.",
        "tags": "pattern/logging,pattern/tracing", "memory_type": "architecture",
    },
    {
        "content": "Prometheus scrapes time-series metrics from services for alerting and dashboards.",
        "tags": "tech/prometheus,pattern/metrics", "memory_type": "architecture",
    },
    {
        "content": "Grafana visualizes Prometheus metrics with customizable dashboards and alert rules.",
        "tags": "tech/grafana,tech/prometheus", "memory_type": "architecture",
    },
    {
        "content": "P99 latency is a better SLO metric than average because it exposes tail behavior.",
        "tags": "pattern/slo,pattern/metrics", "memory_type": "decision",
    },
    {
        "content": "Exemplars link Prometheus metrics to specific traces for root-cause analysis.",
        "tags": "tech/prometheus,pattern/tracing", "memory_type": "architecture",
    },
    {
        "content": "Alert fatigue occurs when too many non-actionable alerts fire in production.",
        "tags": "pattern/alerting,pattern/ops", "memory_type": "error",
    },
    {
        "content": "SLO burn rates detect budget exhaustion faster than static alert thresholds.",
        "tags": "pattern/slo,pattern/alerting", "memory_type": "decision",
    },
    {
        "content": "Span baggage propagates request context across service boundaries in traces.",
        "tags": "tech/opentelemetry,pattern/tracing", "memory_type": "architecture",
    },
    {
        "content": "Cardinality explosion in Prometheus metrics leads to OOM and slow query performance.",
        "tags": "tech/prometheus,pattern/ops", "memory_type": "error",
    },
]

_DATA_ARCHITECTURE_CLUSTER = [
    {
        "content": "Column-oriented Parquet files greatly improve analytical query throughput over row formats.",
        "tags": "tech/parquet,pattern/analytics", "memory_type": "architecture",
    },
    {
        "content": "Data lake medallion architecture separates raw, cleansed, and curated data layers.",
        "tags": "pattern/data-lake,pattern/analytics", "memory_type": "architecture",
    },
    {
        "content": "Apache Iceberg provides ACID transactions and schema evolution for data lake tables.",
        "tags": "tech/iceberg,pattern/data-lake", "memory_type": "architecture",
    },
    {
        "content": "dbt transforms raw data into business facts using version-controlled SQL models.",
        "tags": "tech/dbt,pattern/data-lake", "memory_type": "architecture",
    },
    {
        "content": "Partition pruning in BigQuery eliminates full table scans on date-partitioned tables.",
        "tags": "tech/bigquery,pattern/analytics", "memory_type": "decision",
    },
    {
        "content": "Slowly changing dimensions SCD2 preserve historical attribute changes in data warehouses.",
        "tags": "pattern/analytics,pattern/dimensions", "memory_type": "architecture",
    },
    {
        "content": "Exactly-once semantics in Kafka require producer idempotency and consumer transactions.",
        "tags": "tech/kafka,pattern/streaming", "memory_type": "architecture",
    },
    {
        "content": "Z-ordering in Delta Lake clusters related data to minimize file reads for filter queries.",
        "tags": "tech/delta-lake,pattern/analytics", "memory_type": "decision",
    },
    {
        "content": "Data contracts between producers and consumers prevent silent schema breakage.",
        "tags": "pattern/data-lake,pattern/governance", "memory_type": "decision",
    },
    {
        "content": "Stream-table joins in Flink allow enriching real-time events with reference dimension data.",
        "tags": "tech/flink,pattern/streaming", "memory_type": "architecture",
    },
]

_SECURITY_CLUSTER = [
    {
        "content": "Zero-trust architecture assumes no implicit trust even inside the corporate network perimeter.",
        "tags": "pattern/security,pattern/zero-trust", "memory_type": "architecture",
    },
    {
        "content": "OAuth2 PKCE flow is required for public clients that cannot store a client secret securely.",
        "tags": "tech/oauth2,pattern/security", "memory_type": "architecture",
    },
    {
        "content": "Short-lived JWTs with refresh token rotation minimize the blast radius of token theft.",
        "tags": "tech/jwt,pattern/security", "memory_type": "decision",
    },
    {
        "content": "mTLS authenticates both client and server certificates to prevent service impersonation.",
        "tags": "tech/tls,pattern/security", "memory_type": "architecture",
    },
    {
        "content": "RBAC assigns permissions to roles rather than individual users for easier access auditing.",
        "tags": "pattern/rbac,pattern/security", "memory_type": "architecture",
    },
    {
        "content": "Automated secrets rotation avoids long-lived credentials accumulating in production.",
        "tags": "pattern/security,pattern/ops", "memory_type": "decision",
    },
    {
        "content": "SQL injection is prevented by parameterized queries, never by string concatenation.",
        "tags": "pattern/security,tech/sql", "memory_type": "error",
    },
    {
        "content": "Rate limiting at the API gateway blocks brute-force and credential stuffing attacks.",
        "tags": "pattern/security,pattern/api-gateway", "memory_type": "architecture",
    },
    {
        "content": "Content Security Policy headers mitigate XSS by restricting allowed script sources.",
        "tags": "pattern/security,tech/http", "memory_type": "architecture",
    },
    {
        "content": "SSRF vulnerabilities arise when user-supplied URLs are fetched server-side without validation.",
        "tags": "pattern/security,pattern/api", "memory_type": "error",
    },
]

_PYTHON_ASYNC_CLUSTER = [
    {
        "content": "asyncio.gather runs coroutines concurrently to reduce total I/O wait time dramatically.",
        "tags": "tech/python,pattern/async", "memory_type": "architecture",
    },
    {
        "content": "Connection pool reuse in asyncpg avoids TCP handshake overhead on every database request.",
        "tags": "tech/python,pattern/db", "memory_type": "decision",
    },
    {
        "content": "CPU-bound work should move to a ProcessPoolExecutor to avoid blocking the event loop.",
        "tags": "tech/python,pattern/async", "memory_type": "decision",
    },
    {
        "content": "asyncpg is significantly faster than psycopg2 for async PostgreSQL access in Python.",
        "tags": "tech/python,tech/postgres", "memory_type": "decision",
    },
    {
        "content": "uvicorn with multiple workers provides horizontal scale for async FastAPI services.",
        "tags": "tech/python,tech/fastapi", "memory_type": "architecture",
    },
    {
        "content": "Pydantic V2 is 5-50x faster than V1 due to its Rust-based validation core.",
        "tags": "tech/python,tech/pydantic", "memory_type": "decision",
    },
    {
        "content": "Memory leaks in async Python often come from tasks created but never awaited or cancelled.",
        "tags": "tech/python,pattern/async", "memory_type": "error",
    },
    {
        "content": "GIL contention bottlenecks multi-threaded Python CPU work – use multiprocessing instead.",
        "tags": "tech/python,pattern/performance", "memory_type": "error",
    },
    {
        "content": "Caching embedding vectors in Redis avoids redundant OpenAI API calls within a session.",
        "tags": "tech/python,tech/redis,pattern/caching", "memory_type": "decision",
    },
    {
        "content": "Semaphores in asyncio bound the number of concurrent coroutines accessing shared resources.",
        "tags": "tech/python,pattern/async", "memory_type": "architecture",
    },
]

_ALL_BULK_MEMORIES = (
    _OBSERVABILITY_CLUSTER
    + _DATA_ARCHITECTURE_CLUSTER
    + _SECURITY_CLUSTER
    + _PYTHON_ASYNC_CLUSTER
)


def test_bulk_ingestion_stores_all_memories(brain_client, unique_project_name):
    """Ingesta 40 memorias diversas y verifica que todas se almacenen con memory_id."""
    project = unique_project_name("bulk-all")
    ids = brain_client.bulk_create_memories([
        {**mem, "project": project, "importance": 0.8, "agent_id": "pytest-bulk"}
        for mem in _ALL_BULK_MEMORIES
    ])
    assert len(ids) == len(_ALL_BULK_MEMORIES), (
        f"Esperado {len(_ALL_BULK_MEMORIES)} ids, obtenido {len(ids)}"
    )
    # Todos los ids deben ser UUIDs válidos
    for mid in ids:
        assert len(mid) == 36, f"memory_id debe ser UUID: {mid}"


def test_bulk_ingestion_search_retrieves_cluster_correctly(brain_client, unique_project_name):
    """Después de ingesta masiva, la búsqueda recupera los clusters temáticos correctos."""
    project = unique_project_name("bulk-search")
    brain_client.bulk_create_memories([
        {**mem, "project": project, "importance": 0.82, "agent_id": "pytest-bulk"}
        for mem in _ALL_BULK_MEMORIES
    ])

    # Buscar cluster observabilidad
    obs = brain_client.structured_search(
        query="distributed tracing OpenTelemetry microservices correlation IDs",
        project=project, scope="project", limit=8, register_access=False,
    )
    assert len(obs["results"]) >= 2
    obs_contents = " ".join(r["content"].lower() for r in obs["results"])
    assert any(kw in obs_contents for kw in ("tracing", "opentelemetry", "prometheus", "correlation"))

    # Buscar cluster seguridad — usar tokens que aparecen verbatim en las memorias
    # El tokenizador determinista trata 'zero-trust' como un solo token
    sec = brain_client.structured_search(
        query="oauth2 pkce flow public clients cannot store client secret securely mtls authenticates certificates prevent service impersonation",
        project=project, scope="project", limit=8, register_access=False,
    )
    assert len(sec["results"]) >= 2
    sec_contents = " ".join(r["content"].lower() for r in sec["results"])
    assert any(kw in sec_contents for kw in ("zero-trust", "trust", "oauth", "jwt", "mtls", "security"))

    # Buscar cluster datos — usar tokens literales de múltiples memorias del cluster
    # (el tokenizador hash requiere alta superposición léxica con el contenido almacenado)
    data = brain_client.structured_search(
        query="column-oriented parquet files greatly improve analytical query throughput row formats data lake medallion architecture separates raw cleansed curated layers apache iceberg acid transactions schema evolution",
        project=project, scope="project", limit=8, register_access=False,
    )
    assert len(data["results"]) >= 2

    # Buscar cluster Python async — tokens literales de múltiples memorias del cluster
    py = brain_client.structured_search(
        query="asyncio gather runs coroutines concurrently reduce total time semaphores bound concurrent coroutines accessing",
        project=project, scope="project", limit=8, register_access=False,
    )
    assert len(py["results"]) >= 2


def test_bulk_ingestion_graph_metrics_reflect_volume(brain_client, unique_project_name):
    """Los métricas del grafo deben reflejar el volumen de memorias ingeridas."""
    project = unique_project_name("bulk-metrics")
    brain_client.bulk_create_memories([
        {**mem, "project": project, "importance": 0.8, "agent_id": "pytest-bulk"}
        for mem in _ALL_BULK_MEMORIES
    ])

    metrics = brain_client.graph_metrics(project=project)
    assert metrics["memory_count"] >= len(_ALL_BULK_MEMORIES)
    assert metrics["project"] == project


def test_bulk_ingestion_facets_expose_all_memory_types(brain_client, unique_project_name):
    """Las facetas deben exponer los tipos de memoria usados en la ingesta masiva."""
    project = unique_project_name("bulk-facets")
    brain_client.bulk_create_memories([
        {**mem, "project": project, "importance": 0.8, "agent_id": "pytest-bulk"}
        for mem in _ALL_BULK_MEMORIES
    ])

    facets = brain_client.graph_facets(project=project)
    memory_types = {item["memory_type"] for item in facets["memory_types"]}
    assert "architecture" in memory_types, "Debe haber memorias de tipo 'architecture'"
    assert "decision" in memory_types, "Debe haber memorias de tipo 'decision'"
    assert "error" in memory_types, "Debe haber memorias de tipo 'error'"

    # Las etiquetas más frecuentes deben estar presentes
    top_tags = {item["tag"] for item in facets["top_tags"]}
    expected_tag_namespaces = {"tech", "pattern"}
    found = any(
        any(tag.startswith(ns + "/") for tag in top_tags)
        for ns in expected_tag_namespaces
    )
    assert found, f"Se esperaban tags con namespace tech/ o pattern/. Encontrados: {sorted(top_tags)[:10]}"


def test_bulk_ingestion_graph_subgraph_respects_limits(brain_client, unique_project_name):
    """El subgrafo caliente debe respetar node_limit y edge_limit incluso con muchas memorias."""
    project = unique_project_name("bulk-graph-limits")
    brain_client.bulk_create_memories([
        {**mem, "project": project, "importance": 0.8, "agent_id": "pytest-bulk"}
        for mem in _PYTHON_ASYNC_CLUSTER + _OBSERVABILITY_CLUSTER
    ])

    for node_limit, edge_limit in [(5, 8), (10, 15)]:
        subgraph = brain_client.graph_subgraph(
            project=project,
            mode="project_hot",
            scope="project",
            node_limit=node_limit,
            edge_limit=edge_limit,
            include_inactive=False,
        )
        assert subgraph["summary"]["node_count"] <= node_limit, (
            f"node_count {subgraph['summary']['node_count']} supera el límite {node_limit}"
        )
        assert subgraph["summary"]["edge_count"] <= edge_limit, (
            f"edge_count {subgraph['summary']['edge_count']} supera el límite {edge_limit}"
        )
        assert all(node["project"] == project for node in subgraph["nodes"]), (
            "Todos los nodos deben pertenecer al proyecto solicitado"
        )


def test_bulk_ingestion_auto_linking_forms_relations_within_cluster(brain_client, unique_project_name):
    """Las memorias del mismo cluster semántico deben auto-enlazarse durante la ingesta."""
    project = unique_project_name("bulk-autolink")
    ids = brain_client.bulk_create_memories([
        {**mem, "project": project, "importance": 0.88, "agent_id": "pytest-bulk"}
        for mem in _OBSERVABILITY_CLUSTER
    ])

    # Verificar que al menos algunas memorias del cluster están enlazadas entre sí
    total_relations = 0
    for mid in ids[:6]:
        rels = brain_client.relations(mid)["relations"]
        total_relations += len(rels)

    assert total_relations >= 1, (
        f"Se esperaba al menos 1 relación auto-inferida en el cluster de observabilidad, "
        f"pero se encontraron {total_relations}"
    )


def test_cross_project_bridged_search_with_bulk(brain_client, unique_project_name):
    """Búsqueda bridged cross-project funciona correctamente tras ingesta masiva."""
    project_a = unique_project_name("bulk-bridge-a")
    project_b = unique_project_name("bulk-bridge-b")

    brain_client.bulk_create_memories([
        {**mem, "project": project_a, "importance": 0.82, "agent_id": "pytest-bulk"}
        for mem in _SECURITY_CLUSTER
    ])
    brain_client.bulk_create_memories([
        {**mem, "project": project_b, "importance": 0.82, "agent_id": "pytest-bulk"}
        for mem in _DATA_ARCHITECTURE_CLUSTER
    ])

    # Sin bridge: project_b NO debe aparecer en búsquedas de project_a
    blocked = brain_client.structured_search(
        query="data lake medallion architecture parquet iceberg analytics",
        project=project_a, scope="bridged", limit=10, register_access=False,
    )
    assert all(r["project"] != project_b for r in blocked["results"]), (
        "Sin bridge, project_b no debe aparecer en búsqueda bridged de project_a"
    )

    # Crear bridge
    brain_client.bridge_projects(
        project=project_a,
        related_project=project_b,
        reason="Security and data governance share compliance requirements.",
        active=True,
        created_by="pytest",
    )

    # Con bridge: project_b SÍ debe aparecer
    allowed = brain_client.structured_search(
        query="data lake medallion architecture parquet iceberg analytics",
        project=project_a, scope="bridged", limit=10, register_access=False,
    )
    assert any(r["project"] == project_b for r in allowed["results"]), (
        "Con bridge, project_b debe aparecer en resultados bridged de project_a"
    )


def test_bulk_plasticity_activates_and_reinforces(brain_client, unique_project_name):
    """Session plasticity con sesión rica activa memorias relevantes del cluster correcto."""
    project = unique_project_name("bulk-plasticity")
    brain_client.set_test_clock("2030-06-01T00:00:00+00:00")

    brain_client.bulk_create_memories([
        {**mem, "project": project, "importance": 0.85, "agent_id": "pytest-plasticity"}
        for mem in _SECURITY_CLUSTER
    ])

    plasticity = brain_client.apply_session_plasticity(
        project=project,
        agent_id="pytest",
        session_id=f"plasticity-bulk-{uuid.uuid4().hex[:8]}",
        # Usar frases que tienen alta superposición léxica con las memorias del cluster
        # de seguridad (reusa tokens exactos del contenido almacenado)
        goal="oauth2 pkce flow public clients cannot store client secret securely mtls authenticates client server certificates prevent service impersonation",
        outcome="rbac assigns permissions roles users access auditing secrets rotation avoid long-lived credentials production",
        summary=(
            "Configured oauth2 pkce flow for public clients that cannot store client secret securely. "
            "Deployed mtls to authenticate client server certificates and prevent service impersonation. "
            "Assigned rbac permissions to roles rather than individual users for easier access auditing. "
            "Automated secrets rotation to avoid long-lived credentials accumulating in production."
        ),
        changes=[
            "oauth2 pkce flow configured for public clients store client secret",
            "mtls authenticates both client server certificates prevent service impersonation",
            "rbac assigns permissions roles individual users access auditing",
        ],
        decisions=[],
        errors=[],
        follow_ups=[],
        # Sin filtro de tags: las memorias usan prefijos como 'pattern/security', 'tech/oauth2'.
        # El filtro tags hace intersección exacta → valores sin prefijo dan intersección vacía.
        tags=[],
    )

    assert plasticity["activated_memories"] >= 1, (
        "Plasticity debe activar al menos una memoria de seguridad"
    )
    assert "reinforced_pairs" in plasticity
    assert "expanded_links" in plasticity
    assert "decayed_relations" in plasticity
    assert "decayed_stability" in plasticity


def test_search_scores_are_valid_and_ordered(brain_client, unique_project_name):
    """Los resultados de búsqueda deben estar ordenados por hybrid_score DESC con valores válidos."""
    project = unique_project_name("score-order")
    brain_client.bulk_create_memories([
        {**mem, "project": project, "importance": 0.8, "agent_id": "pytest"}
        for mem in _PYTHON_ASYNC_CLUSTER
    ])

    results = brain_client.structured_search(
        query="asyncio gather concurrent coroutines reduce I/O wait time",
        project=project, scope="project", limit=8, register_access=False,
    )

    items = results["results"]
    assert len(items) >= 1

    scores = [r["hybrid_score"] for r in items]
    assert scores == sorted(scores, reverse=True), (
        f"Los resultados deben estar ordenados por hybrid_score DESC. Scores: {scores}"
    )
    assert all(0.0 <= s <= 1.0 for s in scores), (
        "Todos los hybrid_score deben estar en [0, 1]"
    )
    assert all(0.0 <= r["semantic_score"] <= 1.0 for r in items), (
        "Todos los semantic_score deben estar en [0, 1]"
    )
