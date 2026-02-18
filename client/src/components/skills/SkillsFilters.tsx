interface SkillsFiltersProps {
  owners: string[]
  owner: string
  onOwnerChange: (value: string) => void
  installsRange: string
  onInstallsRangeChange: (value: string) => void
  hasSkillMd: boolean
  onHasSkillMdChange: (value: boolean) => void
  sort: 'weekly_desc' | 'az' | 'recent'
  onSortChange: (value: 'weekly_desc' | 'az' | 'recent') => void
}

export function SkillsFilters({
  owners,
  owner,
  onOwnerChange,
  installsRange,
  onInstallsRangeChange,
  hasSkillMd,
  onHasSkillMdChange,
  sort,
  onSortChange,
}: SkillsFiltersProps) {
  return (
    <section className="filters-shell" aria-label="Skill filters">
      <label className="field">
        <span>Owner</span>
        <select value={owner} onChange={(event) => onOwnerChange(event.target.value)}>
          <option value="">All owners</option>
          {owners.map((ownerOption) => (
            <option key={ownerOption} value={ownerOption}>
              {ownerOption}
            </option>
          ))}
        </select>
      </label>

      <label className="field">
        <span>Installs range</span>
        <select value={installsRange} onChange={(event) => onInstallsRangeChange(event.target.value)}>
          <option value="all">Any</option>
          <option value="0-999">0 - 999</option>
          <option value="1000-9999">1K - 9.9K</option>
          <option value="10000-99999">10K - 99.9K</option>
          <option value="100000+">100K+</option>
        </select>
      </label>

      <label className="field">
        <span>Sort</span>
        <select value={sort} onChange={(event) => onSortChange(event.target.value as 'weekly_desc' | 'az' | 'recent')}>
          <option value="weekly_desc">Weekly installs</option>
          <option value="az">A - Z</option>
          <option value="recent">Recently updated</option>
        </select>
      </label>

      <label className="toggle">
        <input
          type="checkbox"
          checked={hasSkillMd}
          onChange={(event) => onHasSkillMdChange(event.target.checked)}
        />
        <span>Has SKILL.md</span>
      </label>
    </section>
  )
}
