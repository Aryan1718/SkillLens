import { Footer } from './components/layout/Footer'
import { Navbar } from './components/layout/Navbar'
import { BackgroundBeams } from './components/ui/BackgroundBeams'
import { useCurrentPath, useSkillIdParam } from './lib/router'
import { Home } from './pages/Home'
import { NotFoundPage } from './pages/NotFoundPage'
import { Report } from './pages/Report'

export function App() {
  const path = useCurrentPath()
  const isSkillDetail = Boolean(useSkillIdParam(path))

  let page = <NotFoundPage />
  if (path === '/' || path === '/skills') {
    page = <Home />
  } else if (isSkillDetail) {
    page = <Report />
  }

  return (
    <BackgroundBeams>
      <Navbar />
      <main className="container site-main">{page}</main>
      <Footer />
    </BackgroundBeams>
  )
}
