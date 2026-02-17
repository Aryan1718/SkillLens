import type { SourceType } from '../types'

interface SourceSelectorProps {
  value: SourceType
  onChange: (value: SourceType) => void
}

const options: SourceType[] = ['github', 'official', 'upload']

export function SourceSelector({ value, onChange }: SourceSelectorProps) {
  return (
    <div style={{ display: 'flex', gap: 8, marginBottom: 12 }}>
      {options.map((option) => (
        <button
          key={option}
          onClick={() => onChange(option)}
          style={{
            padding: '8px 10px',
            border: '1px solid #ccc',
            background: option === value ? '#eee' : '#fff',
            cursor: 'pointer',
          }}
        >
          {option}
        </button>
      ))}
    </div>
  )
}
