-- Expand skills table to capture full skills.sh page content and metadata.
-- Safe to run on existing deployments.

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

-- Backfill compatibility aliases so old code paths still work.
UPDATE skills
SET skill_md_rendered = skill_content
WHERE skill_md_rendered IS NULL;

-- Keep name in sync with skill_slug where possible for existing constraints.
UPDATE skills
SET name = COALESCE(skill_slug, name)
WHERE name IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_skills_source ON skills (source);
CREATE INDEX IF NOT EXISTS idx_skills_skill_slug ON skills (skill_slug);
CREATE INDEX IF NOT EXISTS idx_skills_weekly_installs ON skills (weekly_installs DESC);
CREATE INDEX IF NOT EXISTS idx_skills_last_seen_at ON skills (last_seen_at DESC);

-- Canonical uniqueness for sourced skills pages.
CREATE UNIQUE INDEX IF NOT EXISTS idx_skills_canonical
ON skills (source, owner, repo, skill_slug);
