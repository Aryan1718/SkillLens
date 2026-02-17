import { useState } from 'react'
import type { AnalyzeRequest, AnalyzeResponse, SourceType } from '../types'
import { analyzeSkill } from '../lib/api'
import { SourceSelector } from './SourceSelector'

interface AnalyzeFormProps {
  onAnalyzed: (result: AnalyzeResponse) => void
}

export function AnalyzeForm({ onAnalyzed }: AnalyzeFormProps) {
  const [sourceType, setSourceType] = useState<SourceType>('github')
  const [githubUrl, setGithubUrl] = useState('')
  const [officialSkillName, setOfficialSkillName] = useState('')
  const [skillContent, setSkillContent] = useState('')
  const [loading, setLoading] = useState(false)

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault()
    setLoading(true)
    try {
      const payload: AnalyzeRequest = {
        source_type: sourceType,
        github_url: githubUrl || undefined,
        official_skill_name: officialSkillName || undefined,
        skill_content: skillContent || undefined,
      }
      const result = await analyzeSkill(payload)
      onAnalyzed(result)
    } finally {
      setLoading(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} style={{ border: '1px solid #ddd', padding: 16, borderRadius: 8 }}>
      <SourceSelector value={sourceType} onChange={setSourceType} />
      <div style={{ display: 'grid', gap: 8 }}>
        <input
          placeholder="GitHub URL"
          value={githubUrl}
          onChange={(e) => setGithubUrl(e.target.value)}
        />
        <input
          placeholder="Official skill name"
          value={officialSkillName}
          onChange={(e) => setOfficialSkillName(e.target.value)}
        />
        <textarea
          placeholder="Skill content"
          value={skillContent}
          onChange={(e) => setSkillContent(e.target.value)}
          rows={6}
        />
      </div>
      <button type="submit" disabled={loading} style={{ marginTop: 12 }}>
        {loading ? 'Analyzing...' : 'Analyze'}
      </button>
    </form>
  )
}
