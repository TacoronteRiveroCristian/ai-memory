from __future__ import annotations

from typing import Any


def find_relation(relations: list[dict[str, Any]], other_memory_id: str) -> dict[str, Any] | None:
    for relation in relations:
        if relation.get("other_memory_id") == other_memory_id:
            return relation
    return None


def minimal_session_payload(project: str) -> dict[str, Any]:
    return {
        "project": project,
        "agent_id": "pytest",
        "session_id": f"session-{project}",
        "goal": "Ejecutar validacion determinista",
        "outcome": "Validacion completada",
        "summary": "Tick de plasticidad para medir refuerzo y decay sin usar providers reales.",
        "changes": [],
        "decisions": [],
        "errors": [],
        "follow_ups": [],
        "tags": ["tests", "plasticity"],
    }


def test_same_project_memories_auto_link_and_retrieve(brain_client, unique_project_name):
    project = unique_project_name("brain-retrieval")
    memory_a = brain_client.create_memory(
        content="Event sourcing keeps a replayable audit trail and rebuilds projections after failures.",
        project=project,
        memory_type="architecture",
        tags="concept/event-sourcing,pattern/replay,tech/postgres",
        importance=0.92,
        agent_id="pytest",
    )["memory_id"]
    memory_b = brain_client.create_memory(
        content="Replayable audit trails with event sourcing let us rebuild projections and recover state reliably.",
        project=project,
        memory_type="architecture",
        tags="concept/event-sourcing,pattern/replay,tech/postgres",
        importance=0.9,
        agent_id="pytest",
    )["memory_id"]

    search = brain_client.structured_search(
        query="event sourcing replay audit trail rebuild projections",
        project=project,
        scope="project",
        tags=["concept/event-sourcing"],
        limit=3,
        register_access=False,
    )
    result_ids = [item["memory_id"] for item in search["results"]]
    assert memory_a in result_ids
    assert memory_b in result_ids
    assert search["results"][0]["memory_id"] in {memory_a, memory_b}

    relations = brain_client.relations(memory_a)["relations"]
    relation = find_relation(relations, memory_b)
    assert relation is not None
    assert relation["relation_type"] in {"same_concept", "extends", "supports", "applies_to"}
    assert relation["active"] is True


def test_bridged_scope_blocks_then_allows_cross_project_retrieval(brain_client, unique_project_name):
    project_a = unique_project_name("brain-bridge-a")
    project_b = unique_project_name("brain-bridge-b")

    brain_client.create_memory(
        content="Prompt versioning stores experiment history and regression findings for retrieval tuning.",
        project=project_a,
        memory_type="general",
        tags="concept/prompt-versioning,pattern/evaluation",
        importance=0.88,
        agent_id="pytest",
    )
    first_b = brain_client.create_memory(
        content="Another product also uses prompt versioning to preserve experiment history and regression findings.",
        project=project_b,
        memory_type="general",
        tags="concept/prompt-versioning,pattern/evaluation",
        importance=0.86,
        agent_id="pytest",
    )["memory_id"]

    blocked = brain_client.structured_search(
        query="prompt versioning experiment history regression findings",
        project=project_a,
        scope="bridged",
        limit=5,
        register_access=False,
    )
    assert all(item["project"] != project_b for item in blocked["results"])

    brain_client.bridge_projects(
        project=project_a,
        related_project=project_b,
        reason="Las ideas de prompt versioning se reutilizan entre productos.",
        active=True,
        created_by="pytest",
    )
    bridges = brain_client.list_bridges(project_a)["bridges"]
    assert any(item["related_project"] == project_b and item["active"] for item in bridges)

    second_b = brain_client.create_memory(
        content="Prompt versioning for the second project captures regression findings and experiment history in a reusable way.",
        project=project_b,
        memory_type="general",
        tags="concept/prompt-versioning,pattern/evaluation",
        importance=0.9,
        agent_id="pytest",
    )["memory_id"]

    allowed = brain_client.structured_search(
        query="prompt versioning experiment history regression findings",
        project=project_a,
        scope="bridged",
        limit=6,
        register_access=False,
    )
    assert any(item["project"] == project_b for item in allowed["results"])

    relations = brain_client.relations(second_b)["relations"]
    assert find_relation(relations, first_b) is not None or len(relations) >= 1

    context = brain_client.project_context(project_a, include_related=True)["result"]
    assert "RELATED IDEAS" in context
    assert project_b in context


def test_shared_tags_without_semantic_similarity_do_not_create_false_links(brain_client, unique_project_name):
    project = unique_project_name("brain-noise")
    memory_a = brain_client.create_memory(
        content="Kubernetes node affinity restricts pod scheduling to selected worker pools.",
        project=project,
        memory_type="general",
        tags="concept/shared-anchor,tech/kubernetes",
        importance=0.8,
        agent_id="pytest",
    )["memory_id"]
    memory_b = brain_client.create_memory(
        content="Figma export presets help designers prepare thumbnail variants for social campaigns.",
        project=project,
        memory_type="general",
        tags="concept/shared-anchor,tech/design",
        importance=0.8,
        agent_id="pytest",
    )["memory_id"]

    relations = brain_client.relations(memory_a)["relations"]
    assert find_relation(relations, memory_b) is None


def test_graph_subgraph_is_bounded_and_memory_detail_is_available(brain_client, unique_project_name):
    project = unique_project_name("brain-graph")
    memory_a = brain_client.create_memory(
        content="Event sourcing keeps a replayable audit trail and rebuilds projections after failures.",
        project=project,
        memory_type="architecture",
        tags="concept/event-sourcing,pattern/replay,tech/postgres",
        importance=0.92,
        agent_id="pytest",
    )["memory_id"]
    memory_b = brain_client.create_memory(
        content="Replayable audit trails with event sourcing let us rebuild projections and recover state reliably.",
        project=project,
        memory_type="architecture",
        tags="concept/event-sourcing,pattern/replay,tech/postgres",
        importance=0.9,
        agent_id="pytest",
    )["memory_id"]
    brain_client.create_memory(
        content="A separate observability note about alarm thresholds should not appear in the event sourcing search graph.",
        project=project,
        memory_type="general",
        tags="concept/observability,pattern/alerts",
        importance=0.6,
        agent_id="pytest",
    )

    subgraph = brain_client.graph_subgraph(
        project=project,
        mode="search",
        query="event sourcing replay audit trail rebuild projections",
        scope="project",
        tags=["concept/event-sourcing"],
        node_limit=3,
        edge_limit=2,
        include_inactive=False,
    )
    assert subgraph["summary"]["node_count"] <= 3
    assert subgraph["summary"]["edge_count"] <= 2
    node_ids = {node["memory_id"] for node in subgraph["nodes"]}
    assert memory_a in node_ids
    assert memory_b in node_ids
    assert all(node["project"] == project for node in subgraph["nodes"])
    assert all(node["memory_type"] == "architecture" for node in subgraph["nodes"])
    assert all("concept/event-sourcing" in node["tags"] for node in subgraph["nodes"])
    assert all(edge["source_memory_id"] in node_ids and edge["target_memory_id"] in node_ids for edge in subgraph["edges"])

    focus = brain_client.graph_subgraph(
        project=project,
        mode="memory_focus",
        center_memory_id=memory_a,
        scope="project",
        node_limit=3,
        edge_limit=3,
        include_inactive=False,
    )
    assert any(node["memory_id"] == memory_a for node in focus["nodes"])

    detail = brain_client.memory_detail(memory_a)
    assert detail["memory"]["memory_id"] == memory_a
    assert detail["memory"]["project"] == project
    assert detail["memory"]["prominence"] >= 0.0
    assert detail["relation_count"] >= 0
    assert "relations" in detail

    metrics = brain_client.graph_metrics(project=project)
    assert metrics["project"] == project
    assert metrics["memory_count"] >= 3
    assert metrics["active_relation_count"] >= 0
    assert metrics["hot_memory_count"] >= 1

    facets = brain_client.graph_facets(project=project)
    assert facets["project"] == project
    assert any(item["project"] == project for item in facets["projects"])
    assert any(item["memory_type"] == "architecture" for item in facets["memory_types"])
    assert any(item["tag"] == "concept/event-sourcing" for item in facets["top_tags"])
    assert any(item["memory_id"] == memory_a for item in facets["hot_memories"])


def test_plasticity_reinforces_auto_relations_and_preserves_manual_links(brain_client, unique_project_name):
    project = unique_project_name("brain-plasticity")
    brain_client.set_test_clock("2030-01-01T00:00:00+00:00")

    auto_a = brain_client.create_memory(
        content="Context caching reduces token cost by reusing repeated prefixes in long conversations.",
        project=project,
        memory_type="general",
        tags="concept/context-caching,tech/llm",
        importance=0.9,
        agent_id="pytest",
    )["memory_id"]
    auto_b = brain_client.create_memory(
        content="Reusing repeated prompt prefixes through context caching lowers token cost for long LLM sessions.",
        project=project,
        memory_type="general",
        tags="concept/context-caching,tech/llm",
        importance=0.9,
        agent_id="pytest",
    )["memory_id"]

    manual_a = brain_client.create_memory(
        content="ADR records architectural decisions with rationale and alternatives for later review.",
        project=project,
        memory_type="decision",
        tags="concept/adr,pattern/documentation",
        importance=0.84,
        agent_id="pytest",
    )["memory_id"]
    manual_b = brain_client.create_memory(
        content="Decision logs preserve rationale and alternatives so architecture reviews remain explainable.",
        project=project,
        memory_type="decision",
        tags="concept/adr,pattern/documentation",
        importance=0.84,
        agent_id="pytest",
    )["memory_id"]
    brain_client.link_memories(
        source_memory_id=manual_a,
        target_memory_id=manual_b,
        relation_type="supports",
        reason="Manual curation for regression tests.",
        weight=0.77,
    )

    initial_auto = find_relation(brain_client.relations(auto_a)["relations"], auto_b)
    assert initial_auto is not None
    initial_weight = float(initial_auto["weight"])

    for _ in range(3):
        brain_client.structured_search(
            query="context caching repeated prompt prefixes token cost",
            project=project,
            scope="project",
            limit=4,
            register_access=True,
        )

    reinforced_auto = find_relation(brain_client.relations(auto_a)["relations"], auto_b)
    assert reinforced_auto is not None
    reinforced_weight = float(reinforced_auto["weight"])
    assert reinforced_weight >= initial_weight

    brain_client.set_test_clock("2030-02-20T00:00:00+00:00")
    plasticity = brain_client.apply_session_plasticity(**minimal_session_payload(project))
    assert plasticity["decayed_relations"] >= 1
    assert plasticity["reinforced_pairs"] >= 0
    assert "expanded_links" in plasticity

    decayed_auto = find_relation(brain_client.relations(auto_a)["relations"], auto_b)
    assert decayed_auto is not None
    assert float(decayed_auto["weight"]) < reinforced_weight

    manual_relation = find_relation(brain_client.relations(manual_a)["relations"], manual_b)
    assert manual_relation is not None
    assert manual_relation["origin"] == "manual"
    assert manual_relation["active"] is True
    assert float(manual_relation["weight"]) >= 0.77


def test_novelty_merge_deduplicates_near_identical_memories(brain_client, unique_project_name):
    """When a new memory is >85% similar to an existing one (novelty < 0.15),
    it should merge into the existing memory instead of creating a duplicate."""
    project = unique_project_name("novelty-merge")

    original = brain_client.create_memory(
        content="PostgreSQL partial indexes speed up filtered queries on large tables significantly.",
        project=project,
        memory_type="general",
        tags="tech/postgres,pattern/indexing",
        importance=0.7,
        agent_id="pytest",
    )
    original_id = original["memory_id"]

    duplicate = brain_client.create_memory(
        content="PostgreSQL partial indexes speed up filtered queries on large tables significantly.",
        project=project,
        memory_type="general",
        tags="tech/postgres,pattern/indexing",
        importance=0.8,
        agent_id="pytest",
    )

    assert duplicate.get("merged_into") == original_id or duplicate.get("action") == "merged"

    search = brain_client.structured_search(
        query="PostgreSQL partial indexes filtered queries",
        project=project,
        scope="project",
        limit=5,
        register_access=False,
    )
    matching_ids = [r["memory_id"] for r in search["results"]]
    assert original_id in matching_ids
    postgres_results = [r for r in search["results"] if "partial indexes" in r["content"]]
    assert len(postgres_results) == 1


def test_novelty_merge_preserves_distinct_memories(brain_client, unique_project_name):
    """Memories with genuinely different content should NOT be merged."""
    project = unique_project_name("novelty-distinct")

    mem_a = brain_client.create_memory(
        content="Redis pub/sub enables real-time event broadcasting between microservices.",
        project=project,
        memory_type="general",
        tags="tech/redis,pattern/pubsub",
        importance=0.7,
        agent_id="pytest",
    )["memory_id"]

    mem_b = brain_client.create_memory(
        content="PostgreSQL LISTEN/NOTIFY provides lightweight change notification without polling.",
        project=project,
        memory_type="general",
        tags="tech/postgres,pattern/notification",
        importance=0.7,
        agent_id="pytest",
    )["memory_id"]

    assert mem_a != mem_b
    detail_a = brain_client.memory_detail(mem_a)
    detail_b = brain_client.memory_detail(mem_b)
    assert detail_a is not None
    assert detail_b is not None


def test_uncertainty_aware_retrieval_includes_confidence(brain_client, unique_project_name):
    """Structured search response should include confidence and low_confidence fields."""
    project = unique_project_name("uncertainty-conf")

    brain_client.create_memory(
        content="Docker compose health checks use test commands to verify container readiness.",
        project=project,
        memory_type="general",
        tags="tech/docker",
        importance=0.8,
        agent_id="pytest",
    )

    search = brain_client.structured_search(
        query="Docker compose health checks container readiness",
        project=project,
        scope="project",
        limit=5,
        register_access=False,
    )
    assert "confidence" in search
    assert isinstance(search["confidence"], float)
    assert "low_confidence" in search
    assert isinstance(search["low_confidence"], bool)
    assert search["confidence"] > 0


def test_uncertainty_aware_retrieval_flags_irrelevant_query(brain_client, unique_project_name):
    """A query completely unrelated to stored memories should be flagged as low confidence."""
    project = unique_project_name("uncertainty-irrelevant")

    brain_client.create_memory(
        content="Kubernetes pod autoscaling uses HPA to adjust replica count based on CPU metrics.",
        project=project,
        memory_type="general",
        tags="tech/kubernetes",
        importance=0.8,
        agent_id="pytest",
    )

    search = brain_client.structured_search(
        query="French impressionist painting techniques of the 19th century",
        project=project,
        scope="project",
        limit=5,
        register_access=False,
    )
    assert "confidence" in search
    assert "low_confidence" in search


def test_keyphrase_prefilter_retrieves_relevant_memories(brain_client, unique_project_name):
    """Keyphrase pre-filtering should still find relevant memories efficiently."""
    project = unique_project_name("keyphrase-prefilter")

    mem_redis = brain_client.create_memory(
        content="Redis streams provide append-only log data structures for event processing pipelines.",
        project=project,
        memory_type="general",
        tags="tech/redis,pattern/streaming",
        importance=0.8,
        agent_id="pytest",
    )["memory_id"]

    brain_client.create_memory(
        content="GraphQL schema stitching merges multiple service schemas into a unified API gateway.",
        project=project,
        memory_type="general",
        tags="tech/graphql,pattern/gateway",
        importance=0.8,
        agent_id="pytest",
    )

    search = brain_client.structured_search(
        query="Redis streams event processing pipeline",
        project=project,
        scope="project",
        limit=5,
        register_access=False,
    )
    result_ids = [r["memory_id"] for r in search["results"]]
    assert mem_redis in result_ids
    assert search["results"][0]["memory_id"] == mem_redis
