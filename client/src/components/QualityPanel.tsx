import { formatJson } from '../lib/utils'

interface QualityPanelProps {
  data: Record<string, unknown>
}

export function QualityPanel({ data }: QualityPanelProps) {
  return (
    <section>
      <h4>Quality</h4>
      <pre>{formatJson(data)}</pre>
    </section>
  )
}
