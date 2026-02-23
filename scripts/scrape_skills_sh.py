#!/usr/bin/env python3
"""
Scrape skills from https://skills.sh with incremental local updates.

Usage:
  python scripts/scrape_skills_sh.py --count 5
  python scripts/scrape_skills_sh.py --count 5 --seed 123
  python scripts/scrape_skills_sh.py --all
  python scripts/scrape_skills_sh.py --all --dry-run
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

from server.fetchers.skills_sh_scraper import SkillsShScraper


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Scrape skills.sh skill pages.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--count", type=int, help="Scrape N random skills from discovered URLs.")
    mode.add_argument("--all", action="store_true", help="Scrape all discoverable skill URLs.")

    parser.add_argument("--outdir", default="data/skills", help="Output directory for per-skill JSON.")
    parser.add_argument("--concurrency", type=int, default=10, help="Concurrent page fetches.")
    parser.add_argument("--rate-limit", type=float, default=5.0, help="Requests per second cap.")
    parser.add_argument("--seed", type=int, default=None, help="Random seed for deterministic sampling.")
    parser.add_argument("--dry-run", action="store_true", help="Parse changes without writing files.")
    parser.add_argument(
        "--db-write",
        dest="db_write",
        action="store_true",
        default=True,
        help="Upsert scraped records into the skills table (default: true).",
    )
    parser.add_argument(
        "--no-db-write",
        dest="db_write",
        action="store_false",
        help="Disable upserting scraped records into the skills table.",
    )
    parser.add_argument(
        "--print",
        dest="do_print",
        action="store_true",
        default=True,
        help="Print NEW/UPDATED records as JSONL (default: true).",
    )
    parser.add_argument(
        "--no-print",
        dest="do_print",
        action="store_false",
        help="Disable JSONL output of changed records.",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Logging level.",
    )
    return parser.parse_args()


async def run() -> int:
    args = parse_args()
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )

    scraper = SkillsShScraper(
        outdir=Path(args.outdir),
        concurrency=args.concurrency,
        rate_limit=args.rate_limit,
    )
    summary = await scraper.scrape(
        count=args.count,
        include_all=args.all,
        seed=args.seed,
        dry_run=args.dry_run,
        print_jsonl=args.do_print,
        write_db=args.db_write,
    )
    print(json.dumps({"summary": summary}, ensure_ascii=False))
    return 0 if summary["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run()))
