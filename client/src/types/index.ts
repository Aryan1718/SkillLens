export type SourceType = 'github' | 'official' | 'upload'

export interface AnalyzeRequest {
  source_type: SourceType
  github_url?: string
  official_skill_name?: string
  skill_content?: string
}

export interface AnalyzeResponse {
  skill_name: string
  overall_score: number
  trust_badge: string
  security: Record<string, unknown>
  quality: Record<string, unknown>
  behavior: Record<string, unknown>
  dependencies: Record<string, unknown>
  analyzed_at: string
}

export interface SimulateRequest {
  skill_content: string
  user_inputs: Record<string, unknown>
}

export interface SimulateResponse {
  execution_steps: string[]
  expected_outputs: Record<string, unknown>
  security_warnings: string[]
}

export type InstalledOn = Record<string, number>

export interface SkillSummary {
  id: string
  name?: string | null
  source: string
  owner: string
  repo: string
  skill_slug: string
  page_url: string
  repository_url: string
  install_command: string
  weekly_installs: number
  trust_badge?: string | null
  overall_score?: number | null
  first_seen_date: string
  installed_on: InstalledOn
  scraped_at: string
  last_seen_at: string
  has_skill_md: boolean
  search_blob: string
  detail_id: string
}

export interface SkillRecord {
  id: string
  source: string
  owner: string
  repo: string
  skill_slug: string
  page_url: string
  repository_url: string
  install_command: string
  skill_md_rendered: string
  skill_md_hash: string
  extracted_links: string[]
  weekly_installs: number
  first_seen_date: string
  installed_on: InstalledOn
  parse_version: string
  scraped_at: string
  last_seen_at: string
}

export interface AnalysisSummary {
  overall_score: number | null
  trust_badge: string | null
  security: Record<string, unknown> | null
  quality: Record<string, unknown> | null
  behavior: Record<string, unknown> | null
  dependencies: Record<string, unknown> | null
  analyzed_at: string | null
}

export interface SecurityFinding {
  id: string
  category: string
  severity: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL'
  title: string
  evidence: string
  file_path: string
  line_start: number | null
  line_end: number | null
  confidence: 'low' | 'medium' | 'high'
}

export interface UserSecurityExplanation {
  headline?: string
  summary?: string
  top_concerns?: string[]
  recommended_actions?: string[]
  safety_checks?: Array<{
    key: string
    safe: boolean
    safe_message: string
    risk_message: string
  }>
  safety_statements?: string[]
}

export interface SecurityData {
  findings?: SecurityFinding[]
  validated_findings?: Array<Record<string, unknown>>
  security_summary?: string | null
  user_explanation?: UserSecurityExplanation
  risk_score?: number
  trust_badge?: string
  capabilities?: Record<string, boolean>
  llm_used?: boolean
  llm_model?: string | null
  analyzed_at?: string
}

export interface SkillDetail {
  id: string
  name: string
  owner: string
  repo: string
  skill_slug: string
  page_url: string
  repository_url: string
  install_command: string
  weekly_installs: number
  skill_md_rendered: string
  extracted_links: string[]
  scraped_at: string | null
  last_seen_at: string | null
  analysis: AnalysisSummary
}

export type SkillSort = 'weekly_desc' | 'az' | 'recent'

export interface SkillListQuery {
  page?: number
  pageSize?: number
  search?: string
  owner?: string
  minInstalls?: number
  maxInstalls?: number
  hasSkillMd?: boolean
  sort?: SkillSort
}

export interface SkillListResponse {
  items: SkillSummary[]
  total: number
  page: number
  pageSize: number
  totalPages: number
  owners: string[]
  emptyReason?: string
}
