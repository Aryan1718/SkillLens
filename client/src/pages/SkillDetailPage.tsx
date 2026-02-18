import { useEffect, useState } from 'react'
import { MarkdownContent } from '../components/skills/MarkdownContent'
import { AppLink, useCurrentPath, useSkillParams } from '../lib/router'
import { getSkill } from '../lib/skillsData'
import { formatDate, formatInstalls, topPlatforms } from '../lib/utils'
import type { SkillRecord } from '../types'

export function SkillDetailPage() {
  const path = useCurrentPath()
  const params = useSkillParams(path)

  const [skill, setSkill] = useState<SkillRecord | null>(null)
  const [notFound, setNotFound] = useState(false)
  const [copied, setCopied] = useState(false)

  useEffect(() => {
    if (!params) {
      setNotFound(true)
      return
    }

    getSkill(params.owner, params.repo, params.skillSlug)
      .then((result) => {
        setSkill(result)
        setNotFound(!result)
      })
      .catch(() => setNotFound(true))
  }, [params])

  async function handleCopyInstall() {
    if (!skill?.install_command) {
      return
    }
    try {
      await navigator.clipboard.writeText(skill.install_command)
      setCopied(true)
      setTimeout(() => setCopied(false), 1200)
    } catch {
      setCopied(false)
    }
  }

  if (notFound) {
    return (
      <div className="page-stack">
        <section className="section-block compact">
          <p>Skill not found.</p>
          <AppLink to="/skills">Back to skills</AppLink>
        </section>
      </div>
    )
  }

  if (!skill) {
    return (
      <div className="page-stack">
        <section className="section-block compact">
          <p>Loading skill...</p>
        </section>
      </div>
    )
  }

  const platforms = topPlatforms(skill.installed_on, 20)

  return (
    <div className="page-stack">
      <section className="section-block compact">
        <nav className="breadcrumbs" aria-label="Breadcrumb">
          <AppLink to="/skills">Skills</AppLink>
          <span>/</span>
          <span>{skill.owner}</span>
          <span>/</span>
          <span>{skill.repo}</span>
          <span>/</span>
          <span>{skill.skill_slug}</span>
        </nav>
      </section>

      <section className="section-block">
        <h1>{skill.skill_slug}</h1>
        <p className="skill-repo">{skill.owner + '/' + skill.repo}</p>

        <div className="meta-grid">
          <div className="meta-panel">
            <p>Weekly installs</p>
            <strong>{formatInstalls(skill.weekly_installs)}</strong>
          </div>
          <div className="meta-panel">
            <p>First seen</p>
            <strong>{formatDate(skill.first_seen_date)}</strong>
          </div>
          <div className="meta-panel">
            <p>Last updated</p>
            <strong>{formatDate(skill.scraped_at || skill.last_seen_at)}</strong>
          </div>
        </div>

        <div className="install-row">
          <code>{skill.install_command}</code>
          <button type="button" onClick={handleCopyInstall} aria-label="Copy install command">
            {copied ? 'Copied' : 'Copy install command'}
          </button>
        </div>

        <div className="links-row">
          <a href={skill.repository_url} target="_blank" rel="noreferrer noopener">
            Repository
          </a>
          <a href={skill.page_url} target="_blank" rel="noreferrer noopener">
            Source page
          </a>
        </div>
      </section>

      <section className="section-block markdown-wrap">
        <h2>SKILL.md</h2>
        <MarkdownContent content={skill.skill_md_rendered || ''} />
      </section>

      <section className="section-block compact">
        <h2>Extracted links</h2>
        {skill.extracted_links.length === 0 ? (
          <p>No links extracted.</p>
        ) : (
          <ul className="links-list">
            {skill.extracted_links.map((link) => (
              <li key={link}>
                <a href={link} target="_blank" rel="noreferrer noopener">
                  Link: {link}
                </a>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="section-block compact">
        <h2>Installed on</h2>
        <div className="chip-row" aria-label="Installed on platforms">
          {platforms.length === 0 ? (
            <span className="chip chip-muted">No platform data</span>
          ) : (
            platforms.map(([platform, count]) => (
              <span className="chip" key={platform}>
                {platform}: {count}
              </span>
            ))
          )}
        </div>
      </section>
    </div>
  )
}
