/*
 Run:
  npm install
  npm run dev
*/

import { useEffect } from 'react'
import { Footer } from './components/layout/Footer'
import { Navbar } from './components/layout/Navbar'
import { BackgroundBeams } from './components/ui/BackgroundBeams'
import { useCurrentPath, useSkillParams, navigate } from './lib/router'
import { LandingPage } from './pages/LandingPage'
import { NotFoundPage } from './pages/NotFoundPage'
import { SkillDetailPage } from './pages/SkillDetailPage'
import { SkillsDirectoryPage } from './pages/SkillsDirectoryPage'

export function App() {
  const path = useCurrentPath()

  useEffect(() => {
    if (path === '/home') {
      navigate('/', true)
    }
  }, [path])

  const isSkillDetail = Boolean(useSkillParams(path))

  let page = <NotFoundPage />
  if (path === '/') {
    page = <LandingPage />
  } else if (path === '/skills') {
    page = <SkillsDirectoryPage />
  } else if (isSkillDetail) {
    page = <SkillDetailPage />
  }

  return (
    <BackgroundBeams>
      <Navbar />
      <main className="container site-main">{page}</main>
      <Footer />
    </BackgroundBeams>
  )
}
