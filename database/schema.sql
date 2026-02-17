-- SkillLens schema (current state)
-- Mirrors supabase migrations and is safe to re-run.

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

-- Expanded capture attributes for skills.sh pages
ALTER TABLE skills ADD COLUMN IF NOT EXISTS owner TEXT;
ALTER TABLE skills ADD COLUMN IF NOT EXISTS repo TEXT;
ALTER TABLE skills ADD COLUMN IF NOT EXISTS skill_slug TEXT;
ALTER TABLE skills ADD COLUMN IF NOT EXISTS page_url TEXT;
ALTER TABLE skills ADD COLUMN IF NOT EXISTS repository_url TEXT;
ALTER TABLE skills ADD COLUMN IF NOT EXISTS install_command TEXT;
ALTER TABLE skills ADD COLUMN IF NOT EXISTS skill_md_rendered TEXT;
ALTER TABLE skills ADD COLUMN IF NOT EXISTS skill_md_hash TEXT;
ALTER TABLE skills ADD COLUMN IF NOT EXISTS raw_html TEXT;
ALTER TABLE skills ADD COLUMN IF NOT EXISTS extracted_links JSONB NOT NULL DEFAULT '[]'::jsonb;
ALTER TABLE skills ADD COLUMN IF NOT EXISTS weekly_installs BIGINT;
ALTER TABLE skills ADD COLUMN IF NOT EXISTS first_seen_date DATE;
ALTER TABLE skills ADD COLUMN IF NOT EXISTS installed_on JSONB NOT NULL DEFAULT '{}'::jsonb;
ALTER TABLE skills ADD COLUMN IF NOT EXISTS scraped_at TIMESTAMPTZ;
ALTER TABLE skills ADD COLUMN IF NOT EXISTS last_seen_at TIMESTAMPTZ;
ALTER TABLE skills ADD COLUMN IF NOT EXISTS parse_version TEXT NOT NULL DEFAULT 'v1';

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

ALTER TABLE analyses ADD COLUMN IF NOT EXISTS content_hash TEXT;
ALTER TABLE analyses ADD COLUMN IF NOT EXISTS cache_until TIMESTAMPTZ;
ALTER TABLE analyses ADD COLUMN IF NOT EXISTS analyzed_at TIMESTAMPTZ NOT NULL DEFAULT now();
ALTER TABLE analyses ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NOT NULL DEFAULT now();

-- Shareable report links
CREATE TABLE IF NOT EXISTS shared_reports (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  analysis_id UUID REFERENCES analyses(id),
  short_code TEXT UNIQUE,
  view_count INTEGER DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE shared_reports ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NOT NULL DEFAULT now();

-- Backward-safe metadata defaults
ALTER TABLE skills ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NOT NULL DEFAULT now();

CREATE INDEX IF NOT EXISTS idx_skills_source ON skills (source);
CREATE INDEX IF NOT EXISTS idx_skills_skill_slug ON skills (skill_slug);
CREATE INDEX IF NOT EXISTS idx_skills_weekly_installs ON skills (weekly_installs DESC);
CREATE INDEX IF NOT EXISTS idx_skills_last_seen_at ON skills (last_seen_at DESC);
CREATE UNIQUE INDEX IF NOT EXISTS idx_skills_canonical
ON skills (source, owner, repo, skill_slug);

CREATE INDEX IF NOT EXISTS idx_analyses_github_url ON analyses (github_url);
CREATE INDEX IF NOT EXISTS idx_analyses_cache_until ON analyses (cache_until);
CREATE INDEX IF NOT EXISTS idx_analyses_content_hash ON analyses (content_hash);
CREATE INDEX IF NOT EXISTS idx_shared_reports_short_code ON shared_reports (short_code);
