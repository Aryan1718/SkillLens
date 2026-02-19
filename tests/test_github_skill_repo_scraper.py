from __future__ import annotations

from server.fetchers.github_skill_repo_scraper import (
    decide_update_event,
    extract_paths_from_skill_md,
    locate_skill_md_path,
    sha256_text,
    should_skip_by_size,
)


def test_locate_skill_md_path_prefers_configured_pattern() -> None:
    tree_paths = {
        "README.md",
        "skills/my-skill/SKILL.md",
        "skills/other/SKILL.md",
    }
    found = locate_skill_md_path(tree_paths, "my-skill", repo_skill_count=2)
    assert found == "skills/my-skill/SKILL.md"


def test_locate_skill_md_path_fallback_by_parent_folder() -> None:
    tree_paths = {
        "README.md",
        "catalog/my-skill/skill.md",
        "catalog/other/SKILL.md",
    }
    found = locate_skill_md_path(tree_paths, "my-skill", repo_skill_count=2)
    assert found == "catalog/my-skill/skill.md"


def test_locate_skill_md_path_root_only_for_single_skill_repo() -> None:
    tree_paths = {"SKILL.md", "README.md"}
    found = locate_skill_md_path(tree_paths, "anything", repo_skill_count=1)
    assert found == "SKILL.md"

    not_found = locate_skill_md_path(tree_paths, "anything", repo_skill_count=2)
    assert not_found is None


def test_extract_paths_from_skill_md_relative_and_github_links() -> None:
    content = """
# Demo

See [config](./config/settings.yaml) and [script](../shared/build.py).
External link [blob](https://github.com/acme/demo/blob/main/skills/my-skill/run.sh)
Raw link: https://raw.githubusercontent.com/acme/demo/main/skills/my-skill/prompts/system.txt
Ignore other repo:
https://github.com/other/repo/blob/main/nope.py
```bash
python ./scripts/task.py
cat ../shared/policy.md
```
"""
    paths = extract_paths_from_skill_md(
        skill_md_content=content,
        owner="acme",
        repo="demo",
        skill_md_path="skills/my-skill/SKILL.md",
    )
    assert "skills/my-skill/config/settings.yaml" in paths
    assert "skills/shared/build.py" in paths
    assert "skills/my-skill/run.sh" in paths
    assert "skills/my-skill/prompts/system.txt" in paths
    assert "skills/my-skill/scripts/task.py" in paths
    assert "skills/shared/policy.md" in paths
    assert all("other/repo" not in path for path in paths)


def test_decide_update_event_flow() -> None:
    assert decide_update_event(None, "sha-a", {"a.py": "file-a"}) == "NEW"

    previous = {
        "skill_md_sha": "sha-a",
        "files": {"a.py": {"sha": "file-a"}, "b.py": {"sha": "file-b"}},
    }
    assert decide_update_event(previous, "sha-a", {"a.py": "file-a", "b.py": "file-b"}) == "UNCHANGED"
    assert decide_update_event(previous, "sha-b", {"a.py": "file-a", "b.py": "file-b"}) == "UPDATED"
    assert decide_update_event(previous, "sha-a", {"a.py": "file-a2", "b.py": "file-b"}) == "UPDATED_FILE"


def test_sha256_and_size_cap_helpers() -> None:
    value_hash = sha256_text("hello")
    assert len(value_hash) == 64
    assert value_hash == "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824"

    assert should_skip_by_size(100, 1_000_000) is False
    assert should_skip_by_size(1_000_001, 1_000_000) is True
