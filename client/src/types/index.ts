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
