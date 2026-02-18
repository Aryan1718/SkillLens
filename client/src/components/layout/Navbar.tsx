import { AppLink, useCurrentPath } from '../../lib/router'
import { MovingBorderButton } from '../ui/MovingBorderButton'

export function Navbar() {
  const path = useCurrentPath()

  return (
    <header className="site-header">
      <div className="container nav-shell">
        <AppLink className="brand" to="/" aria-label="SkillLens Home">
          <span className="brand-mark" aria-hidden="true">
            SL
          </span>
          <span>SkillLens</span>
        </AppLink>
        <nav className="nav-links" aria-label="Main navigation">
          <AppLink to="/" className={path === '/' ? 'active' : ''}>
            Home
          </AppLink>
          <AppLink to="/skills" className={path.startsWith('/skills') ? 'active' : ''}>
            Skills
          </AppLink>
        </nav>
        <AppLink to="/skills" className="nav-cta-link">
          <MovingBorderButton aria-label="Browse Skills">Browse Skills</MovingBorderButton>
        </AppLink>
      </div>
    </header>
  )
}
