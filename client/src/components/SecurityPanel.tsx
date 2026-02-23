import { useState } from 'react'
import type { SecurityData, SecurityFinding } from '../types'

interface SecurityPanelProps {
  data: Record<string, unknown> | null
}

export function SecurityPanel({ data }: SecurityPanelProps) {
  const [expanded, setExpanded] = useState(false)
  const security = (data || {}) as SecurityData
  const findings = Array.isArray(security.findings) ? security.findings : []
  const trustBadge = security.trust_badge || 'Unknown'
  const riskScore = typeof security.risk_score === 'number' ? security.risk_score : null
  const summary = security.user_explanation?.summary || security.security_summary || 'Security analysis unavailable.'

  const counts = findings.reduce(
    (acc, item) => {
      const level = item.severity
      if (level in acc) {
        acc[level as keyof typeof acc] += 1
      }
      return acc
    },
    { CRITICAL: 0, HIGH: 0, MEDIUM: 0, LOW: 0 },
  )

  const topFindings: SecurityFinding[] = [...findings]
    .sort((a, b) => severityRank(b.severity) - severityRank(a.severity))
    .slice(0, 5)

  const actions = Array.isArray(security.user_explanation?.recommended_actions)
    ? security.user_explanation?.recommended_actions || []
    : []
  const safetyChecks = Array.isArray(security.user_explanation?.safety_checks)
    ? security.user_explanation?.safety_checks || []
    : []
  const safetyStatements = Array.isArray(security.user_explanation?.safety_statements)
    ? security.user_explanation?.safety_statements || []
    : []

  return (
    <section>
      <h4>Security</h4>
      <p><strong>Trust:</strong> {trustBadge}</p>
      <p><strong>Risk score:</strong> {riskScore ?? '-'}</p>
      <p>{summary}</p>
      <button type="button" onClick={() => setExpanded((prev) => !prev)}>
        {expanded ? 'Hide security details' : 'View security details'}
      </button>
      {expanded ? (
        <>
          {safetyChecks.length > 0 ? (
            <div>
              <h5 style={{ marginBottom: 8 }}>Safety Checks</h5>
              <ul style={{ margin: 0, paddingLeft: 18 }}>
                {safetyChecks.map((item) => (
                  <li key={item.key}>{item.safe ? item.safe_message : item.risk_message}</li>
                ))}
              </ul>
            </div>
          ) : null}
          {safetyStatements.length > 0 && safetyChecks.length === 0 ? (
            <div>
              <h5 style={{ marginBottom: 8 }}>Safety Checks</h5>
              <ul style={{ margin: 0, paddingLeft: 18 }}>
                {safetyStatements.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </div>
          ) : null}
          <p>
            <strong>Findings:</strong>{' '}
            Critical {counts.CRITICAL} · High {counts.HIGH} · Medium {counts.MEDIUM} · Low {counts.LOW}
          </p>

          {topFindings.length > 0 ? (
            <div>
              <h5 style={{ marginBottom: 8 }}>Top Findings</h5>
              <ul style={{ margin: 0, paddingLeft: 18 }}>
                {topFindings.map((finding) => (
                  <li key={finding.id} style={{ marginBottom: 8 }}>
                    <strong>{finding.severity}</strong> - {finding.title}
                    <div style={{ opacity: 0.85, fontSize: 13 }}>
                      {finding.file_path}
                      {finding.line_start ? `:${finding.line_start}` : ''}
                    </div>
                    <div style={{ opacity: 0.9 }}>{finding.evidence}</div>
                  </li>
                ))}
              </ul>
            </div>
          ) : (
            <p>No findings detected in scanned artifacts.</p>
          )}

          {actions.length > 0 ? (
            <div>
              <h5 style={{ marginBottom: 8 }}>Recommended Actions</h5>
              <ul style={{ margin: 0, paddingLeft: 18 }}>
                {actions.slice(0, 4).map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </div>
          ) : null}
        </>
      ) : null}
    </section>
  )
}

function severityRank(severity: SecurityFinding['severity']): number {
  switch (severity) {
    case 'CRITICAL':
      return 4
    case 'HIGH':
      return 3
    case 'MEDIUM':
      return 2
    default:
      return 1
  }
}
