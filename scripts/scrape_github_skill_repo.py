#!/usr/bin/env python3
"""
Scrape canonical SKILL.md and related files from GitHub repositories.

Usage:
  python scripts/scrape_github_skill_repo.py --input data/skills --all
  python scripts/scrape_github_skill_repo.py --input data/skills --count 5 --seed 123
  python scripts/scrape_github_skill_repo.py --repo https://github.com/owner/repo --skill demo
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from server.fetchers.github_skill_repo_scraper import (
    GitHubSkillRepoScraper,
    load_skill_records,
    parse_github_repo_url,
    sample_records,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Scrape GitHub repos for canonical SKILL.md and referenced files."
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--input", help="Directory of skills JSON files from scraper #1.")
    source.add_argument("--repo", help="Single repository URL (https://github.com/{owner}/{repo}).")

    selection = parser.add_mutually_exclusive_group()
    selection.add_argument("--all", action="store_true", help="Process all records from --input.")
    selection.add_argument("--count", type=int, help="Process N random records from --input.")

    parser.add_argument("--skill", help="Optional skill slug for --repo mode.")
    parser.add_argument("--seed", type=int, default=None, help="Random seed for deterministic sampling.")
    parser.add_argument("--outdir", default="data/github", help="Output base directory.")
    parser.add_argument("--concurrency", type=int, default=5, help="Concurrent skills to process.")
    parser.add_argument("--rate-limit", type=float, default=2.0, help="GitHub requests per second cap.")
    parser.add_argument("--dry-run", action="store_true", help="Run without writing files/state.")
    parser.add_argument(
        "--print",
        dest="do_print",
        action="store_true",
        default=True,
        help="Print JSONL events (default: true).",
    )
    parser.add_argument(
        "--no-print",
        dest="do_print",
        action="store_false",
        help="Disable JSONL event output.",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Logging level.",
    )
    return parser.parse_args()


def build_records_from_repo_mode(repository_url: str, skill_slug: str | None) -> list[dict[str, str]]:
    owner, repo = parse_github_repo_url(repository_url)
    return [
        {
            "repository_url": repository_url,
            "owner": owner,
            "repo": repo,
            "skill_slug": skill_slug or repo,
        }
    ]


def build_records_from_input_mode(args: argparse.Namespace) -> list[dict[str, str]]:
    input_dir = Path(args.input)
    records = load_skill_records(input_dir)
    if not records:
        raise ValueError(f"No valid skill records found in {input_dir}")
    if args.all:
        return sample_records(records, include_all=True, count=None, seed=args.seed)
    if args.count:
        return sample_records(records, include_all=False, count=args.count, seed=args.seed)
    raise ValueError("For --input mode, pass either --all or --count N.")


async def run() -> int:
    args = parse_args()
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )

    if args.repo:
        records = build_records_from_repo_mode(args.repo, args.skill)
    else:
        records = build_records_from_input_mode(args)

    scraper = GitHubSkillRepoScraper(
        outdir=Path(args.outdir),
        concurrency=args.concurrency,
        rate_limit=args.rate_limit,
    )
    summary = await scraper.scrape(
        records=records,
        dry_run=args.dry_run,
        print_jsonl=args.do_print,
    )
    print(json.dumps({"summary": summary}, ensure_ascii=False))
    return 0 if summary["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run()))
