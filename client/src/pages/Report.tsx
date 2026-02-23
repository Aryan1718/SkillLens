import { useEffect, useMemo, useState } from 'react'
import { ReportCard } from '../components/ReportCard'
import { SecurityPanel } from '../components/SecurityPanel'
import { QualityPanel } from '../components/QualityPanel'
import { BehaviorPanel } from '../components/BehaviorPanel'
import { DependencyPanel } from '../components/DependencyPanel'
import { TrySkillModal } from '../components/TrySkillModal'
import { AppLink, useCurrentPath, useSkillIdParam } from '../lib/router'
import { getSkill } from '../lib/api'
import type { SkillDetail } from '../types'

export function Report() {
  const path = useCurrentPath()
  const params = useSkillIdParam(path)
  const [skill, setSkill] = useState<SkillDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [notFound, setNotFound] = useState(false)

  useEffect(() => {
    if (!params?.id) {
      setNotFound(true)
      setLoading(false)
      return
    }
    let mounted = true
    setLoading(true)
    setNotFound(false)
    getSkill(params.id)
      .then((data) => {
        if (mounted) {
          setSkill(data)
        }
      })
      .catch(() => {
        if (mounted) {
          setNotFound(true)
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
  }, [params?.id])

  const canTrySkill = useMemo(() => {
    if (!skill) {
      return false
    }
    return Boolean(skill.skill_md_rendered?.trim() || skill.install_command?.trim() || skill.extracted_links?.length)
  }, [skill])

  if (loading) {
    return (
      <div className="page-stack">
        <section className="section-block compact">
          <p>Loading skill...</p>
        </section>
      </div>
    )
  }

  if (notFound || !skill) {
    return (
      <div className="page-stack">
        <section className="section-block compact">
          <p>Skill not found</p>
          <AppLink to="/">Back to skills</AppLink>
        </section>
      </div>
    )
  }

  return (
    <div className="page-stack">
      <section className="section-block compact">
        <AppLink to="/">Back to skills</AppLink>
      </section>

      <section className="section-block compact">
        <h2>{skill.name || skill.skill_slug}</h2>
        <p>{skill.owner + '/' + skill.repo}</p>
        <p>Slug: {skill.skill_slug}</p>
        {skill.page_url ? (
          <p>
            Page:{" "}
            <a href={skill.page_url} target="_blank" rel="noreferrer noopener">
              {skill.page_url}
            </a>
          </p>
        ) : null}
        {skill.repository_url ? (
          <p>
            Repository:{" "}
            <a href={skill.repository_url} target="_blank" rel="noreferrer noopener">
              {skill.repository_url}
            </a>
          </p>
        ) : null}
        {skill.install_command ? <p>Install: <code>{skill.install_command}</code></p> : null}
      </section>

      <section className="section-block compact report-security-layout">
        <div>
          <h3>Skill Content</h3>
          <pre style={{ whiteSpace: 'pre-wrap' }}>{skill.skill_md_rendered || 'No skill content available.'}</pre>
        </div>
        <div>
          <SecurityPanel data={skill.analysis.security} />
        </div>
      </section>

      <section className="section-block compact">
        <ReportCard
          report={{
            skill_name: skill.name || skill.skill_slug,
            overall_score: skill.analysis.overall_score,
            trust_badge: skill.analysis.trust_badge,
            analyzed_at: skill.analysis.analyzed_at,
          }}
        />
      </section>

      <section className="section-block compact">
        <QualityPanel data={skill.analysis.quality} />
        <BehaviorPanel data={skill.analysis.behavior} />
        <DependencyPanel data={skill.analysis.dependencies} />
      </section>

      {canTrySkill ? (
        <section className="section-block compact">
          <TrySkillModal skillContent={skill.skill_md_rendered} />
        </section>
      ) : null}
    </div>
  )
}
