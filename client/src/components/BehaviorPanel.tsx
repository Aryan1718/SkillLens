import { formatJson } from '../lib/utils'

interface BehaviorPanelProps {
  data: Record<string, unknown>
}

export function BehaviorPanel({ data }: BehaviorPanelProps) {
  return (
    <section>
      <h4>Behavior</h4>
      <pre>{formatJson(data)}</pre>
    </section>
  )
}
