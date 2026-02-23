interface ReportCardProps {
  report: {
    skill_name: string
    overall_score: number | null
    trust_badge: string | null
    analyzed_at: string | null
  }
}

export function ReportCard({ report }: ReportCardProps) {
  return (
    <div style={{ border: '1px solid #ddd', padding: 16, borderRadius: 8 }}>
      <h3 style={{ marginTop: 0 }}>{report.skill_name}</h3>
      <p>Overall score: {report.overall_score ?? '-'}</p>
      <p>Trust badge: {report.trust_badge ?? '-'}</p>
      <p>Analyzed at: {report.analyzed_at ?? '-'}</p>
    </div>
  )
}
