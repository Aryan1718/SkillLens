from __future__ import annotations

from pathlib import Path

from server.fetchers.skills_sh_scraper import parse_count, parse_skill_page


FIXTURES = Path(__file__).parent / "fixtures"


def test_parse_count_normalization() -> None:
    assert parse_count("249.7K") == 249700
    assert parse_count("1.2M") == 1200000
    assert parse_count("71") == 71


def test_parse_skill_page_with_skill_md_fixture() -> None:
    html = (FIXTURES / "skills_sh_skill_with_md.html").read_text(encoding="utf-8")
    page_url = "https://skills.sh/21st-dev/magic-mcp/react:components"
    record = parse_skill_page(page_url, html)

    assert record["owner"] == "21st-dev"
    assert record["repo"] == "magic-mcp"
    assert record["skill_slug"] == "react:components"
    assert record["install_command"] == "$ npx skills add github:21st-dev/magic-mcp --skill react:components"
    assert record["weekly_installs"] == 249700
    assert record["first_seen_date"] == "2026-01-26"
    assert record["repository_url"] == "https://github.com/21st-dev/magic-mcp"
    assert record["installed_on"] == {"codex": 216800, "cursor": 54500}
    assert "# React Components" in record["skill_md_rendered"]
    assert "Use Tailwind CSS" in record["skill_md_rendered"]
    assert "https://react.dev" in record["extracted_links"]


def test_parse_skill_page_no_skill_md_fixture() -> None:
    html = (FIXTURES / "skills_sh_skill_no_md.html").read_text(encoding="utf-8")
    page_url = "https://skills.sh/owner/repo/no-skill"
    record = parse_skill_page(page_url, html)

    assert record["owner"] == "owner"
    assert record["repo"] == "repo"
    assert record["skill_slug"] == "no-skill"
    assert record["skill_md_rendered"] == "No SKILL.md available for this skill."
    assert record["weekly_installs"] == 0
    assert record["first_seen_date"] == "2026-02-01"
    assert record["installed_on"] == {}


def test_parse_skill_page_installed_on_split_lines_fixture() -> None:
    html = (FIXTURES / "skills_sh_installed_on_split_lines.html").read_text(
        encoding="utf-8"
    )
    page_url = "https://skills.sh/owner/repo/demo"
    record = parse_skill_page(page_url, html)

    assert record["installed_on"] == {"gemini-cli": 4200, "codex": 3600}
