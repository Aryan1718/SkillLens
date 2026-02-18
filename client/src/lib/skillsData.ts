/*
 Run:
  npm install
  npm run dev
*/

import type {
  SkillListQuery,
  SkillListResponse,
  SkillRecord,
  SkillSort,
  SkillSummary,
} from '../types'

interface SkillsIndexPayload {
  generated_at: string
  count: number
  owners: string[]
  items: SkillSummary[]
}

const API_BASE = import.meta.env.VITE_SKILLS_API_BASE?.replace(/\/$/, '')
const DEFAULT_PAGE_SIZE = 24

let indexCache: SkillsIndexPayload | null = null

function normalizeSort(sort?: SkillSort): SkillSort {
  return sort || 'weekly_desc'
}

function compareSkills(sort: SkillSort): (a: SkillSummary, b: SkillSummary) => number {
  if (sort === 'az') {
    return (a, b) => `${a.owner}/${a.repo}/${a.skill_slug}`.localeCompare(`${b.owner}/${b.repo}/${b.skill_slug}`)
  }
  if (sort === 'recent') {
    return (a, b) => Date.parse(b.scraped_at || b.last_seen_at) - Date.parse(a.scraped_at || a.last_seen_at)
  }
  return (a, b) => b.weekly_installs - a.weekly_installs
}

async function loadLocalIndex(): Promise<SkillsIndexPayload> {
  if (indexCache) {
    return indexCache
  }
  const response = await fetch('/skills/index.json')
  if (!response.ok) {
    indexCache = { generated_at: new Date().toISOString(), count: 0, owners: [], items: [] }
    return indexCache
  }
  indexCache = (await response.json()) as SkillsIndexPayload
  return indexCache
}

async function listSkillsFromApi(query: SkillListQuery): Promise<SkillListResponse> {
  const params = new URLSearchParams()
  if (query.page) params.set('page', String(query.page))
  if (query.pageSize) params.set('page_size', String(query.pageSize))
  if (query.search) params.set('search', query.search)
  if (query.owner) params.set('owner', query.owner)
  if (query.minInstalls !== undefined) params.set('min_installs', String(query.minInstalls))
  if (query.maxInstalls !== undefined) params.set('max_installs', String(query.maxInstalls))
  if (query.hasSkillMd !== undefined) params.set('has_skill_md', String(query.hasSkillMd))
  if (query.sort) params.set('sort', query.sort)

  const response = await fetch(`${API_BASE}/api/skills?${params.toString()}`)
  if (!response.ok) {
    throw new Error(`Skills API failed: ${response.status}`)
  }
  return response.json() as Promise<SkillListResponse>
}

function filterSkills(skills: SkillSummary[], query: SkillListQuery): SkillSummary[] {
  const search = query.search?.trim().toLowerCase()
  const minInstalls = query.minInstalls
  const maxInstalls = query.maxInstalls

  return skills.filter((skill) => {
    if (query.owner && skill.owner !== query.owner) {
      return false
    }
    if (query.hasSkillMd === true && !skill.has_skill_md) {
      return false
    }
    if (query.hasSkillMd === false && skill.has_skill_md) {
      return false
    }
    if (minInstalls !== undefined && skill.weekly_installs < minInstalls) {
      return false
    }
    if (maxInstalls !== undefined && skill.weekly_installs > maxInstalls) {
      return false
    }
    if (search) {
      const haystack = `${skill.owner}/${skill.repo}/${skill.skill_slug} ${skill.search_blob}`
      if (!haystack.includes(search)) {
        return false
      }
    }
    return true
  })
}

function paginate(skills: SkillSummary[], page: number, pageSize: number): SkillSummary[] {
  const start = (page - 1) * pageSize
  return skills.slice(start, start + pageSize)
}

export async function listSkills(query: SkillListQuery = {}): Promise<SkillListResponse> {
  if (API_BASE) {
    try {
      return await listSkillsFromApi(query)
    } catch {
      // fallback to local data when api is configured but unavailable
    }
  }

  const index = await loadLocalIndex()
  const page = Math.max(1, query.page || 1)
  const pageSize = Math.max(1, query.pageSize || DEFAULT_PAGE_SIZE)
  const sort = normalizeSort(query.sort)

  const filtered = filterSkills(index.items, query).sort(compareSkills(sort))
  const total = filtered.length
  const totalPages = Math.max(1, Math.ceil(total / pageSize))
  const currentPage = Math.min(page, totalPages)

  return {
    items: paginate(filtered, currentPage, pageSize),
    total,
    page: currentPage,
    pageSize,
    totalPages,
    owners: index.owners,
    emptyReason:
      index.count === 0
        ? 'No local skill data found. Run scraper first to populate data/skills/*.json.'
        : undefined,
  }
}

async function getSkillFromApi(owner: string, repo: string, slug: string): Promise<SkillRecord | null> {
  const response = await fetch(
    `${API_BASE}/api/skills/${encodeURIComponent(owner)}/${encodeURIComponent(repo)}/${encodeURIComponent(slug)}`
  )
  if (response.status === 404) {
    return null
  }
  if (!response.ok) {
    throw new Error(`Skill API failed: ${response.status}`)
  }
  return (await response.json()) as SkillRecord
}

function toDetailId(owner: string, repo: string, slug: string): string {
  return `${owner}__${repo}__${slug}`.replace(/[^a-zA-Z0-9._-]+/g, '-').toLowerCase()
}

export async function getSkill(owner: string, repo: string, slug: string): Promise<SkillRecord | null> {
  if (API_BASE) {
    try {
      return await getSkillFromApi(owner, repo, slug)
    } catch {
      // fallback to local data when api is configured but unavailable
    }
  }

  const detailId = toDetailId(owner, repo, slug)
  const response = await fetch(`/skills/details/${detailId}.json`)
  if (response.status === 404) {
    return null
  }
  if (!response.ok) {
    throw new Error(`Local skill detail failed: ${response.status}`)
  }
  return (await response.json()) as SkillRecord
}

export async function getTrendingSkills(limit = 8): Promise<SkillSummary[]> {
  const response = await listSkills({ page: 1, pageSize: limit, sort: 'weekly_desc' })
  return response.items.slice(0, limit)
}
