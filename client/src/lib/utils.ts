/*
 Run:
  npm install
  npm run dev
*/

export function formatJson(value: unknown): string {
  return JSON.stringify(value, null, 2)
}

export function formatInstalls(value: number): string {
  if (value < 1000) {
    return value.toString()
  }
  if (value < 1_000_000) {
    return `${(value / 1000).toFixed(1).replace(/\.0$/, '')}K`
  }
  return `${(value / 1_000_000).toFixed(1).replace(/\.0$/, '')}M`
}

export function formatDate(value: string): string {
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) {
    return value
  }
  return new Intl.DateTimeFormat('en-US', {
    month: 'short',
    day: '2-digit',
    year: 'numeric',
  }).format(parsed)
}

export function toSkillPath(owner: string, repo: string, skillSlug: string): string {
  return `/skills/${encodeURIComponent(owner)}/${encodeURIComponent(repo)}/${encodeURIComponent(skillSlug)}`
}

export function topPlatforms(installedOn: Record<string, number>, count = 3): Array<[string, number]> {
  return Object.entries(installedOn)
    .sort((a, b) => b[1] - a[1])
    .slice(0, count)
}
