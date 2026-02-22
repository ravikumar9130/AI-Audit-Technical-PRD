-- =============================================================================
-- Audit AI Database Schema
-- Enterprise-grade speech intelligence platform
-- =============================================================================

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Enable JSONB for flexible schemas
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- =============================================================================
-- Users & Authentication
-- =============================================================================

CREATE TYPE user_role AS ENUM ('Agent', 'Manager', 'CXO', 'Admin');
CREATE TYPE user_status AS ENUM ('active', 'inactive', 'suspended');

CREATE TABLE users (
    user_id SERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    role user_role NOT NULL DEFAULT 'Agent',
    department VARCHAR(100),
    manager_id INTEGER REFERENCES users(user_id) ON DELETE SET NULL,
    status user_status NOT NULL DEFAULT 'active',
    mfa_enabled BOOLEAN DEFAULT FALSE,
    mfa_secret VARCHAR(255),
    last_login TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_role ON users(role);
CREATE INDEX idx_users_manager ON users(manager_id);

-- =============================================================================
-- Multi-tenant Clients/Organizations
-- =============================================================================

CREATE TABLE clients (
    client_id SERIAL PRIMARY KEY,
    org_name VARCHAR(255) NOT NULL,
    api_key_hash VARCHAR(255),
    retention_days INTEGER DEFAULT 2555,  -- 7 years
    data_classification VARCHAR(50) DEFAULT 'standard',
    gdpr_enabled BOOLEAN DEFAULT TRUE,
    hipaa_enabled BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =============================================================================
-- Scoring Templates (Call Types)
-- =============================================================================

CREATE TYPE vertical_type AS ENUM ('Sales', 'Support', 'Collections');

CREATE TABLE scoring_templates (
    template_id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    vertical vertical_type NOT NULL,
    system_prompt TEXT NOT NULL,
    user_prompt_template TEXT NOT NULL,
    json_schema JSONB NOT NULL,
    scoring_weights JSONB NOT NULL,  -- e.g., {"CQS": 0.25, "ECS": 0.20}
    version INTEGER DEFAULT 1,
    is_active BOOLEAN DEFAULT TRUE,
    created_by INTEGER REFERENCES users(user_id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_templates_vertical ON scoring_templates(vertical);
CREATE INDEX idx_templates_active ON scoring_templates(is_active);

-- =============================================================================
-- Call Records
-- =============================================================================

CREATE TYPE call_status AS ENUM ('queued', 'processing', 'completed', 'failed', 'cancelled');

CREATE TABLE calls (
    call_id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(user_id),
    client_id INTEGER REFERENCES clients(client_id),
    template_id INTEGER REFERENCES scoring_templates(template_id),
    batch_id UUID,
    s3_path VARCHAR(500) NOT NULL,
    original_filename VARCHAR(255),
    file_size_bytes BIGINT,
    duration_seconds INTEGER,
    status call_status DEFAULT 'queued',
    processing_started_at TIMESTAMP,
    processing_completed_at TIMESTAMP,
    error_message TEXT,
    metadata JSONB,  -- e.g., source, campaign_id
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_calls_user ON calls(user_id);
CREATE INDEX idx_calls_status ON calls(status);
CREATE INDEX idx_calls_batch ON calls(batch_id);
CREATE INDEX idx_calls_created ON calls(created_at);
CREATE INDEX idx_calls_client ON calls(client_id);

-- =============================================================================
-- Media Files (Raw Audio)
-- =============================================================================

CREATE TABLE media_files (
    media_id SERIAL PRIMARY KEY,
    call_id INTEGER NOT NULL REFERENCES calls(call_id) ON DELETE CASCADE,
    s3_key VARCHAR(500) NOT NULL,
    file_format VARCHAR(20),  -- wav, mp3, etc.
    sample_rate INTEGER,
    channels INTEGER,
    duration_seconds INTEGER,
    file_size_bytes BIGINT,
    checksum VARCHAR(64),
    encryption_enabled BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_media_call ON media_files(call_id);

-- =============================================================================
-- Transcripts (ASR Output)
-- =============================================================================

CREATE TABLE transcripts (
    transcript_id SERIAL PRIMARY KEY,
    call_id INTEGER NOT NULL REFERENCES calls(call_id) ON DELETE CASCADE,
    speaker_label VARCHAR(50) NOT NULL,  -- "Agent", "Customer", "SPEAKER_00"
    start_time FLOAT NOT NULL,  -- seconds
    end_time FLOAT NOT NULL,
    text TEXT NOT NULL,
    confidence FLOAT,  -- ASR confidence score
    emotion VARCHAR(50),  -- Optional: happy, neutral, angry
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_transcripts_call ON transcripts(call_id);
CREATE INDEX idx_transcripts_time ON transcripts(call_id, start_time);

-- =============================================================================
-- Evaluation Results (LLM Scoring)
-- =============================================================================

CREATE TABLE evaluation_results (
    result_id SERIAL PRIMARY KEY,
    call_id INTEGER UNIQUE NOT NULL REFERENCES calls(call_id) ON DELETE CASCADE,
    
    -- Overall Scores
    overall_score FLOAT NOT NULL,
    ses_score FLOAT,  -- Sales Excellence Score
    sqs_score FLOAT,  -- Service Quality Score
    res_score FLOAT,  -- Recovery Efficiency Score
    
    -- Pillar Scores (JSONB for flexibility)
    pillar_scores JSONB,
    
    -- Compliance & Flags
    compliance_flags JSONB,
    fatal_flaw_detected BOOLEAN DEFAULT FALSE,
    fatal_flaw_type VARCHAR(100),
    
    -- AI Analysis
    summary TEXT,
    recommendations JSONB,
    sentiment_score FLOAT,  -- Net Sentiment Score
    
    -- Raw LLM Output
    full_json_output JSONB NOT NULL,
    prompt_version INTEGER,
    model_used VARCHAR(100),
    
    -- Processing metadata
    processing_duration_seconds INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_eval_call ON evaluation_results(call_id);
CREATE INDEX idx_eval_score ON evaluation_results(overall_score);
CREATE INDEX idx_eval_fatal ON evaluation_results(fatal_flaw_detected);

-- =============================================================================
-- Processing Jobs (Pipeline Tracking)
-- =============================================================================

CREATE TYPE pipeline_stage AS ENUM (
    'uploaded', 'normalization', 'vad', 'diarization', 
    'transcription', 'scoring', 'completed', 'failed'
);

CREATE TABLE processing_jobs (
    job_id SERIAL PRIMARY KEY,
    call_id INTEGER NOT NULL REFERENCES calls(call_id) ON DELETE CASCADE,
    stage pipeline_stage NOT NULL,
    status VARCHAR(50) NOT NULL,  -- in_progress, completed, failed
    celery_task_id VARCHAR(255),
    started_at TIMESTAMP,
    finished_at TIMESTAMP,
    error_message TEXT,
    metadata JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_jobs_call ON processing_jobs(call_id);
CREATE INDEX idx_jobs_stage ON processing_jobs(stage);

-- =============================================================================
-- Batches (Bulk Uploads)
-- =============================================================================

CREATE TABLE batches (
    batch_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id INTEGER NOT NULL REFERENCES users(user_id),
    client_id INTEGER REFERENCES clients(client_id),
    num_calls INTEGER NOT NULL,
    num_completed INTEGER DEFAULT 0,
    num_failed INTEGER DEFAULT 0,
    status VARCHAR(50) DEFAULT 'processing',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP
);

CREATE INDEX idx_batches_user ON batches(user_id);

-- =============================================================================
-- Audit Logs (SOC2 Compliance)
-- =============================================================================

CREATE TYPE audit_action AS ENUM (
    'login', 'logout', 'upload', 'view', 'delete', 
    'download', 'api_call', 'config_change', 'data_export'
);

CREATE TABLE audit_logs (
    log_id BIGSERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(user_id),
    client_id INTEGER REFERENCES clients(client_id),
    action_type audit_action NOT NULL,
    resource_type VARCHAR(100),  -- call, user, template, etc.
    resource_id VARCHAR(100),
    ip_address INET,
    user_agent TEXT,
    request_path VARCHAR(500),
    request_method VARCHAR(10),
    response_status INTEGER,
    metadata JSONB,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_audit_user ON audit_logs(user_id);
CREATE INDEX idx_audit_action ON audit_logs(action_type);
CREATE INDEX idx_audit_timestamp ON audit_logs(timestamp);
CREATE INDEX idx_audit_resource ON audit_logs(resource_type, resource_id);

-- =============================================================================
-- Performance Metrics (Monitoring)
-- =============================================================================

CREATE TABLE performance_metrics (
    metric_id SERIAL PRIMARY KEY,
    metric_name VARCHAR(100) NOT NULL,
    metric_value FLOAT NOT NULL,
    call_id INTEGER REFERENCES calls(call_id),
    stage VARCHAR(50),
    metadata JSONB,
    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_metrics_name ON performance_metrics(metric_name);
CREATE INDEX idx_metrics_call ON performance_metrics(call_id);

-- =============================================================================
-- Retention Schedule (GDPR/CCPA)
-- =============================================================================

CREATE TABLE retention_schedule (
    schedule_id SERIAL PRIMARY KEY,
    call_id INTEGER NOT NULL REFERENCES calls(call_id) ON DELETE CASCADE,
    scheduled_deletion_at TIMESTAMP NOT NULL,
    reason VARCHAR(100),  -- retention_policy, user_request, etc.
    status VARCHAR(50) DEFAULT 'pending',
    executed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_retention_schedule ON retention_schedule(scheduled_deletion_at);

-- =============================================================================
-- Insert Default Data
-- =============================================================================

-- Insert default client
INSERT INTO clients (org_name, retention_days) 
VALUES ('Default Organization', 2555);

-- Insert default scoring templates
INSERT INTO scoring_templates (
    name, vertical, system_prompt, user_prompt_template, json_schema, scoring_weights
) VALUES (
    'Sales - Cold Call',
    'Sales',
    'You are a QA Auditor for sales calls. Analyze the transcript and output JSON only.',
    'Evaluate this sales call for: greeting, discovery, objection handling, closing attempt. Transcript: {transcript}',
    '{
        "type": "object",
        "properties": {
            "overall_score": {"type": "number", "minimum": 0, "maximum": 100},
            "cqs_score": {"type": "number"},
            "ecs_score": {"type": "number"},
            "phs_score": {"type": "number"},
            "dis_score": {"type": "number"},
            "ros_score": {"type": "number"},
            "compliance_flags": {"type": "object"},
            "summary": {"type": "string"},
            "recommendations": {"type": "array", "items": {"type": "string"}}
        },
        "required": ["overall_score", "summary"]
    }'::jsonb,
    '{"CQS": 0.25, "ECS": 0.25, "PHS": 0.20, "DIS": 0.15, "ROS": 0.15}'::jsonb
);

INSERT INTO scoring_templates (
    name, vertical, system_prompt, user_prompt_template, json_schema, scoring_weights
) VALUES (
    'Support - Technical Issue',
    'Support',
    'You are a QA Auditor for support calls. Analyze the transcript and output JSON only.',
    'Evaluate this support call for: first contact resolution, empathy, efficiency, product knowledge. Transcript: {transcript}',
    '{
        "type": "object",
        "properties": {
            "overall_score": {"type": "number", "minimum": 0, "maximum": 100},
            "fcr_score": {"type": "number"},
            "emp_score": {"type": "number"},
            "eff_score": {"type": "number"},
            "sat_score": {"type": "number"},
            "prk_score": {"type": "number"},
            "compliance_flags": {"type": "object"},
            "summary": {"type": "string"},
            "recommendations": {"type": "array", "items": {"type": "string"}}
        },
        "required": ["overall_score", "summary"]
    }'::jsonb,
    '{"FCR": 0.30, "EMP": 0.25, "EFF": 0.20, "SAT": 0.15, "PRK": 0.10}'::jsonb
);

INSERT INTO scoring_templates (
    name, vertical, system_prompt, user_prompt_template, json_schema, scoring_weights
) VALUES (
    'Collections - Payment Follow-up',
    'Collections',
    'You are a compliance auditor for collections calls. Check for harassment, threats, privacy violations. Output JSON only.',
    'Evaluate this collections call for: compliance, negotiation skill, promise quality, amount recovered. Transcript: {transcript}',
    '{
        "type": "object",
        "properties": {
            "overall_score": {"type": "number", "minimum": 0, "maximum": 100},
            "cmp_score": {"type": "number"},
            "neg_score": {"type": "number"},
            "ptp_score": {"type": "number"},
            "amt_score": {"type": "number"},
            "compliance_violation": {"type": "boolean"},
            "compliance_flags": {"type": "object"},
            "summary": {"type": "string"},
            "recommendations": {"type": "array", "items": {"type": "string"}}
        },
        "required": ["overall_score", "compliance_violation", "summary"]
    }'::jsonb,
    '{"CMP": 0.40, "NEG": 0.25, "PTP": 0.20, "AMT": 0.15}'::jsonb
);
