import { useEffect, useMemo, useState } from 'react'
import { AppLink } from '../lib/router'
import { listSkills } from '../lib/api'
import type { SkillSummary } from '../types'
import { formatInstalls } from '../lib/utils'

export function Home() {
  const [skills, setSkills] = useState<SkillSummary[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [search, setSearch] = useState('')

  useEffect(() => {
    let mounted = true
    setLoading(true)
    listSkills()
      .then((rows) => {
        if (mounted) {
          setSkills(rows)
        }
      })
      .catch((err: Error) => {
        if (mounted) {
          setError(err.message || 'Failed to load skills')
        }
      })
      .finally(() => {
        if (mounted) {
          setLoading(false)
        }
      })
    return () => {
      mounted = false
    }
  }, [])

  const filtered = useMemo(() => {
    const needle = search.trim().toLowerCase()
    if (!needle) {
      return skills
    }
    return skills.filter((skill) => {
      const haystack = `${skill.name || ''} ${skill.skill_slug} ${skill.owner}/${skill.repo}`.toLowerCase()
      return haystack.includes(needle)
    })
  }, [search, skills])

  return (
    <div className="page-stack">
      <section className="section-block compact">
        <h1>Skills</h1>
        <input
          aria-label="Search skills"
          placeholder="Search by name or slug"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
        />
      </section>

      <section className="section-block compact">
        {loading ? <p>Loading skills...</p> : null}
        {error ? <p role="alert">{error}</p> : null}
        {!loading && !error && filtered.length === 0 ? <p>No skills found</p> : null}
        {!loading && !error && filtered.length > 0 ? (
          <table style={{ width: '100%' }}>
            <thead>
              <tr>
                <th align="left">Name</th>
                <th align="left">Owner/Repo</th>
                <th align="left">Weekly installs</th>
                <th align="left">Trust</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((skill) => (
                <tr key={skill.id}>
                  <td>
                    <AppLink to={`/skills/${encodeURIComponent(skill.id)}`}>{skill.name || skill.skill_slug}</AppLink>
                  </td>
                  <td>{skill.owner + '/' + skill.repo}</td>
                  <td>{formatInstalls(skill.weekly_installs || 0)}</td>
                  <td>
                    {skill.trust_badge || '-'}
                    {typeof skill.overall_score === 'number' ? ` (${skill.overall_score})` : ''}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : null}
      </section>
    </div>
  )
}
