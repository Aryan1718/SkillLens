import type { ReactNode } from 'react'

interface BackgroundBeamsProps {
  children: ReactNode
}

export function BackgroundBeams({ children }: BackgroundBeamsProps) {
  return (
    <div className="bg-shell">
      <div className="bg-grid" aria-hidden="true" />
      <div className="bg-aurora bg-aurora-a" aria-hidden="true" />
      <div className="bg-aurora bg-aurora-b" aria-hidden="true" />
      <div className="bg-vignette" aria-hidden="true" />
      {children}
    </div>
  )
}
