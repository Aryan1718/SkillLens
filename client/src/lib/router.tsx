import { useEffect, useMemo, useState } from 'react'
import type { AnchorHTMLAttributes, MouseEvent, ReactNode } from 'react'

export interface SkillRouteParams {
  owner: string
  repo: string
  skillSlug: string
}

function cleanPath(path: string): string {
  if (!path) return '/'
  const next = path.startsWith('/') ? path : `/${path}`
  return next.replace(/\/+$/, '') || '/'
}

export function navigate(to: string, replace = false): void {
  const nextPath = cleanPath(to)
  if (replace) {
    window.history.replaceState(null, '', nextPath)
  } else {
    window.history.pushState(null, '', nextPath)
  }
  window.dispatchEvent(new PopStateEvent('popstate'))
}

export function useCurrentPath(): string {
  const [path, setPath] = useState(() => cleanPath(window.location.pathname))

  useEffect(() => {
    function onPopState() {
      setPath(cleanPath(window.location.pathname))
    }

    window.addEventListener('popstate', onPopState)
    return () => window.removeEventListener('popstate', onPopState)
  }, [])

  return path
}

export function useSkillParams(path: string): SkillRouteParams | null {
  return useMemo(() => {
    const matched = path.match(/^\/skills\/([^/]+)\/([^/]+)\/([^/]+)$/)
    if (!matched) {
      return null
    }
    return {
      owner: decodeURIComponent(matched[1]),
      repo: decodeURIComponent(matched[2]),
      skillSlug: decodeURIComponent(matched[3]),
    }
  }, [path])
}

interface AppLinkProps extends Omit<AnchorHTMLAttributes<HTMLAnchorElement>, 'href'> {
  to: string
  children: ReactNode
}

export function AppLink({ to, onClick, children, ...rest }: AppLinkProps) {
  function handleClick(event: MouseEvent<HTMLAnchorElement>) {
    if (onClick) {
      onClick(event)
    }
    if (event.defaultPrevented) {
      return
    }
    if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey || rest.target === '_blank') {
      return
    }
    event.preventDefault()
    navigate(to)
  }

  return (
    <a href={to} {...rest} onClick={handleClick}>
      {children}
    </a>
  )
}
