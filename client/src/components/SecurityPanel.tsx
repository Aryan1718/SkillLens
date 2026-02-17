import { formatJson } from '../lib/utils'

interface SecurityPanelProps {
  data: Record<string, unknown>
}

export function SecurityPanel({ data }: SecurityPanelProps) {
  return (
    <section>
      <h4>Security</h4>
      <pre>{formatJson(data)}</pre>
    </section>
  )
}
