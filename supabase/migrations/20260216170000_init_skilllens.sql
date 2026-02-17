-- SkillLens initial schema migration
-- Source of truth: AGENTS.md database section + MVP cache hash support

CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- Official skills catalog
CREATE TABLE IF NOT EXISTS skills (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name TEXT NOT NULL,
  source TEXT NOT NULL,
  skill_content TEXT NOT NULL,
  last_fetched TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (source, name)
);

-- Cached analysis results
CREATE TABLE IF NOT EXISTS analyses (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  github_url TEXT,
  content_hash TEXT,
  overall_score DECIMAL(5,2),
  trust_badge TEXT,
  security_data JSONB,
  quality_data JSONB,
  behavior_data JSONB,
  dependency_data JSONB,
  cache_until TIMESTAMPTZ,
  analyzed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Shareable report links
CREATE TABLE IF NOT EXISTS shared_reports (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  analysis_id UUID REFERENCES analyses(id),
  short_code TEXT UNIQUE,
  view_count INTEGER DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Safe alters for existing instances
ALTER TABLE skills ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NOT NULL DEFAULT now();

ALTER TABLE analyses ADD COLUMN IF NOT EXISTS content_hash TEXT;
ALTER TABLE analyses ADD COLUMN IF NOT EXISTS cache_until TIMESTAMPTZ;
ALTER TABLE analyses ADD COLUMN IF NOT EXISTS analyzed_at TIMESTAMPTZ NOT NULL DEFAULT now();
ALTER TABLE analyses ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NOT NULL DEFAULT now();

ALTER TABLE shared_reports ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NOT NULL DEFAULT now();

CREATE INDEX IF NOT EXISTS idx_analyses_github_url ON analyses (github_url);
CREATE INDEX IF NOT EXISTS idx_analyses_cache_until ON analyses (cache_until);
CREATE INDEX IF NOT EXISTS idx_shared_reports_short_code ON shared_reports (short_code);
CREATE INDEX IF NOT EXISTS idx_analyses_content_hash ON analyses (content_hash);
