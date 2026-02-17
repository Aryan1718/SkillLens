-- Official skills catalog
CREATE TABLE skills (
  id UUID PRIMARY KEY,
  name TEXT NOT NULL,
  source TEXT NOT NULL,
  skill_content TEXT NOT NULL,
  last_fetched TIMESTAMP,
  UNIQUE(source, name)
);

-- Cached analysis results
CREATE TABLE analyses (
  id UUID PRIMARY KEY,
  github_url TEXT,
  overall_score DECIMAL(5,2),
  trust_badge TEXT,
  security_data JSONB,
  quality_data JSONB,
  behavior_data JSONB,
  dependency_data JSONB,
  cache_until TIMESTAMP
);

CREATE INDEX idx_github_url ON analyses (github_url);

-- Shareable report links
CREATE TABLE shared_reports (
  id UUID PRIMARY KEY,
  analysis_id UUID REFERENCES analyses(id),
  short_code TEXT UNIQUE,
  view_count INTEGER DEFAULT 0
);
