"""Refresh only a standalone Skill's catalog and original-LF chapter directory.

No application manifest, database, network, model, or source rewriting is used.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from html import unescape
from pathlib import Path
import posixpath
import re
from urllib.parse import quote, unquote, urlsplit

import yaml


REPO = Path(__file__).resolve().parents[1]
DEFAULT_SKILL = REPO / "marxism-sources"
CATALOG_HEADER = "# 原著材料目录"
FRONTMATTER = re.compile(r"\A---\r?\n(.*?)\r?\n---[ \t]*(?:\r?\n|$)", re.S)
LINK = re.compile(r"!?\[[^\]\r\n]*\]\(([^)\r\n]+)\)")
HTML_LINK = re.compile(r'''<(?:a|img|source|audio|video|iframe|link)\b[^>]*?\b(?:href|src)\s*=\s*["']([^"']+)["'][^>]*>''', re.I)


@dataclass(frozen=True)
class BuildResult:
    folder: Path
    work_count: int
    asset_count: int
    changed: tuple[Path, ...]


def _read_metadata(raw: bytes, path: Path):
    text = raw.decode("utf-8-sig")
    match = FRONTMATTER.match(text)
    if match is None:
        raise ValueError(f"Material has no YAML header: {path}")
    metadata = yaml.safe_load(match[1])
    if not isinstance(metadata, dict) or not all(metadata.get(key) for key in ("title", "authors", "edition")):
        raise ValueError(f"Material needs title, authors and edition: {path}")
    return metadata, text[match.end():]

def _cell(value):
    if isinstance(value, list):
        value = "、".join(str(item) for item in value)
    return str(value).replace("|", "\\|").replace("\n", " ")


def _chapter_ranges(raw: bytes):
    """Use original LF positions, including frontmatter; never normalize source bytes."""
    text = raw.decode("utf-8-sig")
    lines = text.split("\n")
    if lines[-1] == "":
        lines.pop()
    frontmatter = FRONTMATTER.match(text)
    start = text.count("\n", 0, frontmatter.end()) if frontmatter else 0
    headings, stack = [], []
    fence = None
    index = start
    while index < len(lines):
        line = lines[index].rstrip("\r")
        marker = re.match(r"^ {0,3}(`{3,}|~{3,})", line)
        if fence:
            if re.fullmatch(r" {0,3}" + re.escape(fence[0]) + "{" + str(len(fence)) + r",}\s*", line):
                fence = None
            index += 1
            continue
        if marker:
            fence = marker[1]
            index += 1
            continue
        markdown = re.match(r"^ {0,3}(#{1,6})[ \t]+(.+?)\s*#*\s*$", line)
        html = re.match(r"^\s*<h([1-6])\b[^>]*>", line, re.I)
        heading_line = index + 1
        if markdown:
            level, title = len(markdown[1]), markdown[2]
        elif html:
            closing = re.compile(r"</h" + html[1] + r">", re.I)
            end = index
            while end < len(lines) and not closing.search(lines[end]):
                end += 1
            if end == len(lines):
                index += 1
                continue
            title = "\n".join(lines[index:end + 1])
            title = closing.split(title, maxsplit=1)[0][html.end():]
            level, index = int(html[1]), end
        else:
            index += 1
            continue
        title = re.sub(r"<br\s*/?>", " ", title, flags=re.I)
        title = re.sub(r"<[^>]+>", "", title)
        title = re.sub(r"!?\[(.*?)\]\([^)]+\)", r"\1", title)
        title = " ".join(unescape(title).split())
        while stack and stack[-1]["level"] >= level:
            stack.pop()["end"] = heading_line - 1
        path = " > ".join([item["title"] for item in stack] + [title])
        row = {"level": level, "title": title, "path": path, "start": heading_line, "end": len(lines)}
        headings.append(row)
        stack.append(row)
        index += 1
    return headings or [{"path": "全文（无原文章名）", "start": start + 1, "end": len(lines)}]


def _chapter_anchor(relative: Path):
    return quote(relative.as_posix(), safe="/._-")


def _chapter_directory(selected):
    lines = ["# 原文章目与文件行号", "", "自动从本包最终原文件生成；只用于定位，不是理论依据。先按作品路径或章名查找，勿整份加载。", "", "行号从文件第一行起按LF（与rg -n一致）计数，包含YAML头。范围截至下一同级或更高标题之前，父级包含子节；它用于缩小搜索，不要求整章通读。保留原有标题级别，未替作者重排结构。", ""]
    for relative, raw, meta, _body in selected:
        lines += [f'<a id="{_chapter_anchor(relative)}"></a>', f"## {_cell(meta['title'])}", "", f"文件：`{relative.as_posix()}` · [原文]({quote(relative.as_posix(), safe='/')})", "", "| 原有标题路径 | 文件行号范围 |", "| --- | --- |"]
        lines += [f"| {_cell(row['path'])} | {row['start']}–{row['end']} |" for row in _chapter_ranges(raw)]
        lines.append("")
    return "\n".join(lines)


def _catalog(selected):
    lines = [CATALOG_HEADER, "", "自动生成自本Skill的references/works下全部Markdown原著；请修改原著标准源后重新运行维护工具，不手工维护本目录。", "", f"本包包含 {len(selected)} 份马克思、恩格斯原著及相关文献，不代表完整收录马克思主义。", "", "原著正文、原有章节及元信息按原文件保留。来源、版本、原稿/修订等说明见各文件开头；整理检查记录不作为理论依据。用当前Agent自己的工具读取需要的章节，不必一次加载全库。正文和目录内链接均相对各自文件解析。头部source_file记录转换原件的位置，原件不随本包打包；需要对照来源时使用source字段已有的公共来源。", "", "| 作品 | 作者 | 采用版本 | 正文 | 章目 |", "| --- | --- | --- | --- | --- |"]
    for relative, _raw, meta, _body in selected:
        link = quote(relative.as_posix(), safe="/")
        chapter_link = "chapters.md#" + quote(_chapter_anchor(relative), safe="/._-")
        lines.append(f"| {_cell(meta['title'])} | {_cell(meta['authors'])} | {_cell(meta['edition'])} | [读取]({link}) | [章目]({chapter_link}) |")
    return "\n".join(lines) + "\n"


def local_links(relative: Path, body: str):
    """Resolve Markdown destinations and HTML file attributes from each file.

    Like the previous exporter, bare mathematical expressions such as [x](b)
    are not file references. URLs and source_file metadata are not attachments.
    """
    for link in dict.fromkeys(LINK.findall(body) + HTML_LINK.findall(body)):
        link = unescape(link.strip())
        # Markdown may enclose destinations in <> and add a quoted title.
        if link.startswith("<") and ">" in link:
            link = link[1:link.index(">")]
        else:
            link = re.sub(r'''\s+["'][^"']*["']\s*$''', "", link)
        if re.match(r"^[A-Za-z]:[/\\]", link):
            raise ValueError(f"Local link escapes Skill directory in {relative}: {link}")
        parsed = urlsplit(link)
        if parsed.scheme or parsed.netloc or not (parsed.path or parsed.fragment):
            continue
        decoded = unquote(parsed.path).replace("\\", "/")
        if decoded.startswith("/") or re.match(r"^[A-Za-z]:", decoded):
            raise ValueError(f"Local link escapes Skill directory in {relative}: {link}")
        path = Path(posixpath.normpath((relative.parent / decoded).as_posix())) if decoded else relative
        if ".." in path.parts:
            raise ValueError(f"Local link escapes Skill directory in {relative}: {link}")
        if not path.suffix:
            continue
        yield path, unquote(parsed.fragment), link


def _anchors(raw: bytes):
    text = raw.decode("utf-8-sig")
    anchors = set(re.findall(r'''\b(?:id|name)\s*=\s*["']([^"']+)["']''', text))
    counts = {}
    for heading in _chapter_ranges(raw):
        if "title" not in heading:
            continue
        slug = re.sub(r"[^\w -]", "", heading["title"].lower()).replace(" ", "-")
        count = counts.get(slug, 0)
        anchors.add(slug + (f"-{count}" if count else ""))
        counts[slug] = count + 1
    return anchors


def _validate_links(root: Path, relative: Path, body: str, generated: dict[Path, bytes], *, fragments: bool, anchor_cache: dict):
    targets = set()
    for path, fragment, link in local_links(relative, body):
        target = root / path
        if not target.resolve().is_relative_to(root):
            raise ValueError(f"Local link escapes Skill directory in {relative}: {link}")
        raw = generated.get(path)
        if raw is None and not target.is_file():
            raise FileNotFoundError(f"Missing file link or attachment in {relative}: {link}")
        if fragments and fragment:
            if path not in anchor_cache:
                anchor_cache[path] = _anchors(raw if raw is not None else target.read_bytes())
            if fragment not in anchor_cache[path]:
                raise ValueError(f"Chapter heading or anchor does not exist in {relative}: {link}")
        targets.add(path)
    return targets


def build_skill(skill_directory: Path = DEFAULT_SKILL, *, check: bool = False) -> BuildResult:
    """Validate all sources, then write only catalog.md and chapters.md.

    check=True compares current navigation bytes without creating or changing
    any file. Entry, guide, sources and attachments always remain untouched.
    """
    root = Path(skill_directory).resolve(strict=True)
    refs = root / "references"
    works = refs / "works"
    if not works.is_dir() or not works.resolve().is_relative_to(root):
        raise ValueError(f"Missing or unsafe original material directory: {works}")
    selected = []
    for source in sorted(works.rglob("*.md"), key=lambda path: path.relative_to(works).as_posix()):
        if source.is_symlink() or not source.resolve().is_relative_to(works.resolve()):
            raise ValueError(f"Original material must be a regular file within works/: {source}")
        raw = source.read_bytes()
        metadata, body = _read_metadata(raw, source)
        selected.append((source.relative_to(refs), raw, metadata, body))
    if not selected:
        raise ValueError("There are no original Markdown materials under references/works")

    generated = {
        Path("references/catalog.md"): _catalog(selected).encode("utf-8"),
        Path("references/chapters.md"): _chapter_directory(selected).encode("utf-8"),
    }
    for relative in generated:
        target = root / relative
        if target.is_symlink() or not target.resolve().is_relative_to(root):
            raise ValueError(f"Generated navigation must stay inside the Skill: {target}")
        if target.exists() and not target.is_file():
            raise ValueError(f"Generated navigation path is not a regular file: {target}")

    entry = (root / "SKILL.md").read_bytes()
    match = FRONTMATTER.match(entry.decode("utf-8-sig"))
    metadata = yaml.safe_load(match[1]) if match else None
    if not isinstance(metadata, dict) or not all(metadata.get(key) for key in ("name", "description")):
        raise ValueError("SKILL.md needs a YAML header containing name and description")
    guide = (refs / "reading-guide.md").read_bytes()
    anchor_cache = {}
    _validate_links(root, Path("SKILL.md"), entry.decode("utf-8-sig")[match.end():], generated,
                    fragments=True, anchor_cache=anchor_cache)
    _validate_links(root, Path("references/reading-guide.md"), guide.decode("utf-8-sig"), generated,
                    fragments=True, anchor_cache=anchor_cache)
    for relative, raw in generated.items():
        _validate_links(root, relative, raw.decode("utf-8"), generated,
                        fragments=True, anchor_cache=anchor_cache)
    originals = {Path("references") / relative for relative, *_rest in selected}
    assets = set()
    for relative, _raw, _meta, body in selected:
        targets = _validate_links(root, Path("references") / relative, body, generated,
                                  fragments=False, anchor_cache=anchor_cache)
        assets.update(targets - originals - set(generated) - {Path("references/reading-guide.md"), Path("SKILL.md")})

    changed = tuple(root / relative for relative, raw in generated.items()
                    if not (root / relative).is_file() or (root / relative).read_bytes() != raw)
    if check and changed:
        names = ", ".join(path.relative_to(root).as_posix() for path in changed)
        raise ValueError(f"Outdated navigation: {names}; run tools/build_skill.py to refresh")
    if not check:
        # No directory is replaced or removed, including maintenance repositories
        # and directories containing .git. The two generated files are the only writes.
        for relative, raw in generated.items():
            if root / relative in changed:
                (root / relative).write_bytes(raw)
    return BuildResult(root, len(selected), len(assets), changed)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skill-directory", type=Path, default=DEFAULT_SKILL)
    parser.add_argument("--check", action="store_true", help="validate without writing; fail if navigation is outdated")
    args = parser.parse_args(argv)
    try:
        result = build_skill(args.skill_directory, check=args.check)
    except (OSError, ValueError, KeyError, yaml.YAMLError, UnicodeError) as error:
        parser.exit(1, f"Build failed: {error}\n")
    print(f"SKILL {result.folder}\nWORKS {result.work_count} ASSETS {result.asset_count}\n"
          f"{'CHECK OK' if args.check else f'UPDATED {len(result.changed)}'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())