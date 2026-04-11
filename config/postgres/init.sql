-- Ensure the application role exists regardless of POSTGRES_USER ordering.
-- DO block is idempotent: only creates the role if it doesn't already exist.
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'memoryuser') THEN
    CREATE ROLE memoryuser WITH LOGIN SUPERUSER PASSWORD 'change-me';
  END IF;
END
$$;

CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE TABLE IF NOT EXISTS projects (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) UNIQUE NOT NULL,
    description TEXT,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS tasks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
    title VARCHAR(500) NOT NULL,
    description TEXT,
    state VARCHAR(50) DEFAULT 'pending',
    priority INTEGER DEFAULT 5,
    agent_id VARCHAR(100),
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    CONSTRAINT tasks_project_title_unique UNIQUE (project_id, title)
);

CREATE TABLE IF NOT EXISTS decisions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
    title VARCHAR(500) NOT NULL,
    context TEXT,
    decision TEXT NOT NULL,
    rationale TEXT,
    alternatives TEXT,
    agent_id VARCHAR(100),
    tags TEXT[] DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS known_errors (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
    error_signature VARCHAR(500) NOT NULL,
    description TEXT NOT NULL,
    solution TEXT,
    occurrence_count INTEGER DEFAULT 1,
    last_seen TIMESTAMPTZ DEFAULT NOW(),
    tags TEXT[] DEFAULT '{}',
    metadata JSONB DEFAULT '{}',
    CONSTRAINT known_errors_project_signature_unique UNIQUE (project_id, error_signature)
);

CREATE TABLE IF NOT EXISTS memory_log (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id UUID REFERENCES projects(id) ON DELETE SET NULL,
    agent_id VARCHAR(100) NOT NULL,
    action_type VARCHAR(100),
    summary TEXT NOT NULL,
    details JSONB DEFAULT '{}',
    importance FLOAT DEFAULT 0.5,
    tags TEXT[] DEFAULT '{}',
    access_count INTEGER DEFAULT 0,
    last_accessed_at TIMESTAMPTZ,
    activation_score FLOAT DEFAULT 0,
    stability_score FLOAT DEFAULT 0.5,
    manual_pin BOOLEAN DEFAULT FALSE,
    -- [1] Ebbinghaus: curva de olvido real
    review_count INT DEFAULT 0,
    stability_halflife_days FLOAT DEFAULT 1.0,
    -- [2] Valencia emocional: carga afectiva de la memoria
    valence FLOAT DEFAULT 0.0,
    arousal FLOAT DEFAULT 0.5,
    -- [3] Sesgo de novedad
    novelty_score FLOAT DEFAULT 0.5,
    -- [6] Nivel de abstracción (0=concreto, 3=esquema abstracto)
    abstraction_level INT DEFAULT 0,
    -- [L0] Keyphrases automáticas (KeyBERT + tags canonicalizados)
    keyphrases TEXT[] DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS reflection_runs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    mode VARCHAR(20) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'queued',
    model VARCHAR(100) NOT NULL,
    input_count INTEGER DEFAULT 0,
    promoted_count INTEGER DEFAULT 0,
    error TEXT,
    started_at TIMESTAMPTZ DEFAULT NOW(),
    finished_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS session_summaries (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
    agent_id VARCHAR(100) NOT NULL,
    session_id VARCHAR(255) NOT NULL,
    payload_json JSONB NOT NULL,
    checksum CHAR(64) NOT NULL UNIQUE,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    last_error TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    reviewed_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS reflection_promotions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    run_id UUID REFERENCES reflection_runs(id) ON DELETE CASCADE,
    project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
    item_type VARCHAR(50) NOT NULL,
    item_hash CHAR(64) NOT NULL,
    target_ref VARCHAR(255),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT reflection_promotions_unique UNIQUE (project_id, item_type, item_hash)
);

CREATE TABLE IF NOT EXISTS memory_relations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    source_memory_id UUID REFERENCES memory_log(id) ON DELETE CASCADE,
    target_memory_id UUID REFERENCES memory_log(id) ON DELETE CASCADE,
    relation_type VARCHAR(50) NOT NULL,
    weight FLOAT DEFAULT 0.5,
    origin VARCHAR(50) NOT NULL DEFAULT 'vector_inference',
    evidence_json JSONB DEFAULT '{}',
    reinforcement_count INTEGER DEFAULT 1,
    last_activated_at TIMESTAMPTZ,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    -- [L1] Myelination: conductivity score for cross-project relations
    myelin_score FLOAT DEFAULT 0.0,
    myelin_last_updated TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT memory_relations_no_self CHECK (source_memory_id <> target_memory_id),
    CONSTRAINT memory_relations_unique UNIQUE (source_memory_id, target_memory_id, relation_type)
);

CREATE TABLE IF NOT EXISTS project_bridges (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
    related_project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
    reason TEXT NOT NULL DEFAULT '',
    active BOOLEAN NOT NULL DEFAULT TRUE,
    created_by VARCHAR(100) NOT NULL DEFAULT 'api',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT project_bridges_no_self CHECK (project_id <> related_project_id),
    CONSTRAINT project_bridges_unique UNIQUE (project_id, related_project_id)
);

-- [7] Cola de contradicciones: pares que se contradicen y necesitan resolución
CREATE TABLE IF NOT EXISTS contradiction_queue (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    memory_a_id UUID REFERENCES memory_log(id) ON DELETE CASCADE,
    memory_b_id UUID REFERENCES memory_log(id) ON DELETE CASCADE,
    resolution_status VARCHAR(20) DEFAULT 'pending',
    resolution_type VARCHAR(30),
    resolution_memory_id UUID REFERENCES memory_log(id) ON DELETE SET NULL,
    condition_text TEXT,
    resolved_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT contradiction_queue_unique UNIQUE (memory_a_id, memory_b_id)
);

-- [6] Vínculos entre memorias-esquema y sus fuentes concretas
CREATE TABLE IF NOT EXISTS schema_sources (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    schema_memory_id UUID REFERENCES memory_log(id) ON DELETE CASCADE,
    source_memory_id UUID REFERENCES memory_log(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT schema_sources_unique UNIQUE (schema_memory_id, source_memory_id)
);

-- [8] Historial de ejecuciones de consolidación profunda (deep sleep)
CREATE TABLE IF NOT EXISTS deep_sleep_runs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    status VARCHAR(20) NOT NULL DEFAULT 'running',
    memories_scanned INT DEFAULT 0,
    schemas_created INT DEFAULT 0,
    contradictions_resolved INT DEFAULT 0,
    memories_pruned INT DEFAULT 0,
    relations_reinforced INT DEFAULT 0,
    error TEXT,
    started_at TIMESTAMPTZ DEFAULT NOW(),
    finished_at TIMESTAMPTZ
);

-- [L0] Synapse candidates: Tier 3 holding area until sleep validates
CREATE TABLE IF NOT EXISTS synapse_candidates (
    id SERIAL PRIMARY KEY,
    source_memory_id UUID NOT NULL REFERENCES memory_log(id) ON DELETE CASCADE,
    target_memory_id UUID NOT NULL REFERENCES memory_log(id) ON DELETE CASCADE,
    semantic_score FLOAT NOT NULL,
    domain_score FLOAT NOT NULL,
    lexical_overlap FLOAT NOT NULL,
    emotional_proximity FLOAT NOT NULL,
    importance_attraction FLOAT NOT NULL,
    temporal_proximity FLOAT NOT NULL,
    type_compatibility FLOAT NOT NULL,
    combined_score FLOAT NOT NULL,
    suggested_type VARCHAR(50),
    status VARCHAR(20) DEFAULT 'pending',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    reviewed_at TIMESTAMPTZ,
    CONSTRAINT synapse_candidates_unique UNIQUE (source_memory_id, target_memory_id)
);

-- [L1] Project permeability: continuous score replacing binary bridges
CREATE TABLE IF NOT EXISTS project_permeability (
    id SERIAL PRIMARY KEY,
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    related_project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    permeability_score FLOAT DEFAULT 0.0,
    organic_origin BOOLEAN DEFAULT TRUE,
    formation_reason TEXT,
    last_activity TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT project_permeability_unique UNIQUE (project_id, related_project_id)
);

-- [L1] Myelination events audit log
CREATE TABLE IF NOT EXISTS myelination_events (
    id SERIAL PRIMARY KEY,
    relation_id UUID REFERENCES memory_relations(id) ON DELETE CASCADE,
    permeability_id INTEGER REFERENCES project_permeability(id) ON DELETE CASCADE,
    event_type VARCHAR(50) NOT NULL,
    delta FLOAT NOT NULL,
    new_score FLOAT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- [L2] Sleep cycles tracking (NREM + REM)
CREATE TABLE IF NOT EXISTS sleep_cycles (
    id SERIAL PRIMARY KEY,
    cycle_type VARCHAR(10) NOT NULL,
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    trigger_reason TEXT,
    projects_processed TEXT[],
    stats JSONB DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_synapse_candidates_status ON synapse_candidates(status);
CREATE INDEX IF NOT EXISTS idx_synapse_candidates_score ON synapse_candidates(combined_score DESC);
CREATE INDEX IF NOT EXISTS idx_project_permeability_score ON project_permeability(permeability_score DESC);
CREATE INDEX IF NOT EXISTS idx_myelination_events_relation ON myelination_events(relation_id);
CREATE INDEX IF NOT EXISTS idx_myelination_events_created ON myelination_events(created_at);
CREATE INDEX IF NOT EXISTS idx_sleep_cycles_type ON sleep_cycles(cycle_type);
CREATE INDEX IF NOT EXISTS idx_sleep_cycles_started ON sleep_cycles(started_at DESC);

CREATE INDEX IF NOT EXISTS idx_tasks_project ON tasks(project_id);
CREATE INDEX IF NOT EXISTS idx_tasks_state ON tasks(state);
CREATE INDEX IF NOT EXISTS idx_decisions_project ON decisions(project_id);
CREATE INDEX IF NOT EXISTS idx_memory_log_project ON memory_log(project_id);
CREATE INDEX IF NOT EXISTS idx_memory_log_agent ON memory_log(agent_id);
CREATE INDEX IF NOT EXISTS idx_memory_log_created ON memory_log(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_memory_log_accessed ON memory_log(last_accessed_at DESC);
CREATE INDEX IF NOT EXISTS idx_known_errors_sig ON known_errors USING gin(to_tsvector('english', error_signature));
CREATE INDEX IF NOT EXISTS idx_session_summaries_project ON session_summaries(project_id);
CREATE INDEX IF NOT EXISTS idx_session_summaries_status ON session_summaries(status, created_at);
CREATE INDEX IF NOT EXISTS idx_reflection_runs_status ON reflection_runs(status, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_reflection_promotions_run ON reflection_promotions(run_id);
CREATE INDEX IF NOT EXISTS idx_memory_relations_source ON memory_relations(source_memory_id, weight DESC);
CREATE INDEX IF NOT EXISTS idx_memory_relations_target ON memory_relations(target_memory_id, weight DESC);
CREATE INDEX IF NOT EXISTS idx_memory_relations_active ON memory_relations(active, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_memory_relations_active_source ON memory_relations(source_memory_id, weight DESC, updated_at DESC) WHERE active = TRUE;
CREATE INDEX IF NOT EXISTS idx_memory_relations_active_target ON memory_relations(target_memory_id, weight DESC, updated_at DESC) WHERE active = TRUE;
CREATE INDEX IF NOT EXISTS idx_memory_log_hotspots ON memory_log(project_id, manual_pin DESC, activation_score DESC, stability_score DESC, last_accessed_at DESC, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_project_bridges_project ON project_bridges(project_id, active);
CREATE INDEX IF NOT EXISTS idx_project_bridges_related ON project_bridges(related_project_id, active);
CREATE INDEX IF NOT EXISTS idx_memory_log_arousal ON memory_log(project_id, arousal DESC) WHERE arousal > 0.6;
CREATE INDEX IF NOT EXISTS idx_memory_log_novelty ON memory_log(project_id, novelty_score DESC) WHERE novelty_score > 0.6;
CREATE INDEX IF NOT EXISTS idx_contradiction_pending ON contradiction_queue(resolution_status) WHERE resolution_status = 'pending';
CREATE INDEX IF NOT EXISTS idx_contradiction_suspected ON contradiction_queue(resolution_status) WHERE resolution_status = 'suspected';
CREATE INDEX IF NOT EXISTS idx_schema_sources_schema ON schema_sources(schema_memory_id);
CREATE INDEX IF NOT EXISTS idx_deep_sleep_runs_status ON deep_sleep_runs(status, started_at DESC);

CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS update_projects_updated_at ON projects;
CREATE TRIGGER update_projects_updated_at BEFORE UPDATE ON projects
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

DROP TRIGGER IF EXISTS update_tasks_updated_at ON tasks;
CREATE TRIGGER update_tasks_updated_at BEFORE UPDATE ON tasks
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

DROP TRIGGER IF EXISTS update_memory_relations_updated_at ON memory_relations;
CREATE TRIGGER update_memory_relations_updated_at BEFORE UPDATE ON memory_relations
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

DROP TRIGGER IF EXISTS update_project_bridges_updated_at ON project_bridges;
CREATE TRIGGER update_project_bridges_updated_at BEFORE UPDATE ON project_bridges
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();
