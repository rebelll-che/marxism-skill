"""Standalone navigation maintenance: real files, no application manifest."""
from pathlib import Path
import subprocess
import sys

import pytest


SCRIPT = Path(__file__).resolve().parents[1] / "tools/build_skill.py"


def snapshot(root):
    return {p.relative_to(root).as_posix(): p.read_bytes()
            for p in root.rglob("*") if p.is_file()}


def write_work(path, title="测试原著", author="原作者", body="# 原著\n\n原文。\n"):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes((f"---\ntitle: {title}\nauthors: [{author}]\nedition: 采用版本\n---\n" + body).encode())
    return path


@pytest.fixture
def skill(tmp_path):
    root = tmp_path / "marxism-sources"
    refs = root / "references"
    refs.mkdir(parents=True)
    (root / "SKILL.md").write_bytes(
        b"---\nname: marxism-sources\ndescription: Original sources\n---\n"
        b"[catalog](references/catalog.md)\n[guide](references/reading-guide.md)\n"
        b"[chapters](references/chapters.md)\n")
    (refs / "reading-guide.md").write_bytes("# 导读\n\n[章节](works/marx/first.md#原始章节)\n".encode())
    write_work(refs / "works/marx/first.md", "原著甲", "马克思",
               "# 原著甲\n\n## 原始章节\n\n完整原文。\n\n"
               "![公式](../../sources/公式 图.png)\n"
               '<table><tr><td><img src="../../checks/校对 页.png" /></td></tr></table>\n')
    write_work(refs / "works/engels/second.md", "原著乙", "恩格斯")
    for name, data in (("sources/公式 图.png", b"formula-bytes"),
                       ("checks/校对 页.png", b"page-image-bytes")):
        path = refs / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    return root


def run_cli(root, *extra, cwd=None):
    return subprocess.run([sys.executable, "-X", "utf8", str(SCRIPT),
                           "--skill-directory", str(root), *extra],
                          cwd=cwd or root.parent, capture_output=True, text=True,
                          encoding="utf-8", check=False)


def test_cli_builds_without_application_or_manifest(skill, tmp_path):
    before = snapshot(skill)
    result = run_cli(skill, cwd=tmp_path)
    assert result.returncode == 0, result.stderr
    assert "WORKS 2" in result.stdout and "ASSETS 2" in result.stdout
    after = snapshot(skill)
    assert set(after) - set(before) == {"references/catalog.md", "references/chapters.md"}
    assert all(after[path] == raw for path, raw in before.items())
    catalog = after["references/catalog.md"].decode()
    assert "原著甲" in catalog and "马克思" in catalog and "采用版本" in catalog
    assert "works/marx/first.md" in catalog and "works/engels/second.md" in catalog
    assert run_cli(skill, "--check").returncode == 0


def test_recursive_same_names_encoded_paths_and_table_cells(skill):
    from tools.build_skill import build_skill
    refs = skill / "references"
    (refs / "works/engels/second.md").unlink()
    write_work(refs / "works/engels/书 名.md", "同名|作品", "恩格斯")
    write_work(refs / "works/marx/书 名.md", "同名|作品", "马克思")
    result = build_skill(skill)
    assert result.work_count == 3
    catalog = (refs / "catalog.md").read_text(encoding="utf-8")
    assert "同名\\|作品" in catalog
    assert "works/engels/%E4%B9%A6%20%E5%90%8D.md" in catalog
    assert "works/marx/%E4%B9%A6%20%E5%90%8D.md" in catalog
    assert catalog.count("[章目](chapters.md#") == 3
    build_skill(skill, check=True)


@pytest.mark.parametrize("missing", ["sources/公式 图.png", "checks/校对 页.png"])
def test_missing_markdown_or_html_attachment_prevents_navigation_write(skill, missing):
    from tools.build_skill import build_skill
    build_skill(skill)
    (skill / "references" / missing).unlink()
    before = snapshot(skill)
    with pytest.raises((FileNotFoundError, ValueError), match="(?i)(missing|link|attachment)"):
        build_skill(skill)
    assert snapshot(skill) == before


@pytest.mark.parametrize("link", ["works/marx/missing.md", "works/marx/first.md#不存在的章", "../../outside.md"])
def test_invalid_guide_file_fragment_or_escape_does_not_write(skill, link):
    from tools.build_skill import build_skill
    build_skill(skill)
    (skill / "references/reading-guide.md").write_text(f"# 导读\n[原著]({link})\n", encoding="utf-8")
    before = snapshot(skill)
    with pytest.raises((ValueError, FileNotFoundError)):
        build_skill(skill)
    assert snapshot(skill) == before


def test_invalid_entry_link_prevents_navigation_write(skill):
    from tools.build_skill import build_skill
    with (skill / "SKILL.md").open("ab") as stream:
        stream.write(b"\n[missing](references/absent.md)\n")
    before = snapshot(skill)
    with pytest.raises((ValueError, FileNotFoundError)):
        build_skill(skill)
    assert snapshot(skill) == before


def test_missing_work_link_in_html_is_checked(skill):
    from tools.build_skill import build_skill
    work = skill / "references/works/marx/first.md"
    with work.open("ab") as stream:
        stream.write(b'\n<a href="other.md">other work</a>\n')
    before = snapshot(skill)
    with pytest.raises((ValueError, FileNotFoundError)):
        build_skill(skill)
    assert snapshot(skill) == before


def test_original_bom_crcrlf_lf_ranges_ancestry_and_code_fences(skill):
    from tools.build_skill import build_skill
    work = skill / "references/works/marx/first.md"
    header = "---\ntitle: 原著甲\nauthors: [原作者]\nedition: 采用版本\n---\n"
    body = ("# 原著甲\n## 正文\n### 第一章\n正文。\n```md\n## 不是章名\n```\n"
            "<h3>第二章\n<em>补充</em>[<sup>[1]</sup>](https://example.org/note)</h3>\n"
            "第二章正文。\n## 卷末注释\n### 第一章\n注释。\n")
    raw = (header.replace("\n", "\r\n") + body.replace("\n", "\r\r\n")).encode("utf-8-sig")
    work.write_bytes(raw)
    (skill / "references/reading-guide.md").write_bytes("# 导读\n".encode())
    build_skill(skill)
    chapters = (skill / "references/chapters.md").read_text(encoding="utf-8")
    assert "原著甲 > 正文 > 第一章 | 8–12" in chapters
    assert "原著甲 > 正文 > 第二章 补充[1] | 13–15" in chapters
    assert "原著甲 > 卷末注释 > 第一章 | 17–18" in chapters
    assert "不是章名" not in chapters
    assert "https://example.org/note" not in chapters
    assert work.read_bytes() == raw
    work.write_bytes(raw.replace("正文。".encode(), "新增。\n正文。".encode(), 1))
    build_skill(skill)
    assert "原著甲 > 正文 > 第二章 补充[1] | 14–16" in (skill / "references/chapters.md").read_text(encoding="utf-8")


def test_work_without_heading_has_full_text_range(skill):
    from tools.build_skill import build_skill
    write_work(skill / "references/works/engels/second.md", body="没有标题的原文。\n\n第二段。\n")
    build_skill(skill)
    assert "全文（无原文章名） | 6–8" in (skill / "references/chapters.md").read_text(encoding="utf-8")


@pytest.mark.parametrize("navigation", ["catalog.md", "chapters.md"])
def test_check_reports_stale_navigation_without_mutating_any_file(skill, navigation):
    from tools.build_skill import build_skill
    build_skill(skill)
    stale = skill / "references" / navigation
    stale.write_bytes(stale.read_bytes() + b"\nstale navigation\n")
    before = snapshot(skill)
    result = run_cli(skill, "--check")
    assert result.returncode != 0
    assert "outdated" in result.stderr.lower() and navigation in result.stderr
    assert snapshot(skill) == before
    build_skill(skill)
    assert run_cli(skill, "--check").returncode == 0


def test_check_missing_navigation_never_creates_it(skill):
    before = snapshot(skill)
    result = run_cli(skill, "--check")
    assert result.returncode != 0
    assert "outdated" in result.stderr.lower()
    assert snapshot(skill) == before


def test_source_changes_make_navigation_stale_and_refresh_preserves_new_source(skill):
    from tools.build_skill import build_skill
    build_skill(skill)
    new_work = write_work(skill / "references/works/marx/new.md", "新原著")
    new_bytes = new_work.read_bytes()
    before = snapshot(skill)
    assert run_cli(skill, "--check").returncode != 0
    assert snapshot(skill) == before
    assert build_skill(skill).work_count == 3
    assert new_work.read_bytes() == new_bytes


def test_maintenance_root_and_git_directory_are_never_replaced(skill):
    from tools.build_skill import build_skill
    (skill / ".git").mkdir()
    (skill / ".git/keep").write_bytes(b"keep repository data")
    marker = skill / "maintainer-notes.txt"
    marker.write_bytes(b"keep maintainer files")
    before = snapshot(skill)
    build_skill(skill)
    after = snapshot(skill)
    assert all(after[path] == raw for path, raw in before.items())
    assert marker.read_bytes() == b"keep maintainer files"


def test_empty_or_malformed_work_is_rejected_without_writes(skill):
    from tools.build_skill import build_skill
    work = skill / "references/works/marx/first.md"
    work.write_bytes(b"not a source with metadata\n")
    before = snapshot(skill)
    with pytest.raises(ValueError, match="(?i)(YAML|metadata|header)"):
        build_skill(skill)
    assert snapshot(skill) == before