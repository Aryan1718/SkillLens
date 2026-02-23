import type {
  AnalyzeRequest,
  AnalyzeResponse,
  SkillDetail,
  SkillSummary,
  SimulateRequest,
  SimulateResponse,
} from '../types'

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000'

async function readJsonOrThrow<T>(res: Response, label: string): Promise<T> {
  if (!res.ok) {
    const body = await res.text().catch(() => '')
    throw new Error(`${label} failed: ${res.status}${body ? ` - ${body}` : ''}`)
  }
  return res.json() as Promise<T>
}

export async function analyzeSkill(payload: AnalyzeRequest): Promise<AnalyzeResponse> {
  const res = await fetch(`${API_BASE}/analyze`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  return readJsonOrThrow<AnalyzeResponse>(res, 'Analyze')
}

export async function simulateSkill(payload: SimulateRequest): Promise<SimulateResponse> {
  const res = await fetch(`${API_BASE}/simulate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  return readJsonOrThrow<SimulateResponse>(res, 'Simulate')
}

function normalizeSummary(raw: Partial<SkillSummary> & Record<string, unknown>): SkillSummary {
  const owner = String(raw.owner || '')
  const repo = String(raw.repo || '')
  const slug = String(raw.skill_slug || raw.name || '')
  const id = String(raw.id || `${owner}-${repo}-${slug}`)
  return {
    id,
    name: raw.name ? String(raw.name) : slug,
    source: String(raw.source || ''),
    owner,
    repo,
    skill_slug: slug,
    page_url: String(raw.page_url || ''),
    repository_url: String(raw.repository_url || ''),
    install_command: String(raw.install_command || ''),
    weekly_installs: Number(raw.weekly_installs || 0),
    trust_badge: raw.trust_badge ? String(raw.trust_badge) : null,
    overall_score:
      typeof raw.overall_score === 'number' ? raw.overall_score : raw.overall_score ? Number(raw.overall_score) : null,
    first_seen_date: String(raw.first_seen_date || ''),
    installed_on: (raw.installed_on as SkillSummary['installed_on']) || {},
    scraped_at: String(raw.scraped_at || ''),
    last_seen_at: String(raw.last_seen_at || ''),
    has_skill_md: Boolean(raw.has_skill_md),
    search_blob: String(raw.search_blob || ''),
    detail_id: String(raw.detail_id || id),
  }
}

export async function listSkills(): Promise<SkillSummary[]> {
  const res = await fetch(`${API_BASE}/skills`)
  const data = await readJsonOrThrow<Array<Partial<SkillSummary> & Record<string, unknown>>>(res, 'List skills')
  return data.map(normalizeSummary)
}

export async function getSkill(skillId: string): Promise<SkillDetail> {
  const res = await fetch(`${API_BASE}/skills/${encodeURIComponent(skillId)}`)
  return readJsonOrThrow<SkillDetail>(res, 'Get skill')
}
