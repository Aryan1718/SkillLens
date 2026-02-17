import { useState } from 'react'
import { simulateSkill } from '../lib/api'
import type { SimulateResponse } from '../types'

interface TrySkillModalProps {
  skillContent: string
}

export function TrySkillModal({ skillContent }: TrySkillModalProps) {
  const [open, setOpen] = useState(false)
  const [result, setResult] = useState<SimulateResponse | null>(null)
  const [loading, setLoading] = useState(false)

  async function runSimulation() {
    setLoading(true)
    try {
      const data = await simulateSkill({
        skill_content: skillContent || '# sample skill',
        user_inputs: { input_file: 'document.pdf', output_format: 'txt' },
      })
      setResult(data)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div>
      <button onClick={() => setOpen((v) => !v)}>{open ? 'Close Try Skill' : 'Try Skill'}</button>
      {open && (
        <div style={{ border: '1px solid #ddd', marginTop: 10, padding: 12 }}>
          <button onClick={runSimulation} disabled={loading}>
            {loading ? 'Simulating...' : 'Run Simulation'}
          </button>
          {result && (
            <pre style={{ whiteSpace: 'pre-wrap' }}>{JSON.stringify(result, null, 2)}</pre>
          )}
        </div>
      )}
    </div>
  )
}
