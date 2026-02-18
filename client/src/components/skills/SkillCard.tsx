import type { SkillSummary } from '../../types'
import { formatInstalls, toSkillPath, topPlatforms } from '../../lib/utils'
import { AppLink } from '../../lib/router'
import { HoverTiltCard } from '../ui/HoverTiltCard'

interface SkillCardProps {
  skill: SkillSummary
}

export function SkillCard({ skill }: SkillCardProps) {
  const platforms = topPlatforms(skill.installed_on)

  return (
    <HoverTiltCard>
      <AppLink className="skill-card-link" to={toSkillPath(skill.owner, skill.repo, skill.skill_slug)}>
        <p className="skill-repo">{skill.owner + '/' + skill.repo}</p>
        <h3>{skill.skill_slug}</h3>
        <p className="skill-installs">{formatInstalls(skill.weekly_installs)} weekly installs</p>
        <div className="chip-row" aria-label="Installed on platforms">
          {platforms.length === 0 ? (
            <span className="chip chip-muted">No platform data</span>
          ) : (
            platforms.map(([platform, count]) => (
              <span className="chip" key={platform}>
                {platform} {count > 0 ? `(${count})` : ''}
              </span>
            ))
          )}
        </div>
      </AppLink>
    </HoverTiltCard>
  )
}
