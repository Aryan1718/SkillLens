import { useState } from 'react'
import { Home } from './pages/Home'
import { Report } from './pages/Report'
import type { AnalyzeResponse } from './types'

export function App() {
  const [report, setReport] = useState<AnalyzeResponse | null>(null)

  return (
    <main style={{ maxWidth: 900, margin: '0 auto', padding: 16 }}>
      {report ? (
        <Report report={report} onBack={() => setReport(null)} />
      ) : (
        <Home onAnalyzed={setReport} />
      )}
    </main>
  )
}
