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
