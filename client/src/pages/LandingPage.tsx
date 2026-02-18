import { useEffect, useState } from 'react'
import type { SkillSummary } from '../types'
import { getTrendingSkills } from '../lib/skillsData'
import { formatInstalls, toSkillPath } from '../lib/utils'
import { AppLink } from '../lib/router'
import { MovingBorderButton } from '../components/ui/MovingBorderButton'
import { HoverTiltCard } from '../components/ui/HoverTiltCard'

export function LandingPage() {
  const [trending, setTrending] = useState<SkillSummary[]>([])

  useEffect(() => {
    getTrendingSkills(8)
      .then(setTrending)
      .catch(() => setTrending([]))
  }, [])

  return (
    <div className="page-stack">
      <section className="hero">
        <p className="eyebrow">Skills Intelligence Layer</p>
        <h1>Scan the AI Skill Ecosystem in a Futuristic Control Deck</h1>
        <p>
          Explore high-signal skill metadata, track install momentum, and inspect SKILL.md behavior without
          shipping unsafe artifacts to client bundles.
        </p>
        <div className="hero-actions">
          <AppLink to="/skills">
            <MovingBorderButton>Browse Skills</MovingBorderButton>
          </AppLink>
          <a href="#trending" className="secondary-btn">
            View Trending
          </a>
        </div>
      </section>

      <section id="trending" className="section-block">
        <div className="section-head">
          <h2>Featured / Trending Skills</h2>
          <AppLink to="/skills">See all</AppLink>
        </div>
        {trending.length === 0 ? (
          <div className="empty-state">
            <p>No local skill snapshots available yet.</p>
            <p>Run scraper first to populate `data/skills/*.json`.</p>
          </div>
        ) : (
          <div className="skills-grid">
            {trending.map((skill) => (
              <HoverTiltCard key={skill.id}>
                <AppLink className="skill-card-link" to={toSkillPath(skill.owner, skill.repo, skill.skill_slug)}>
                  <p className="skill-repo">{skill.owner + '/' + skill.repo}</p>
                  <h3>{skill.skill_slug}</h3>
                  <p className="skill-installs">{formatInstalls(skill.weekly_installs)} weekly installs</p>
                </AppLink>
              </HoverTiltCard>
            ))}
          </div>
        )}
      </section>

      <section className="section-block what-is">
        <h2>What is Skills.sh?</h2>
        <p>
          Skills.sh is a public discovery surface for shareable AI skills. SkillLens indexes scraped skill
          snapshots, then offers fast filtering, install insight, and rich markdown inspection through a
          secure local-first data pipeline.
        </p>
      </section>
    </div>
  )
}
