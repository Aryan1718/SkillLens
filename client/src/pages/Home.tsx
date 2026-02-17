import type { AnalyzeResponse } from '../types'
import { AnalyzeForm } from '../components/AnalyzeForm'

interface HomeProps {
  onAnalyzed: (report: AnalyzeResponse) => void
}

export function Home({ onAnalyzed }: HomeProps) {
  return (
    <div>
      <h2>SkillLens</h2>
      <p>Analyze AI skills from GitHub, official catalogs, or uploaded content.</p>
      <AnalyzeForm onAnalyzed={onAnalyzed} />
    </div>
  )
}
