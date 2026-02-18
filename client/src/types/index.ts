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
  source: string
  owner: string
  repo: string
  skill_slug: string
  page_url: string
  repository_url: string
  install_command: string
  weekly_installs: number
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
