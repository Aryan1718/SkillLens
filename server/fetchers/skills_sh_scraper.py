"""skills.sh scraper with discovery, parsing, and incremental local storage."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import random
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup
from xml.etree import ElementTree as ET

LOGGER = logging.getLogger(__name__)

SOURCE_NAME = "skills.sh"
PARSE_VERSION = "skills_sh_v1"
DEFAULT_BASE_URL = "https://skills.sh"
STATE_FILENAME = "state.json"

SKILL_PATH_RE = re.compile(r"^/([^/]+)/([^/]+)/([^/]+)/?$")
COUNT_RE = re.compile(r"^\s*([0-9][0-9,]*(?:\.[0-9]+)?)\s*([KMBkmb]?)\s*$")
DATE_ABS_FORMATS = ("%b %d, %Y", "%B %d, %Y")
DATE_REL_RE = re.compile(r"^\s*(\d+)\s+(day|week|month|year)s?\s+ago\s*$", re.I)

STOP_HEADERS = {"Weekly Installs", "Repository", "First Seen", "Installed on"}


class ScraperError(Exception):
    """Raised for recoverable scraper errors."""


class AsyncRateLimiter:
    """Token-interval rate limiter for async request pacing."""

    def __init__(self, rate_per_second: float) -> None:
        self.rate = max(rate_per_second, 0.001)
        self.interval = 1.0 / self.rate
        self._next_time = 0.0
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        loop = asyncio.get_running_loop()
        async with self._lock:
            now = loop.time()
            wait_for = self._next_time - now
            if wait_for > 0:
                await asyncio.sleep(wait_for)
                now = loop.time()
            self._next_time = now + self.interval


@dataclass(slots=True)
class FetchResult:
    url: str
    status_code: int
    text: str


def parse_count(value: str) -> int:
    """Parse count strings like '249.7K', '1.2M', '71' into integers."""
    match = COUNT_RE.match(value or "")
    if not match:
        raise ValueError(f"Invalid count string: {value!r}")
    base = float(match.group(1).replace(",", ""))
    suffix = match.group(2).upper()
    multiplier = {"": 1, "K": 1_000, "M": 1_000_000, "B": 1_000_000_000}[suffix]
    return int(base * multiplier)


def normalize_whitespace_lines(text: str) -> list[str]:
    lines = [line.rstrip() for line in text.splitlines()]
    return lines


def parse_first_seen_date(raw: str, now: datetime | None = None) -> str:
    """Parse first-seen date to YYYY-MM-DD, handling absolute and relative text."""
    value = (raw or "").strip()
    if not value:
        raise ValueError("Empty first_seen_date")

    for fmt in DATE_ABS_FORMATS:
        try:
            return datetime.strptime(value, fmt).date().isoformat()
        except ValueError:
            continue

    rel = DATE_REL_RE.match(value)
    if rel:
        amount = int(rel.group(1))
        unit = rel.group(2).lower()
        now_dt = now or datetime.now(timezone.utc)
        days = {
            "day": amount,
            "week": amount * 7,
            "month": amount * 30,
            "year": amount * 365,
        }[unit]
        return (now_dt - timedelta(days=days)).date().isoformat()

    raise ValueError(f"Unable to parse first_seen_date: {raw!r}")


def parse_path_parts(page_url: str) -> tuple[str, str, str]:
    parsed = urlparse(page_url)
    match = SKILL_PATH_RE.match(parsed.path)
    if not match:
        raise ValueError(f"Not a skill URL path: {page_url}")
    owner, repo, slug = match.group(1), match.group(2), match.group(3)
    return owner, repo, slug


def absolute_links_from_html(page_url: str, soup: BeautifulSoup) -> list[str]:
    links: list[str] = []
    seen: set[str] = set()
    for a_tag in soup.find_all("a", href=True):
        href = (a_tag.get("href") or "").strip()
        if not href:
            continue
        abs_url = urljoin(page_url, href)
        if abs_url not in seen:
            seen.add(abs_url)
            links.append(abs_url)
    return links


def _extract_install_command(soup: BeautifulSoup) -> str:
    for code in soup.find_all(["code", "pre"]):
        text = " ".join(code.get_text(" ", strip=True).split())
        if "npx skills add" in text and "--skill" in text:
            return code.get_text(" ", strip=True)
    full_text = soup.get_text("\n", strip=False)
    command_match = re.search(
        r"\$\s*npx\s+skills\s+add[^\n]+--skill[^\n]*", full_text, re.IGNORECASE
    )
    if command_match:
        return command_match.group(0).strip()
    return ""


def _section_value_lines(all_lines: list[str], heading: str) -> list[str]:
    try:
        idx = all_lines.index(heading)
    except ValueError:
        return []
    values: list[str] = []
    for line in all_lines[idx + 1 :]:
        stripped = line.strip()
        if not stripped:
            if values:
                continue
            continue
        if stripped in STOP_HEADERS:
            break
        values.append(stripped)
    return values


def _extract_skill_md_rendered(all_lines: list[str]) -> str:
    if "SKILL.md" not in all_lines:
        return ""
    idx = all_lines.index("SKILL.md")
    content_lines: list[str] = []
    for line in all_lines[idx + 1 :]:
        if line.strip() in STOP_HEADERS:
            break
        content_lines.append(line.rstrip())

    while content_lines and not content_lines[0].strip():
        content_lines.pop(0)
    while content_lines and not content_lines[-1].strip():
        content_lines.pop()

    joined = "\n".join(content_lines).strip()
    if "No SKILL.md available for this skill." in joined:
        return "No SKILL.md available for this skill."
    return joined


def parse_skill_page(page_url: str, html: str, now: datetime | None = None) -> dict[str, Any]:
    """Pure parser for one skill page HTML."""
    owner, repo, skill_slug = parse_path_parts(page_url)
    soup = BeautifulSoup(html, "html.parser")
    lines = normalize_whitespace_lines(soup.get_text("\n", strip=False))
    normalized_lines = [line.strip() for line in lines]

    install_command = _extract_install_command(soup)
    skill_md_rendered = _extract_skill_md_rendered(lines)
    skill_md_hash = hashlib.sha256(skill_md_rendered.encode("utf-8")).hexdigest()

    weekly_value_lines = _section_value_lines(normalized_lines, "Weekly Installs")
    weekly_installs = parse_count(weekly_value_lines[0]) if weekly_value_lines else 0

    repo_value_lines = _section_value_lines(normalized_lines, "Repository")
    repository_url = ""
    if repo_value_lines:
        repo_hint = repo_value_lines[0]
        if repo_hint.startswith("http://") or repo_hint.startswith("https://"):
            repository_url = repo_hint
    if not repository_url:
        for a_tag in soup.find_all("a", href=True):
            href = (a_tag.get("href") or "").strip()
            if "github.com" in href:
                abs_url = urljoin(page_url, href)
                if f"/{owner}/{repo}" in abs_url:
                    repository_url = abs_url
                    break
        if not repository_url:
            repository_url = f"https://github.com/{owner}/{repo}"

    first_seen_lines = _section_value_lines(normalized_lines, "First Seen")
    first_seen_raw = first_seen_lines[0] if first_seen_lines else ""
    first_seen_date = parse_first_seen_date(first_seen_raw, now=now) if first_seen_raw else ""

    installed_on: dict[str, int] = {}
    installed_lines = _section_value_lines(normalized_lines, "Installed on")
    for raw_line in installed_lines:
        match = re.match(r"^(.*\S)\s+([0-9][0-9,]*(?:\.[0-9]+)?[KMBkmb]?)$", raw_line)
        if not match:
            continue
        platform = match.group(1).strip().lower()
        installed_on[platform] = parse_count(match.group(2))

    extracted_links = absolute_links_from_html(page_url, soup)
    deterministic_id = str(uuid.uuid5(uuid.NAMESPACE_URL, page_url))

    return {
        "id": deterministic_id,
        "source": SOURCE_NAME,
        "owner": owner,
        "repo": repo,
        "skill_slug": skill_slug,
        "page_url": page_url,
        "repository_url": repository_url,
        "install_command": install_command,
        "skill_md_rendered": skill_md_rendered,
        "skill_md_hash": skill_md_hash,
        "raw_html": html,
        "extracted_links": extracted_links,
        "weekly_installs": weekly_installs,
        "first_seen_date": first_seen_date,
        "installed_on": installed_on,
        "parse_version": PARSE_VERSION,
    }


def _tracked_record_digest(record: dict[str, Any]) -> str:
    tracked = {
        "id": record.get("id"),
        "source": record.get("source"),
        "owner": record.get("owner"),
        "repo": record.get("repo"),
        "skill_slug": record.get("skill_slug"),
        "page_url": record.get("page_url"),
        "repository_url": record.get("repository_url"),
        "install_command": record.get("install_command"),
        "skill_md_hash": record.get("skill_md_hash"),
        "skill_md_rendered": record.get("skill_md_rendered"),
        "extracted_links": record.get("extracted_links", []),
        "weekly_installs": record.get("weekly_installs"),
        "first_seen_date": record.get("first_seen_date"),
        "installed_on": record.get("installed_on", {}),
        "parse_version": record.get("parse_version"),
    }
    payload = json.dumps(tracked, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _sanitize_filename_part(part: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", part)


def record_file_path(outdir: Path, record: dict[str, Any]) -> Path:
    owner = _sanitize_filename_part(record["owner"])
    repo = _sanitize_filename_part(record["repo"])
    slug = _sanitize_filename_part(record["skill_slug"])
    return outdir / f"{owner}__{repo}__{slug}.json"


def load_state(state_path: Path) -> dict[str, Any]:
    if not state_path.exists():
        return {"version": 1, "skills": {}}
    return json.loads(state_path.read_text(encoding="utf-8"))


def save_state(state_path: Path, state: dict[str, Any]) -> None:
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")


def extract_skill_urls_from_html(base_url: str, html: str) -> set[str]:
    soup = BeautifulSoup(html, "html.parser")
    urls: set[str] = set()
    for a_tag in soup.find_all("a", href=True):
        href = (a_tag.get("href") or "").strip()
        if not href:
            continue
        abs_url = urljoin(base_url, href)
        parsed = urlparse(abs_url)
        if parsed.netloc != urlparse(base_url).netloc:
            continue
        if SKILL_PATH_RE.match(parsed.path):
            urls.add(f"{parsed.scheme}://{parsed.netloc}{parsed.path.rstrip('/')}")
    return urls


def extract_pagination_urls(base_url: str, html: str) -> set[str]:
    soup = BeautifulSoup(html, "html.parser")
    urls: set[str] = set()
    for a_tag in soup.find_all("a", href=True):
        href = (a_tag.get("href") or "").strip()
        if not href:
            continue
        abs_url = urljoin(base_url, href)
        parsed = urlparse(abs_url)
        if parsed.netloc != urlparse(base_url).netloc:
            continue
        query = parsed.query.lower()
        if any(k in query for k in ("page=", "cursor=", "offset=", "start=", "from=")):
            urls.add(abs_url)
    return urls


def extract_alltime_count(html: str) -> int | None:
    text = BeautifulSoup(html, "html.parser").get_text(" ", strip=True)
    match = re.search(r"All\s*Time\s*\(\s*([0-9,]+)\s*\)", text, re.IGNORECASE)
    if not match:
        return None
    return int(match.group(1).replace(",", ""))


def extract_api_candidates(base_url: str, html: str) -> set[str]:
    candidates: set[str] = set()
    for raw in re.findall(r"""["'](/(?:api|_next/data)/[^"']+)["']""", html):
        if "leader" in raw.lower() or "skill" in raw.lower() or raw.startswith("/_next/data/"):
            candidates.add(urljoin(base_url, raw))
    return candidates


def extract_skill_urls_from_json(data: Any, base_url: str) -> set[str]:
    found: set[str] = set()
    stack = [data]
    while stack:
        node = stack.pop()
        if isinstance(node, dict):
            stack.extend(node.values())
            for value in node.values():
                if isinstance(value, str):
                    candidate = value.strip()
                    if candidate.startswith("http://") or candidate.startswith("https://"):
                        parsed = urlparse(candidate)
                        if (
                            parsed.netloc == urlparse(base_url).netloc
                            and SKILL_PATH_RE.match(parsed.path)
                        ):
                            found.add(f"{parsed.scheme}://{parsed.netloc}{parsed.path.rstrip('/')}")
                    elif candidate.startswith("/"):
                        if SKILL_PATH_RE.match(urlparse(candidate).path):
                            found.add(urljoin(base_url, candidate).rstrip("/"))
        elif isinstance(node, list):
            stack.extend(node)
    return found


class SkillsShScraper:
    """Scraper runner for discovery + page scraping + incremental file writes."""

    def __init__(
        self,
        outdir: Path,
        concurrency: int = 10,
        rate_limit: float = 5.0,
        timeout_seconds: float = 20.0,
        base_url: str = DEFAULT_BASE_URL,
    ) -> None:
        self.outdir = outdir
        self.concurrency = max(1, concurrency)
        self.rate_limit = max(0.1, rate_limit)
        self.timeout_seconds = timeout_seconds
        self.base_url = base_url.rstrip("/")
        self.state_path = self.outdir.parent / STATE_FILENAME

    async def _fetch_with_retry(
        self,
        client: httpx.AsyncClient,
        limiter: AsyncRateLimiter,
        url: str,
        attempts: int = 4,
    ) -> FetchResult:
        last_error: Exception | None = None
        for attempt in range(1, attempts + 1):
            try:
                await limiter.acquire()
                resp = await client.get(url, timeout=self.timeout_seconds, follow_redirects=True)
                if resp.status_code >= 500:
                    raise ScraperError(f"Server error {resp.status_code} for {url}")
                if resp.status_code >= 400:
                    raise ScraperError(f"HTTP {resp.status_code} for {url}")
                return FetchResult(url=url, status_code=resp.status_code, text=resp.text)
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                if attempt == attempts:
                    break
                await asyncio.sleep(min(8.0, 0.75 * (2**(attempt - 1))))
        raise ScraperError(f"Failed fetching {url}: {last_error}") from last_error

    async def _discover_from_leaderboard(
        self, client: httpx.AsyncClient, limiter: AsyncRateLimiter
    ) -> tuple[set[str], int | None, set[str], set[str]]:
        seed_pages = [f"{self.base_url}/", f"{self.base_url}/trending", f"{self.base_url}/hot"]
        queue = list(seed_pages)
        seen_pages: set[str] = set()
        discovered_skill_urls: set[str] = set()
        api_candidates: set[str] = set()
        total_alltime: int | None = None

        while queue:
            page_url = queue.pop(0)
            if page_url in seen_pages:
                continue
            seen_pages.add(page_url)
            try:
                fetched = await self._fetch_with_retry(client, limiter, page_url)
            except Exception as exc:  # noqa: BLE001
                LOGGER.warning("Failed leaderboard page fetch %s: %s", page_url, exc)
                continue

            html = fetched.text
            discovered_skill_urls.update(extract_skill_urls_from_html(self.base_url, html))
            api_candidates.update(extract_api_candidates(self.base_url, html))
            paginations = extract_pagination_urls(self.base_url, html)
            for nxt in sorted(paginations):
                if nxt not in seen_pages:
                    queue.append(nxt)

            if total_alltime is None and page_url.rstrip("/") == self.base_url:
                total_alltime = extract_alltime_count(html)

        return discovered_skill_urls, total_alltime, api_candidates, seen_pages

    async def _discover_from_api_candidates(
        self,
        client: httpx.AsyncClient,
        limiter: AsyncRateLimiter,
        api_candidates: set[str],
    ) -> set[str]:
        discovered: set[str] = set()
        for endpoint in sorted(api_candidates):
            endpoints_to_try = {endpoint}
            if "?" in endpoint:
                base = endpoint.split("?", 1)[0]
            else:
                base = endpoint
            for offset in (0, 200, 400, 800, 1200):
                for limit in (100, 200):
                    endpoints_to_try.add(f"{base}?offset={offset}&limit={limit}")
                    endpoints_to_try.add(f"{base}?page={offset // max(limit, 1) + 1}&limit={limit}")
                    endpoints_to_try.add(f"{base}?cursor={offset}&limit={limit}")

            for url in sorted(endpoints_to_try):
                try:
                    fetched = await self._fetch_with_retry(client, limiter, url)
                except Exception:
                    continue
                try:
                    payload = json.loads(fetched.text)
                except json.JSONDecodeError:
                    continue
                discovered.update(extract_skill_urls_from_json(payload, self.base_url))
        return discovered

    async def _discover_from_sitemap(
        self, client: httpx.AsyncClient, limiter: AsyncRateLimiter
    ) -> set[str]:
        urls: set[str] = set()
        sitemap_queue = [f"{self.base_url}/sitemap.xml", f"{self.base_url}/sitemap_index.xml"]
        seen: set[str] = set()

        while sitemap_queue:
            sm_url = sitemap_queue.pop(0)
            if sm_url in seen:
                continue
            seen.add(sm_url)
            try:
                fetched = await self._fetch_with_retry(client, limiter, sm_url)
            except Exception:
                continue
            try:
                root = ET.fromstring(fetched.text)
            except ET.ParseError:
                continue
            ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
            loc_nodes = root.findall(".//sm:loc", ns) or root.findall(".//loc")
            for node in loc_nodes:
                loc = (node.text or "").strip()
                if not loc:
                    continue
                parsed = urlparse(loc)
                if parsed.netloc != urlparse(self.base_url).netloc:
                    continue
                if loc.endswith(".xml"):
                    sitemap_queue.append(loc)
                    continue
                if SKILL_PATH_RE.match(parsed.path):
                    urls.add(f"{parsed.scheme}://{parsed.netloc}{parsed.path.rstrip('/')}")
        return urls

    async def discover_skill_urls(self, include_all: bool) -> set[str]:
        timeout = httpx.Timeout(self.timeout_seconds)
        limiter = AsyncRateLimiter(self.rate_limit)
        headers = {"User-Agent": "SkillLens skills.sh scraper (+https://github.com/yourusername/skilllens)"}
        async with httpx.AsyncClient(timeout=timeout, headers=headers) as client:
            from_board, alltime_total, api_candidates, _ = await self._discover_from_leaderboard(
                client, limiter
            )
            discovered = set(from_board)

            if include_all:
                needs_more = alltime_total is None or len(discovered) < alltime_total
                if needs_more and api_candidates:
                    discovered.update(
                        await self._discover_from_api_candidates(client, limiter, api_candidates)
                    )
                needs_more = alltime_total is None or len(discovered) < alltime_total
                if needs_more:
                    discovered.update(await self._discover_from_sitemap(client, limiter))

        return discovered

    async def scrape(
        self,
        count: int | None = None,
        include_all: bool = False,
        seed: int | None = None,
        dry_run: bool = False,
        print_jsonl: bool = True,
    ) -> dict[str, Any]:
        if include_all and count is not None:
            raise ValueError("Use either --all or --count, not both.")
        if not include_all and (count is None or count <= 0):
            raise ValueError("--count must be > 0 when --all is not used.")

        discovered_urls = await self.discover_skill_urls(include_all=include_all)
        all_urls_sorted = sorted(discovered_urls)

        if include_all:
            selected_urls = all_urls_sorted
        else:
            rng = random.Random(seed)
            if count is None:
                selected_urls = all_urls_sorted
            elif count >= len(all_urls_sorted):
                selected_urls = all_urls_sorted
            else:
                selected_urls = sorted(rng.sample(all_urls_sorted, count))

        state = load_state(self.state_path)
        state_skills = state.setdefault("skills", {})
        now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()

        summary = {
            "total_discovered_urls": len(discovered_urls),
            "selected_urls": len(selected_urls),
            "fetched": 0,
            "new": 0,
            "updated": 0,
            "unchanged": 0,
            "failed": 0,
            "errors": [],
        }

        timeout = httpx.Timeout(self.timeout_seconds)
        limiter = AsyncRateLimiter(self.rate_limit)
        semaphore = asyncio.Semaphore(self.concurrency)
        headers = {"User-Agent": "SkillLens skills.sh scraper (+https://github.com/yourusername/skilllens)"}

        async with httpx.AsyncClient(timeout=timeout, headers=headers) as client:
            async def process_one(page_url: str) -> tuple[str, dict[str, Any] | None, str | None]:
                async with semaphore:
                    try:
                        fetched = await self._fetch_with_retry(client, limiter, page_url)
                        record = parse_skill_page(
                            page_url, fetched.text, now=datetime.now(timezone.utc)
                        )
                        record["scraped_at"] = now
                        record["last_seen_at"] = now
                        return page_url, record, None
                    except Exception as exc:  # noqa: BLE001
                        return page_url, None, str(exc)

            tasks = [asyncio.create_task(process_one(u)) for u in selected_urls]
            for coro in asyncio.as_completed(tasks):
                page_url, record, error = await coro
                summary["fetched"] += 1

                if error:
                    summary["failed"] += 1
                    summary["errors"].append({"page_url": page_url, "error": error})
                    LOGGER.error("Failed page %s: %s", page_url, error)
                    continue

                assert record is not None
                digest = _tracked_record_digest(record)
                previous = state_skills.get(page_url)
                event: str
                if previous is None:
                    event = "NEW"
                    summary["new"] += 1
                elif previous.get("record_digest") == digest:
                    event = "UNCHANGED"
                    summary["unchanged"] += 1
                else:
                    event = "UPDATED"
                    summary["updated"] += 1

                state_skills[page_url] = {
                    "id": record["id"],
                    "record_digest": digest,
                    "skill_md_hash": record["skill_md_hash"],
                    "scraped_at": now,
                    "last_seen_at": now,
                    "file_path": str(record_file_path(self.outdir, record)),
                    "parse_version": record["parse_version"],
                }

                if event in {"NEW", "UPDATED"}:
                    if print_jsonl:
                        print(json.dumps({"event": event, "record": record}, ensure_ascii=False))
                    if not dry_run:
                        path = record_file_path(self.outdir, record)
                        path.parent.mkdir(parents=True, exist_ok=True)
                        path.write_text(
                            json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8"
                        )

        if not dry_run:
            save_state(self.state_path, state)

        return summary
