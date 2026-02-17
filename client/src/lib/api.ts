import type {
  AnalyzeRequest,
  AnalyzeResponse,
  SimulateRequest,
  SimulateResponse,
} from '../types'

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000'

export async function analyzeSkill(payload: AnalyzeRequest): Promise<AnalyzeResponse> {
  const res = await fetch(`${API_BASE}/analyze`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!res.ok) {
    throw new Error(`Analyze failed: ${res.status}`)
  }
  return res.json()
}

export async function simulateSkill(payload: SimulateRequest): Promise<SimulateResponse> {
  const res = await fetch(`${API_BASE}/simulate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!res.ok) {
    throw new Error(`Simulate failed: ${res.status}`)
  }
  return res.json()
}
