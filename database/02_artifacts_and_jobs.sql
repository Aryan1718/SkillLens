-- Option B enterprise artifact and job tables.
-- Do not modify the existing expanded skills table in this migration.

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS repo_sources (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  repository_url TEXT NOT NULL,
  provider TEXT NOT NULL DEFAULT 'github',
  owner TEXT NOT NULL,
  repo TEXT NOT NULL,
  default_branch TEXT,
  fetch_status TEXT NOT NULL DEFAULT 'queued',
  attempt_count INTEGER NOT NULL DEFAULT 0,
  last_error TEXT,
  last_fetched_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_repo_sources_repository_url_unique
ON repo_sources (repository_url);

CREATE INDEX IF NOT EXISTS idx_repo_sources_provider_owner_repo
ON repo_sources (provider, owner, repo);

CREATE TABLE IF NOT EXISTS skill_artifacts (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  skill_id UUID NOT NULL REFERENCES skills(id) ON DELETE CASCADE,
  repo_source_id UUID NOT NULL REFERENCES repo_sources(id) ON DELETE CASCADE,
  repo_skill_path TEXT,
  parse_version TEXT NOT NULL DEFAULT 'v1',
  artifact_hash TEXT NOT NULL,
  bucket_name TEXT NOT NULL DEFAULT 'skill-artifacts',
  storage_prefix TEXT NOT NULL,
  files_manifest JSONB NOT NULL DEFAULT '[]'::jsonb,
  fetch_status TEXT NOT NULL DEFAULT 'queued',
  attempt_count INTEGER NOT NULL DEFAULT 0,
  last_error TEXT,
  fetched_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_skill_artifacts_skill_hash_parse_unique
ON skill_artifacts (skill_id, artifact_hash, parse_version);

CREATE INDEX IF NOT EXISTS idx_skill_artifacts_repo_source
ON skill_artifacts (repo_source_id);

CREATE TABLE IF NOT EXISTS skill_analyses (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  skill_id UUID NOT NULL REFERENCES skills(id) ON DELETE CASCADE,
  repo_source_id UUID REFERENCES repo_sources(id) ON DELETE SET NULL,
  artifact_id UUID NOT NULL REFERENCES skill_artifacts(id) ON DELETE CASCADE,
  analysis_version TEXT NOT NULL DEFAULT 'a1',
  status TEXT NOT NULL DEFAULT 'queued',
  overall_score NUMERIC(5,2),
  trust_badge TEXT,
  security_data JSONB,
  quality_data JSONB,
  behavior_data JSONB,
  dependency_data JSONB,
  started_at TIMESTAMPTZ,
  completed_at TIMESTAMPTZ,
  error_message TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_skill_analyses_artifact_version_unique
ON skill_analyses (artifact_id, analysis_version);

CREATE INDEX IF NOT EXISTS idx_skill_analyses_skill_created
ON skill_analyses (skill_id, created_at DESC);

CREATE TABLE IF NOT EXISTS analysis_jobs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  job_type TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'queued',
  priority INTEGER NOT NULL DEFAULT 100,
  skill_id UUID REFERENCES skills(id) ON DELETE CASCADE,
  repo_source_id UUID REFERENCES repo_sources(id) ON DELETE SET NULL,
  artifact_id UUID REFERENCES skill_artifacts(id) ON DELETE CASCADE,
  payload JSONB NOT NULL DEFAULT '{}'::jsonb,
  attempt_count INTEGER NOT NULL DEFAULT 0,
  max_attempts INTEGER NOT NULL DEFAULT 5,
  last_error TEXT,
  run_after TIMESTAMPTZ NOT NULL DEFAULT now(),
  started_at TIMESTAMPTZ,
  finished_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_analysis_jobs_status_priority_run_after
ON analysis_jobs (status, priority, run_after);

CREATE UNIQUE INDEX IF NOT EXISTS idx_analysis_jobs_fetch_artifacts_dedupe
ON analysis_jobs (skill_id)
WHERE job_type = 'fetch_artifacts' AND status IN ('queued', 'running');

CREATE UNIQUE INDEX IF NOT EXISTS idx_analysis_jobs_analyze_dedupe
ON analysis_jobs (artifact_id)
WHERE job_type = 'analyze' AND status IN ('queued', 'running');
