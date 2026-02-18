import type { ReactNode } from 'react'

interface HoverTiltCardProps {
  children: ReactNode
  className?: string
}

export function HoverTiltCard({ children, className = '' }: HoverTiltCardProps) {
  return <article className={`hover-tilt-card ${className}`.trim()}>{children}</article>
}
