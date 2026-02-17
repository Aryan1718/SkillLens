# AGENTS.md

Guidelines for AI agents working on the SkillLens project.

## Project Overview

**SkillLens** is an AI Skill Security & Intelligence Platform that analyzes AI agent skills before installation. It provides security scanning, quality assessment, dependency analysis, and interactive behavior simulation - all without executing untrusted code.

- **Name**: SkillLens
- **Repository**: [yourusername/skilllens](https://github.com/yourusername/skilllens)
- **License**: MIT
- **Status**: Active Development (MVP Phase)

## Repository Structure

```
skilllens/
├── backend/
│   ├── api/
│   │   ├── main.py              # FastAPI app entry point
│   │   └── routes/
│   │       ├── analyze.py       # POST /analyze endpoint
│   │       ├── simulate.py      # POST /simulate endpoint
│   │       ├── skills.py        # GET /skills endpoint
│   │       └── health.py        # GET /health endpoint
│   ├── analyzers/
│   │   ├── security.py          # Security pattern detection & LLM validation
│   │   ├── quality.py           # Documentation quality assessment
│   │   ├── behavior.py          # Skill category & behavior detection
│   │   └── dependencies.py      # Package & API dependency analysis
│   ├── fetchers/
│   │   ├── github.py            # Fetch SKILL.md from GitHub repos
│   │   ├── anthropic.py         # Fetch Anthropic official skills
│   │   └── vercel.py            # Fetch Vercel AI SDK skills
│   ├── simulators/
│   │   ├── input_generator.py   # Auto-generate input forms from code
│   │   └── execution_simulator.py # LLM-powered execution preview
│   ├── core/
│   │   ├── orchestrator.py      # Coordinate all analysis components
│   │   └── cache.py             # Supabase caching layer
│   └── requirements.txt
│
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── ui/              # shadcn/ui components
│   │   │   ├── AnalyzeForm.tsx  # Main skill input form
│   │   │   ├── SourceSelector.tsx # GitHub/Official/Upload tabs
│   │   │   ├── ReportCard.tsx   # Overall analysis results
│   │   │   ├── SecurityPanel.tsx # Security findings display
│   │   │   ├── QualityPanel.tsx  # Quality metrics display
│   │   │   ├── BehaviorPanel.tsx # Behavior simulation results
│   │   │   ├── DependencyPanel.tsx # Dependency list
│   │   │   └── TrySkillModal.tsx # Interactive simulation modal
│   │   ├── pages/
│   │   │   ├── Home.tsx         # Landing page + analyze form
│   │   │   └── Report.tsx       # Full analysis results page
│   │   ├── lib/
│   │   │   ├── api.ts           # FastAPI client
│   │   │   └── utils.ts         # Helper functions
│   │   ├── types/
│   │   │   └── index.ts         # TypeScript type definitions
│   │   ├── App.tsx
│   │   └── main.tsx
│   └── package.json
│
├── database/
│   └── schema.sql               # Supabase database schema
│
├── docs/
│   ├── AGENTS.md                # This file
│   ├── SUMMARY.md               # Quick reference guide
│   └── SECURITY_EXAMPLE.md      # Security analysis walkthrough
│
├── README.md
└── LICENSE
```

## Build / Lint / Test Commands

### Backend

```bash
# Install dependencies
cd backend
pip install -r requirements.txt

# Run development server
uvicorn api.main:app --reload --port 8000

# Run tests
pytest tests/ -v

# Lint & format
black .
flake8 .
mypy .
```

### Frontend

```bash
# Install dependencies
cd frontend
npm install

# Run development server
npm run dev

# Build for production
npm run build

# Lint
npm run lint

# Type check
npm run type-check
```

## Core Features

### 1. Multi-Source Skill Analysis

Fetch and analyze skills from:
- **GitHub URLs**: Any public repository with SKILL.md
- **Official Catalogs**: Pre-indexed Anthropic & Vercel skills
- **Direct Upload**: Local SKILL.md files

### 2. Security Analysis (Hybrid Approach)

**Pattern Matching** (Fast, Free)
- Scans for 50+ dangerous patterns across 6 categories
- Categories: Code execution, command execution, file operations, network access, credentials, database
- Initial severity: CRITICAL, HIGH, MEDIUM, LOW

**LLM Validation** (Smart, Selective)
- Only for HIGH/CRITICAL findings
- Validates context and actual risk
- Generates exploit scenarios
- Provides fix recommendations
- Cost: ~$0.0015 per validation

**Risk Scoring**
```python
Weights:
CRITICAL: 100 points  # One critical = instant fail
HIGH:     25 points
MEDIUM:   5 points
LOW:      1 point

Trust Badges:
0-4:   ✅ Verified Safe
5-19:  ✓ Generally Safe  
20-49: ⚠️ Review Recommended
50-99: ⚠️ Use With Caution
100+:  ❌ Not Recommended
```

### 3. Quality Assessment

Analyzes:
- Documentation completeness (200+ checks)
- Example quality and diversity
- Structure and organization
- Maintenance health (GitHub activity)
- Overall grade: A+ to F

### 4. Behavior Simulation

Detects:
- Skill category (8 types: file processing, API integration, etc.)
- Expected inputs/outputs
- Execution steps
- "What it does" summary

### 5. Dependency Analysis

Identifies:
- Python/NPM packages
- External APIs (OpenAI, AWS, Stripe, etc.)
- Cloud services
- System tools
- Databases
- Complexity scoring

### 6. Try Skill Preview (KEY DIFFERENTIATOR)

**Input Form Generation**
- Auto-detects parameters from code
- Generates smart UI forms
- Type inference (file, text, URL, number)

**Execution Simulation**
- LLM-powered step-by-step preview
- Shows commands/APIs that would be called
- Predicts files created/modified
- Security warnings in context
- **NO actual code execution** (safe!)
- Cost: ~$0.006 per simulation

## API Endpoints

### POST /analyze

Analyze a skill from any source.

**Request:**
```json
{
  "source_type": "github" | "official" | "upload",
  "github_url": "https://github.com/user/skill",
  "official_skill_name": "skill-name",
  "skill_content": "---\nname: skill\n..."
}
```

**Response:**
```json
{
  "skill_name": "pdf-converter",
  "overall_score": 87.5,
  "trust_badge": "✓ Generally Safe",
  "security": { /* findings, risk level */ },
  "quality": { /* grade, metrics */ },
  "behavior": { /* category, steps */ },
  "dependencies": { /* packages, APIs */ },
  "analyzed_at": "2026-02-16T10:30:00Z"
}
```

### POST /simulate

Generate interactive skill preview.

**Request:**
```json
{
  "skill_content": "...",
  "user_inputs": {
    "input_file": "document.pdf",
    "output_format": "txt"
  }
}
```

**Response:**
```json
{
  "execution_steps": [...],
  "expected_outputs": {
    "files_created": ["document.txt"],
    "api_calls": []
  },
  "security_warnings": []
}
```

### GET /skills

List official pre-analyzed skills.

### GET /health

Health check endpoint.

## Database Schema

```sql
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
  cache_until TIMESTAMP,
  INDEX idx_github_url (github_url)
);

-- Shareable report links
CREATE TABLE shared_reports (
  id UUID PRIMARY KEY,
  analysis_id UUID REFERENCES analyses(id),
  short_code TEXT UNIQUE,
  view_count INTEGER DEFAULT 0
);
```

## Caching Strategy

- **Official Skills**: Weekly re-analysis
- **GitHub Skills**: 24-hour cache
- **Uploaded Files**: No caching (privacy)

## Security Patterns

### Critical (Instant Fail)
- `eval()`, `exec()`, `compile()` - Code execution
- `os.system()` - Shell execution
- `subprocess.run(..., shell=True)` - Command injection

### High (Serious Risk)
- `subprocess.call/Popen` - Command execution
- `shutil.rmtree()` - Recursive delete
- SQL injection patterns
- `socket.socket()` - Raw network

### Medium (Review Needed)
- `requests.get/post` - HTTP (SSRF risk)
- `open(..., 'w')` - File writes
- Hardcoded credentials

### Low (Minor Concern)
- `open(..., 'r')` - File reads
- Environment variables

## LLM Usage

### When to Use Claude API

**Security Analysis:**
- Only HIGH/CRITICAL findings
- Cost: ~$0.0015 per validation

**Try Skill Simulation:**
- Execution preview generation
- Cost: ~$0.006 per simulation

**Total Cost Target:**
- Per analysis: ~$0.003
- Per simulation: ~$0.006
- Monthly (1000/day): ~$150

## Development Guidelines

### Backend (Python)

**Style:**
- Black formatter (88 chars)
- Type hints required
- Async/await for I/O
- Docstrings for public functions

**Example:**
```python
async def analyze_security(
    skill_content: str,
    use_llm: bool = True
) -> SecurityAnalysisResult:
    """Analyze skill for security vulnerabilities."""
    # Implementation
```

### Frontend (TypeScript)

**Style:**
- Functional components
- TypeScript strict mode
- Props interfaces required

**Example:**
```tsx
interface SecurityPanelProps {
  findings: SecurityFinding[];
  riskLevel: RiskLevel;
}

export function SecurityPanel({ 
  findings, 
  riskLevel 
}: SecurityPanelProps) {
  // Implementation
}
```

## Git Workflow

### Branch Naming
- `feature/description` - New features
- `fix/description` - Bug fixes
- `docs/description` - Documentation

### Commit Messages

Follow [Conventional Commits](https://www.conventionalcommits.org/):

- `feat: add security pattern detection`
- `fix: handle GitHub rate limiting`
- `docs: update API documentation`

### PR Checklist
- [ ] Tests pass
- [ ] Linting passes
- [ ] No API keys in code
- [ ] Documentation updated

## Environment Variables

### Backend
```bash
SUPABASE_URL=xxx
SUPABASE_KEY=xxx
ANTHROPIC_API_KEY=sk-ant-xxx
GITHUB_TOKEN=ghp_xxx  # Optional
```

### Frontend
```bash
VITE_API_URL=http://localhost:8000
VITE_SUPABASE_URL=xxx
VITE_SUPABASE_ANON_KEY=xxx
```

## Deployment

### Backend (Railway)
```bash
railway login
railway init
railway up
railway variables set ANTHROPIC_API_KEY=xxx
```

### Frontend (Vercel)
```bash
cd frontend
vercel --prod
```

## MVP Launch Checklist

### Pre-Launch
- [ ] Backend deployed
- [ ] Frontend deployed
- [ ] Database configured
- [ ] 30 official skills pre-analyzed
- [ ] Error tracking enabled

### Launch Day
- [ ] End-to-end testing
- [ ] Post on Product Hunt
- [ ] Share on Twitter/LinkedIn

### Post-Launch
- [ ] Monitor errors
- [ ] Fix critical bugs <24h
- [ ] Gather feedback

## Roadmap

### v1.1 (Month 2)
- User accounts
- Save history
- Compare skills
- Dark mode

### v1.2 (Month 3)
- Browser extension
- Public API
- Community ratings

### v2.0 (Month 6)
- Sandboxed execution
- Private repos
- Enterprise features

## Support

- **Issues**: GitHub Issues
- **Docs**: `/docs` directory
- **Security**: security@skilllens.io

## License

MIT - See LICENSE file

---

*Last Updated: 2026-02-16*
