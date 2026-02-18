import { useEffect, useMemo, useState } from 'react'
import { Pagination } from '../components/skills/Pagination'
import { SearchBar } from '../components/skills/SearchBar'
import { SkillCard } from '../components/skills/SkillCard'
import { SkillsFilters } from '../components/skills/SkillsFilters'
import { listSkills } from '../lib/skillsData'
import type { SkillListResponse, SkillSort } from '../types'

const PAGE_SIZE = 24

function parseInstallRange(value: string): { min?: number; max?: number } {
  if (value === '0-999') return { min: 0, max: 999 }
  if (value === '1000-9999') return { min: 1000, max: 9999 }
  if (value === '10000-99999') return { min: 10000, max: 99999 }
  if (value === '100000+') return { min: 100000 }
  return {}
}

export function SkillsDirectoryPage() {
  const [search, setSearch] = useState('')
  const [owner, setOwner] = useState('')
  const [installsRange, setInstallsRange] = useState('all')
  const [hasSkillMd, setHasSkillMd] = useState(false)
  const [sort, setSort] = useState<SkillSort>('weekly_desc')
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [data, setData] = useState<SkillListResponse>({
    items: [],
    total: 0,
    page: 1,
    pageSize: PAGE_SIZE,
    totalPages: 1,
    owners: [],
  })

  const installBounds = useMemo(() => parseInstallRange(installsRange), [installsRange])

  useEffect(() => {
    setLoading(true)
    setError('')

    listSkills({
      page,
      pageSize: PAGE_SIZE,
      search,
      owner,
      minInstalls: installBounds.min,
      maxInstalls: installBounds.max,
      hasSkillMd,
      sort,
    })
      .then((result) => setData(result))
      .catch(() => setError('Failed to load skills.'))
      .finally(() => setLoading(false))
  }, [page, search, owner, installBounds.min, installBounds.max, hasSkillMd, sort])

  useEffect(() => {
    setPage(1)
  }, [search, owner, installsRange, hasSkillMd, sort])

  return (
    <div className="page-stack">
      <section className="section-block compact">
        <h1>Skills Directory</h1>
        <p>Search and filter across skill_slug, owner/repo, and extracted markdown keywords.</p>
      </section>

      <section className="section-block compact">
        <SearchBar value={search} onChange={setSearch} />
        <SkillsFilters
          owners={data.owners}
          owner={owner}
          onOwnerChange={setOwner}
          installsRange={installsRange}
          onInstallsRangeChange={setInstallsRange}
          hasSkillMd={hasSkillMd}
          onHasSkillMdChange={setHasSkillMd}
          sort={sort}
          onSortChange={setSort}
        />
      </section>

      {loading ? <p>Loading skills...</p> : null}
      {error ? <p role="alert">{error}</p> : null}

      {!loading && !error ? (
        <section className="section-block compact">
          <div className="section-head">
            <h2>{data.total.toLocaleString()} skills found</h2>
          </div>

          {data.items.length === 0 ? (
            <div className="empty-state">
              <p>{data.emptyReason || 'No results for the current filters.'}</p>
              {data.emptyReason ? <p>Run scraper first to create `data/skills/*.json` records.</p> : null}
            </div>
          ) : (
            <div className="skills-grid">
              {data.items.map((skill) => (
                <SkillCard key={skill.id} skill={skill} />
              ))}
            </div>
          )}

          <Pagination page={data.page} totalPages={data.totalPages} onPageChange={setPage} />
        </section>
      ) : null}
    </div>
  )
}
