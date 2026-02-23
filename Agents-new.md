# AGENTS.md

Guidelines for AI agents working on the SkillLens project.

------------------------------------------------------------------------

## Project Overview

**SkillLens** is an AI Skill Security and Intelligence Platform that
analyzes AI agent skills before installation. It provides security
scanning, quality assessment, dependency analysis, and interactive
behavior simulation without executing untrusted code.

-   Name: SkillLens\
-   Repository: yourusername/skilllens\
-   License: MIT\
-   Status: Active Development (MVP Phase)

------------------------------------------------------------------------

## Architecture Note (Enterprise Mode)

SkillLens uses a precomputed analysis pipeline for catalog skills.

Skills discovered from skills.sh are:

1.  Ingested into the `skills` table\
2.  Enriched with GitHub artifacts\
3.  Analyzed asynchronously\
4.  Served from precomputed results

This ensures:

-   low latency UI\
-   predictable LLM cost\
-   enterprise scalability

**Try Skill remains on-demand** and runs only when the user explicitly
requests a simulation.

------------------------------------------------------------------------

## Repository Structure

    skilllens/
    ├── server/
    │   ├── api/
    │   │   ├── main.py
    │   │   └── routes/
    │   │       ├── analyze.py
    │   │       ├── simulate.py
    │   │       ├── skills.py
    │   │       └── health.py
    │   ├── analyzers/
    │   │   ├── security.py
    │   │   ├── quality.py
    │   │   ├── behavior.py
    │   │   └── dependencies.py
    │   ├── fetchers/
    │   │   ├── skills_sh.py
    │   │   ├── github.py
    │   │   ├── anthropic.py
    │   │   └── vercel.py
    │   ├── simulators/
    │   │   ├── input_generator.py
    │   │   └── execution_simulator.py
    │   ├── workers/
    │   │   ├── job_runner.py
    │   │   └── scheduler.py
    │   ├── core/
    │   │   ├── orchestrator.py
    │   │   ├── cache.py
    │   │   └── db.py
    │   └── requirements.txt
    │
    ├── client/
    │   ├── src/
    │   │   ├── components/
    │   │   ├── pages/
    │   │   ├── lib/
    │   │   ├── types/
    │   │   ├── App.tsx
    │   │   └── main.tsx
    │   └── package.json
    │
    ├── database/
    │   └── schema.sql
    │
    ├── docs/
    │   ├── AGENTS.md
    │   ├── SUMMARY.md
    │   └── SECURITY_EXAMPLE.md
    │
    ├── README.md
    └── LICENSE

------------------------------------------------------------------------

## Data Pipeline (Enterprise)

### Stage 1: Discovery (skills.sh)

Extract and store in `skills`:

-   owner, repo, skill_slug\
-   page_url, repository_url, install_command\
-   rendered markdown and raw_html\
-   weekly_installs, first_seen_date\
-   scraped_at, last_seen_at

------------------------------------------------------------------------

### Stage 2: Repository Enrichment

Using `repository_url`, fetch:

-   raw SKILL.md\
-   scripts in skill folder\
-   dependency manifests\
-   optional repo metadata

Stored in:

-   `repo_sources`\
-   `skill_artifacts`

------------------------------------------------------------------------

### Stage 3: Precomputed Analysis

Each artifact version produces:

-   security findings\
-   quality assessment\
-   behavior profile\
-   dependency map\
-   overall score and trust badge

Stored in: `skill_analyses`

------------------------------------------------------------------------

### Stage 4: Serving

-   Catalog pages use precomputed results\
-   Try Skill runs on-demand simulation

------------------------------------------------------------------------

## Core Features

### Multi-Source Skill Analysis

Supported sources:

-   Catalog skills from skills.sh (precomputed)\
-   Ad hoc sources via API (GitHub URL, upload)

------------------------------------------------------------------------

### Security Analysis (Hybrid)

Deterministic scan always runs.

Categories:

-   code execution\
-   command execution\
-   file operations\
-   network access\
-   credentials\
-   database access

Selective LLM validation:

-   runs only for HIGH and CRITICAL findings\
-   reduces false positives\
-   generates exploit explanation

Risk scoring:

    CRITICAL: 100
    HIGH:     25
    MEDIUM:   5
    LOW:      1

Trust badges:

-   0 to 4: Verified Safe\
-   5 to 19: Generally Safe\
-   20 to 49: Review Recommended\
-   50 to 99: Use With Caution\
-   100 plus: Not Recommended

------------------------------------------------------------------------

### Quality Assessment

Deterministic metrics:

-   completeness\
-   examples\
-   structure\
-   maintenance signals

LLM grading:

-   grade A plus to F\
-   concise improvement suggestions

------------------------------------------------------------------------

### Behavior Detection

LLM produces structured JSON with evidence:

-   category\
-   expected inputs and outputs\
-   execution steps\
-   side effects

------------------------------------------------------------------------

### Dependency Analysis

Deterministic extraction first:

-   Python and NPM packages\
-   external APIs\
-   cloud services\
-   databases\
-   system tools

Optional LLM grouping for refinement.

------------------------------------------------------------------------

### Try Skill Preview (Key Differentiator)

Input form generation:

-   auto-detect parameters\
-   return JSON schema for UI

Execution simulation:

-   LLM step-by-step preview\
-   predicts side effects\
-   surfaces security warnings\
-   **no code execution**

------------------------------------------------------------------------

## API Endpoints

### POST /analyze

Ad hoc analysis for non catalog sources.

### POST /simulate

On-demand Try Skill preview.

### GET /skills

Returns catalog with latest valid analysis.

### GET /health

Health check endpoint.

------------------------------------------------------------------------

## Database Architecture (Option B)

SkillLens uses a layered model.

### skills

Discovery layer from skills.sh.

### repo_sources

One row per repository.

### skill_artifacts

Versioned GitHub content per skill.

### skill_analyses

Computed results per artifact version.

### analysis_jobs

Durable background job tracking with retries.

------------------------------------------------------------------------

## Freshness Strategy

Re-analysis triggers when:

-   artifact_hash changes\
-   parse_version changes\
-   analysis_version changes\
-   weekly refresh window expires

Try Skill is always on-demand.

------------------------------------------------------------------------

## LLM Usage Policy

-   Security: deterministic first, LLM validate only high severity\
-   Quality: deterministic plus LLM grading\
-   Behavior: LLM structured output with evidence\
-   Dependencies: deterministic first, LLM optional\
-   Try Skill: always on-demand

Target cost:

-   analysis: \~0.003 USD\
-   simulation: \~0.006 USD

------------------------------------------------------------------------

## Environment Variables

### Server

    SUPABASE_URL=xxx
    SUPABASE_KEY=xxx
    ANTHROPIC_API_KEY=xxx
    GITHUB_TOKEN=xxx

### Client

    VITE_API_URL=http://localhost:8000

------------------------------------------------------------------------

## Git Workflow

Branch naming:

-   feature/description\
-   fix/description\
-   docs/description

Commit style:

-   feat: add security pattern detection\
-   fix: handle rate limiting\
-   docs: update API documentation

PR checklist:

-   tests pass\
-   lint passes\
-   no keys committed\
-   docs updated

------------------------------------------------------------------------

*Last Updated: Enterprise Architecture Revision*
