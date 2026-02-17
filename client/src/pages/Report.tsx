import type { AnalyzeResponse } from '../types'
import { ReportCard } from '../components/ReportCard'
import { SecurityPanel } from '../components/SecurityPanel'
import { QualityPanel } from '../components/QualityPanel'
import { BehaviorPanel } from '../components/BehaviorPanel'
import { DependencyPanel } from '../components/DependencyPanel'
import { TrySkillModal } from '../components/TrySkillModal'

interface ReportProps {
  report: AnalyzeResponse
  onBack: () => void
}

export function Report({ report, onBack }: ReportProps) {
  return (
    <div>
      <button onClick={onBack}>Back</button>
      <h2>Analysis Report</h2>
      <ReportCard report={report} />
      <SecurityPanel data={report.security} />
      <QualityPanel data={report.quality} />
      <BehaviorPanel data={report.behavior} />
      <DependencyPanel data={report.dependencies} />
      <TrySkillModal skillContent={String(report.skill_name)} />
    </div>
  )
}
