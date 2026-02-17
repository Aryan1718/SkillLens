import { formatJson } from '../lib/utils'

interface DependencyPanelProps {
  data: Record<string, unknown>
}

export function DependencyPanel({ data }: DependencyPanelProps) {
  return (
    <section>
      <h4>Dependencies</h4>
      <pre>{formatJson(data)}</pre>
    </section>
  )
}
