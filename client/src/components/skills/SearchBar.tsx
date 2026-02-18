interface SearchBarProps {
  value: string
  onChange: (value: string) => void
}

export function SearchBar({ value, onChange }: SearchBarProps) {
  return (
    <label className="field">
      <span>Search skills</span>
      <input
        type="search"
        placeholder="skill slug, owner/repo, or keywords"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        aria-label="Search skills"
      />
    </label>
  )
}
