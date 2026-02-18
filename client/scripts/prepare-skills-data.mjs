#!/usr/bin/env node
import fs from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const __filename = fileURLToPath(import.meta.url)
const __dirname = path.dirname(__filename)
const clientRoot = path.resolve(__dirname, '..')
const repoRoot = path.resolve(clientRoot, '..')
const sourceDir = path.resolve(repoRoot, 'data/skills')
const outputDir = path.resolve(clientRoot, 'public/skills')
const detailsDir = path.resolve(outputDir, 'details')

function toSafePart(value) {
  return String(value || '').replace(/[^a-zA-Z0-9._-]+/g, '-').toLowerCase()
}

function toDetailId(record) {
  return `${toSafePart(record.owner)}__${toSafePart(record.repo)}__${toSafePart(record.skill_slug)}`
}

function normalizeInstalledOn(installedOn) {
  if (installedOn && typeof installedOn === 'object' && !Array.isArray(installedOn)) {
    return installedOn
  }
  return {}
}

async function ensureOutputDirs() {
  await fs.mkdir(outputDir, { recursive: true })
  await fs.mkdir(detailsDir, { recursive: true })
}

function buildSummary(record) {
  const installedOn = normalizeInstalledOn(record.installed_on)
  const searchBlob = [
    record.owner,
    record.repo,
    record.skill_slug,
    record.install_command,
    record.skill_md_rendered?.slice(0, 2000),
  ]
    .filter(Boolean)
    .join(' ')
    .toLowerCase()

  return {
    id: record.id,
    source: record.source,
    owner: record.owner,
    repo: record.repo,
    skill_slug: record.skill_slug,
    page_url: record.page_url,
    repository_url: record.repository_url,
    install_command: record.install_command,
    weekly_installs: Number(record.weekly_installs || 0),
    first_seen_date: record.first_seen_date,
    installed_on: installedOn,
    scraped_at: record.scraped_at,
    last_seen_at: record.last_seen_at,
    has_skill_md: Boolean(record.skill_md_rendered && String(record.skill_md_rendered).trim().length > 0),
    search_blob: searchBlob,
    detail_id: toDetailId(record),
  }
}

function buildDetail(record) {
  return {
    id: record.id,
    source: record.source,
    owner: record.owner,
    repo: record.repo,
    skill_slug: record.skill_slug,
    page_url: record.page_url,
    repository_url: record.repository_url,
    install_command: record.install_command,
    skill_md_rendered: record.skill_md_rendered || '',
    skill_md_hash: record.skill_md_hash,
    extracted_links: Array.isArray(record.extracted_links) ? record.extracted_links : [],
    weekly_installs: Number(record.weekly_installs || 0),
    first_seen_date: record.first_seen_date,
    installed_on: normalizeInstalledOn(record.installed_on),
    parse_version: record.parse_version,
    scraped_at: record.scraped_at,
    last_seen_at: record.last_seen_at,
  }
}

async function clearStaleDetails() {
  try {
    const files = await fs.readdir(detailsDir)
    await Promise.all(files.map((file) => fs.unlink(path.join(detailsDir, file))))
  } catch {
    // noop
  }
}

async function main() {
  await ensureOutputDirs()

  let files = []
  try {
    files = (await fs.readdir(sourceDir)).filter((file) => file.endsWith('.json'))
  } catch {
    files = []
  }

  await clearStaleDetails()

  const summaries = []

  for (const file of files) {
    const sourcePath = path.join(sourceDir, file)
    const raw = await fs.readFile(sourcePath, 'utf8')
    const record = JSON.parse(raw)
    const summary = buildSummary(record)
    const detail = buildDetail(record)
    summaries.push(summary)

    const detailPath = path.join(detailsDir, `${summary.detail_id}.json`)
    await fs.writeFile(detailPath, `${JSON.stringify(detail)}\n`, 'utf8')
  }

  summaries.sort((a, b) => b.weekly_installs - a.weekly_installs)

  const indexPayload = {
    generated_at: new Date().toISOString(),
    count: summaries.length,
    owners: [...new Set(summaries.map((item) => item.owner))].sort((a, b) => a.localeCompare(b)),
    items: summaries,
  }

  await fs.writeFile(path.join(outputDir, 'index.json'), `${JSON.stringify(indexPayload)}\n`, 'utf8')
  console.log(`Prepared skills data: ${summaries.length} records.`)
}

main().catch((error) => {
  console.error(error)
  process.exit(1)
})
