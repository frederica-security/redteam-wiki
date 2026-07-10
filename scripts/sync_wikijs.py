#!/usr/bin/env python3
"""Create a maintainable MkDocs mirror from the public Wiki.js frontend."""

from __future__ import annotations

import argparse
import base64
import hashlib
import html
import json
import os
import re
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Iterable
from urllib.parse import quote, unquote, urljoin, urlsplit

import requests
from bs4 import BeautifulSoup, NavigableString, Tag


ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
ARCHIVE = ROOT / "archive" / "raw"
STATE_FILE = ROOT / ".wikijs-sync" / "state.json"
MKDOCS_FILE = ROOT / "mkdocs.yml"
DEFAULT_SOURCE = "https://redteam-wiki.org"
EXCLUDED_PAGES = {"en/Introduction", "en/quick-start"}
CONVERTER_VERSION = 4
AUTO_NAV_START = "  # BEGIN AUTO NAV"
AUTO_NAV_END = "  # END AUTO NAV"

PAGE_LIST_QUERY = """
query BackupPages {
  pages {
    list(orderBy: PATH) {
      id path locale title description isPublished isPrivate createdAt updatedAt
    }
  }
}
"""

ASSET_FOLDERS_QUERY = """
query BackupFolders($parent: Int!) {
  assets { folders(parentFolderId: $parent) { id slug name } }
}
"""

ASSET_LIST_QUERY = """
query BackupAssets($folder: Int!) {
  assets {
    list(folderId: $folder, kind: ALL) {
      id filename ext kind mime fileSize createdAt updatedAt
      folder { id slug name }
    }
  }
}
"""


class SyncError(RuntimeError):
    pass


@dataclass(frozen=True)
class PageSnapshot:
    key: str
    route: str
    doc_path: str
    title: str
    metadata: dict
    raw_html: bytes
    fragment_html: str
    markdown: str
    upstream_hash: str
    raw_hash: str


@dataclass(frozen=True)
class AssetSnapshot:
    source_path: str
    doc_path: str
    metadata: dict
    content: bytes
    sha256: str


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_text(value: str) -> str:
    return sha256_bytes(value.encode("utf-8"))


def json_hash(value: object) -> str:
    return sha256_text(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")))


def file_hash(path: Path) -> str | None:
    return sha256_bytes(path.read_bytes()) if path.is_file() else None


def atomic_write(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as tmp:
        tmp.write(content)
        tmp_path = Path(tmp.name)
    os.replace(tmp_path, path)


def write_text(path: Path, content: str) -> None:
    atomic_write(path, content.encode("utf-8"))


def load_state() -> dict:
    if not STATE_FILE.exists():
        return {"version": 1, "source": DEFAULT_SOURCE, "pages": {}, "assets": {}}
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SyncError(f"无法读取同步状态 {STATE_FILE}: {exc}") from exc


class WikiClient:
    def __init__(self, base_url: str, timeout: float = 30.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "RedteamWikiStaticBackup/1.0"})

    def graphql(self, query: str, variables: dict | None = None) -> dict:
        try:
            response = self.session.post(
                f"{self.base_url}/graphql",
                json={"query": query, "variables": variables or {}},
                timeout=self.timeout,
            )
            response.raise_for_status()
            payload = response.json()
        except (requests.RequestException, ValueError) as exc:
            raise SyncError(f"GraphQL 请求失败: {exc}") from exc
        if payload.get("errors"):
            raise SyncError(f"GraphQL 返回错误: {payload['errors']}")
        return payload["data"]

    def get(self, path: str) -> bytes:
        url = urljoin(f"{self.base_url}/", path.lstrip("/"))
        try:
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
        except requests.RequestException as exc:
            raise SyncError(f"抓取 {url} 失败: {exc}") from exc
        return response.content


def page_key(item: dict) -> str:
    return f"{item['locale']}/{item['path']}"


def page_route(item: dict) -> str:
    if item["path"] == "home":
        return "/"
    return f"/{item['locale']}/{item['path']}"


def page_doc_path(item: dict) -> str:
    if item["path"] == "home":
        return "index.md"
    return f"{item['locale']}/{item['path']}.md"


def extract_page(raw: bytes, item: dict) -> tuple[str, dict]:
    text = raw.decode("utf-8", errors="replace")
    page_match = re.search(r"<page\b([^>]*)>", text, re.DOTALL)
    content_match = re.search(
        r'<template slot="contents"><div>(.*?)</div></template>', text, re.DOTALL
    )
    if not page_match or not content_match:
        raise SyncError(f"页面 {page_key(item)} 不包含预期的 Wiki.js 正文结构")

    attributes: dict[str, str] = {}
    for match in re.finditer(r'([:\w-]+)="([^"]*)"', page_match.group(1)):
        attributes[match.group(1)] = html.unescape(match.group(2))

    metadata = {
        "id": item["id"],
        "path": item["path"],
        "locale": item["locale"],
        "title": item["title"],
        "description": item.get("description") or "",
        "createdAt": item.get("createdAt"),
        "updatedAt": item.get("updatedAt"),
        "authorName": attributes.get("author-name", ""),
        "editor": attributes.get("editor", ""),
        "filename": attributes.get("filename", ""),
    }
    return content_match.group(1), metadata


def yaml_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


class HtmlToMarkdown:
    def __init__(self, base_url: str, current_doc: str, page_docs: dict[str, str], assets: dict[str, str]):
        self.base_url = base_url.rstrip("/")
        self.host = (urlsplit(base_url).hostname or "").lower()
        self.current_doc = PurePosixPath(current_doc)
        self.page_docs = page_docs
        self.assets = assets

    def convert(self, fragment: str) -> str:
        soup = BeautifulSoup(f"<div id='backup-root'>{fragment}</div>", "html.parser")
        root = soup.find(id="backup-root")
        assert isinstance(root, Tag)
        self.valid_anchors = {tag.get("id") for tag in root.find_all(id=True)}
        body = "".join(self.block(child, 0) for child in root.children)
        body = re.sub(r"[ \t]+\n", "\n", body)
        body = re.sub(r"\n{3,}", "\n\n", body).strip()
        return body + "\n"

    def relative_doc_link(self, target_doc: str) -> str:
        current_dir = str(self.current_doc.parent)
        start = current_dir if current_dir != "." else "."
        relative = os.path.relpath(target_doc, start=start).replace("\\", "/")
        return relative

    def rewrite_href(self, href: str) -> str:
        href = html.unescape(href).strip()
        if href.startswith("#"):
            return href if unquote(href[1:]) in self.valid_anchors else ""
        if not href or href.startswith(("mailto:", "tel:", "javascript:", "data:")):
            return href
        absolute = urljoin(f"{self.base_url}/", href)
        parsed = urlsplit(absolute)
        if (parsed.hostname or "").lower() != self.host:
            return href

        path = unquote(parsed.path).rstrip("/") or "/"
        if path == "/privilege-escalation":
            path = "/en/privilege-escalation"
        target = self.page_docs.get(path)
        if not target:
            return href
        result = self.relative_doc_link(target)
        if parsed.query:
            result += f"?{parsed.query}"
        if parsed.fragment:
            result += f"#{unquote(parsed.fragment)}"
        return result

    def image_target(self, src: str) -> str:
        absolute = urljoin(f"{self.base_url}/", html.unescape(src).strip())
        parsed = urlsplit(absolute)
        if (parsed.hostname or "").lower() != self.host:
            return src
        source_path = quote(unquote(parsed.path), safe="/%")
        target = self.assets.get(source_path) or self.assets.get(unquote(parsed.path))
        return self.relative_doc_link(target) if target else src

    @staticmethod
    def clean_inline(value: str) -> str:
        value = re.sub(r"[ \t\r\f\v]+", " ", value)
        value = re.sub(r" *\n *", " ", value)
        return value

    def clean_text_node(self, value: str) -> str:
        value = self.clean_inline(value)

        def replace_residual_link(match: re.Match[str]) -> str:
            label, target = match.group(1), match.group(2)
            if target.startswith("#") and unquote(target[1:]) not in self.valid_anchors:
                return label
            return match.group(0)

        return re.sub(r"\[([^\]]+)\]\(([^)]+)\)", replace_residual_link, value)

    def inline_children(self, tag: Tag) -> str:
        return "".join(self.inline(child) for child in tag.children)

    def inline(self, node) -> str:
        if isinstance(node, NavigableString):
            return self.clean_text_node(str(node))
        if not isinstance(node, Tag):
            return ""
        name = node.name.lower()
        if name == "a":
            if "toc-anchor" in (node.get("class") or []):
                return ""
            label = self.inline_children(node).strip() or node.get("href", "")
            href = self.rewrite_href(node.get("href", ""))
            title = node.get("title")
            suffix = f' "{title}"' if title else ""
            return f"[{label}]({href}{suffix})" if href else label
        if name in {"strong", "b"}:
            value = self.inline_children(node).strip()
            return f"**{value}**" if value else ""
        if name in {"em", "i"}:
            value = self.inline_children(node).strip()
            return f"*{value}*" if value else ""
        if name in {"s", "del", "strike"}:
            return f"~~{self.inline_children(node).strip()}~~"
        if name == "code":
            value = node.get_text()
            fence = "`" * (max([len(x) for x in re.findall(r"`+", value)] or [0]) + 1)
            if value.startswith("`") or value.endswith("`"):
                value = f" {value} "
            return f"{fence}{value}{fence}"
        if name == "br":
            return "<br>"
        if name == "img":
            target = self.image_target(node.get("src", ""))
            alt = node.get("alt", "")
            title = f' "{node.get("title")}"' if node.get("title") else ""
            return f"![{alt}]({target}{title})"
        if name == "span" and "katex" in (node.get("class") or []):
            return self.math(node)
        if name == "math":
            return self.math(node)
        return self.inline_children(node)

    def math(self, node: Tag) -> str:
        annotation = node.find("annotation")
        if annotation:
            tex = annotation.get_text(strip=True)
        else:
            math_tag = node if node.name == "math" else node.find("math")
            raw = math_tag.get_text("", strip=True) if math_tag else node.get_text("", strip=True)
            tex_match = re.search(r"(\\[A-Za-z]+(?:\{[^}]*\})?)$", raw)
            tex = tex_match.group(1) if tex_match else raw
        return f"${tex}$" if tex else ""

    def block(self, node, depth: int) -> str:
        if isinstance(node, NavigableString):
            value = self.clean_inline(str(node)).strip()
            return f"{value}\n\n" if value else ""
        if not isinstance(node, Tag):
            return ""
        name = node.name.lower()
        if re.fullmatch(r"h[1-6]", name):
            level = int(name[1])
            title = self.inline_children(node).strip()
            ident = node.get("id")
            suffix = f" {{#{ident}}}" if ident else ""
            return f"{'#' * level} {title}{suffix}\n\n"
        if name == "p":
            value = self.inline_children(node).strip()
            return f"{value}\n\n" if value and value != "&nbsp;" else ""
        if name == "pre":
            code = node.find("code")
            value = code.get_text() if code else node.get_text()
            classes = code.get("class", []) if code else []
            language = next((c[9:] for c in classes if c.startswith("language-") and c[9:]), "text")
            language = {"cmd": "batch", "plaintext": "text"}.get(language, language)
            longest = max([len(x) for x in re.findall(r"`+", value)] or [0])
            fence = "`" * max(3, longest + 1)
            return f"{fence}{language}\n{value.rstrip()}\n{fence}\n\n"
        if name in {"ul", "ol"}:
            return self.list_block(node, depth) + "\n\n"
        if name == "blockquote":
            content = "".join(self.block(child, depth) for child in node.children).strip()
            return "\n".join(f"> {line}" if line else ">" for line in content.splitlines()) + "\n\n"
        if name == "table":
            return self.table(node)
        if name == "hr":
            return "---\n\n"
        if name == "figure":
            image = node.find("img")
            if not image:
                return ""
            rendered = self.inline(image)
            width = ""
            match = re.search(r"width\s*:\s*([^;]+)", node.get("style", ""), re.I)
            if match:
                width = f'{{ width="{match.group(1).strip()}" }}'
            caption = node.find("figcaption")
            extra = f"\n*{self.inline_children(caption).strip()}*" if caption else ""
            return f"{rendered}{width}{extra}\n\n"
        if name in {"div", "section", "article", "main", "body"}:
            return "".join(self.block(child, depth) for child in node.children)
        if name in {"script", "style", "comments"}:
            return ""
        value = self.inline(node).strip()
        return f"{value}\n\n" if value else ""

    def list_block(self, tag: Tag, depth: int) -> str:
        ordered = tag.name.lower() == "ol"
        start = int(tag.get("start", 1)) if str(tag.get("start", "1")).isdigit() else 1
        lines: list[str] = []
        items = tag.find_all("li", recursive=False)
        for index, item in enumerate(items):
            marker = f"{start + index}." if ordered else "-"
            inline_parts: list[str] = []
            nested: list[Tag] = []
            for child in item.children:
                if isinstance(child, Tag) and child.name.lower() in {"ul", "ol"}:
                    nested.append(child)
                elif isinstance(child, Tag) and child.name.lower() in {"p", "div"}:
                    inline_parts.append(self.inline_children(child))
                else:
                    inline_parts.append(self.inline(child))
            value = self.clean_inline("".join(inline_parts)).strip()
            indent = "    " * depth
            lines.append(f"{indent}{marker} {value}")
            for child in nested:
                lines.extend(self.list_block(child, depth + 1).splitlines())
        return "\n".join(lines)

    def table(self, tag: Tag) -> str:
        rows: list[list[str]] = []
        aligns: list[str] = []
        for row in tag.find_all("tr"):
            cells = row.find_all(["th", "td"], recursive=False)
            if not cells:
                continue
            rendered: list[str] = []
            for cell in cells:
                value = self.inline_children(cell).strip().replace("\n", " ")
                value = re.sub(r"(?<!\\)\|", r"\\|", value)
                rendered.append(value or " ")
                if len(rows) == 0:
                    style = cell.get("style", "").lower()
                    align = (cell.get("align") or "").lower()
                    if "text-align:center" in style.replace(" ", "") or align == "center":
                        aligns.append(":---:")
                    elif "text-align:right" in style.replace(" ", "") or align == "right":
                        aligns.append("---:")
                    else:
                        aligns.append("---")
            rows.append(rendered)
        if not rows:
            return ""
        width = max(len(row) for row in rows)
        rows = [row + [" "] * (width - len(row)) for row in rows]
        aligns += ["---"] * (width - len(aligns))
        output = ["| " + " | ".join(rows[0]) + " |", "| " + " | ".join(aligns) + " |"]
        output.extend("| " + " | ".join(row) + " |" for row in rows[1:])
        return "\n".join(output) + "\n\n"


def fetch_assets(client: WikiClient) -> list[AssetSnapshot]:
    result: list[AssetSnapshot] = []
    queue: list[tuple[int, PurePosixPath]] = [(0, PurePosixPath("."))]
    seen: set[int] = set()
    while queue:
        folder_id, folder_path = queue.pop(0)
        if folder_id in seen:
            continue
        seen.add(folder_id)
        folders = client.graphql(ASSET_FOLDERS_QUERY, {"parent": folder_id})["assets"]["folders"]
        for folder in folders:
            queue.append((folder["id"], folder_path / folder["slug"]))
        assets = client.graphql(ASSET_LIST_QUERY, {"folder": folder_id})["assets"]["list"] or []
        for item in assets:
            relative = (folder_path / item["filename"]).as_posix().lstrip("./")
            source_path = "/" + quote(relative, safe="/")
            content = client.get(source_path)
            if len(content) != item["fileSize"]:
                raise SyncError(
                    f"资源 {source_path} 大小不符：接口为 {item['fileSize']}，实际为 {len(content)}"
                )
            result.append(
                AssetSnapshot(
                    source_path=source_path,
                    doc_path=f"assets/media/{relative}",
                    metadata=item,
                    content=content,
                    sha256=sha256_bytes(content),
                )
            )
    return sorted(result, key=lambda item: item.source_path)


def fetch_navigation(raw_home: bytes) -> list[dict]:
    text = raw_home.decode("utf-8", errors="replace")
    match = re.search(r'\bsidebar="([^"]+)"', text)
    if not match:
        raise SyncError("首页不包含 Wiki.js 侧栏数据")
    try:
        return json.loads(base64.b64decode(html.unescape(match.group(1))).decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as exc:
        raise SyncError(f"无法解析侧栏数据: {exc}") from exc


def build_nav(sidebar: list[dict], pages: dict[str, PageSnapshot]) -> str:
    route_to_page = {page.route.rstrip("/") or "/": page for page in pages.values()}
    lines = [AUTO_NAV_START]
    appendix: list[tuple[str, str]] = []
    in_appendix = False
    included: set[str] = set()
    for item in sidebar:
        if item.get("k") != "link":
            continue
        label = item.get("l") or ""
        target = item.get("t") or ""
        if label == "附录" and not target:
            in_appendix = True
            continue
        if not target.startswith("/"):
            continue
        route = unquote(target).rstrip("/") or "/"
        page = route_to_page.get(route)
        if not page:
            continue
        included.add(page.key)
        nav_item = (label or page.title, page.doc_path)
        if in_appendix:
            appendix.append(nav_item)
        else:
            lines.append(f"  - {yaml_string(nav_item[0])}: {yaml_string(nav_item[1])}")

    unclassified = sorted((page for key, page in pages.items() if key not in included), key=lambda p: p.title)
    if appendix:
        lines.append('  - "附录":')
        lines.extend(f"      - {yaml_string(label)}: {yaml_string(path)}" for label, path in appendix)
    if unclassified:
        lines.append('  - "未分类":')
        lines.extend(f"      - {yaml_string(page.title)}: {yaml_string(page.doc_path)}" for page in unclassified)
    lines.append(AUTO_NAV_END)
    return "\n".join(lines)


def replace_auto_nav(config: str, nav: str) -> str:
    pattern = re.compile(re.escape(AUTO_NAV_START) + r".*?" + re.escape(AUTO_NAV_END), re.DOTALL)
    if not pattern.search(config):
        raise SyncError("mkdocs.yml 缺少自动导航标记")
    return pattern.sub(nav, config)


def build_snapshots(client: WikiClient) -> tuple[dict[str, PageSnapshot], list[AssetSnapshot], list[dict]]:
    data = client.graphql(PAGE_LIST_QUERY)["pages"]["list"]
    public = [item for item in data if item["isPublished"] and not item["isPrivate"]]
    found_excluded = EXCLUDED_PAGES & {page_key(item) for item in public}
    if found_excluded != EXCLUDED_PAGES:
        missing = ", ".join(sorted(EXCLUDED_PAGES - found_excluded))
        raise SyncError(f"已确认排除的测试页发生变化或消失，请复核: {missing}")
    selected = [item for item in public if page_key(item) not in EXCLUDED_PAGES]
    if not selected:
        raise SyncError("没有发现可发布页面")

    raw_pages: dict[str, bytes] = {}
    fragments: dict[str, tuple[str, dict]] = {}
    for item in selected:
        key = page_key(item)
        raw_pages[key] = client.get(page_route(item))
        fragments[key] = extract_page(raw_pages[key], item)

    assets = fetch_assets(client)
    asset_map: dict[str, str] = {}
    for asset in assets:
        asset_map[asset.source_path] = asset.doc_path
        asset_map[unquote(asset.source_path)] = asset.doc_path

    page_docs: dict[str, str] = {}
    for item in selected:
        route = page_route(item).rstrip("/") or "/"
        page_docs[route] = page_doc_path(item)
        if item["path"] != "home":
            page_docs[f"/{item['path']}"] = page_doc_path(item)

    pages: dict[str, PageSnapshot] = {}
    for item in selected:
        key = page_key(item)
        fragment, metadata = fragments[key]
        doc_path = page_doc_path(item)
        converter = HtmlToMarkdown(client.base_url, doc_path, page_docs, asset_map)
        body = converter.convert(fragment)
        if not re.search(r"^# ", body, re.MULTILINE):
            body = f"# {item['title']}\n\n{body}"
        route = page_route(item)
        front_matter = "\n".join(
            [
                "---",
                f"title: {yaml_string(item['title'])}",
                f"description: {yaml_string(item.get('description') or '')}",
                f"source_url: {yaml_string(client.base_url + route)}",
                f"created_at: {yaml_string(item.get('createdAt') or '')}",
                f"updated_at: {yaml_string(item.get('updatedAt') or '')}",
                f"author: {yaml_string(metadata.get('authorName') or '')}",
                "---",
                "",
            ]
        )
        markdown = front_matter + body
        upstream_hash = json_hash(
            {"converter_version": CONVERTER_VERSION, "metadata": metadata, "fragment": fragment}
        )
        pages[key] = PageSnapshot(
            key=key,
            route=route,
            doc_path=doc_path,
            title=item["title"],
            metadata=metadata,
            raw_html=raw_pages[key],
            fragment_html=fragment,
            markdown=markdown,
            upstream_hash=upstream_hash,
            raw_hash=sha256_bytes(raw_pages[key]),
        )

    home = next((raw_pages[key] for key, page in pages.items() if page.route == "/"), None)
    if home is None:
        raise SyncError("页面清单中缺少首页")
    navigation = fetch_navigation(home)
    return pages, assets, navigation


def page_status(page: PageSnapshot, previous: dict | None) -> tuple[bool, bool, str | None]:
    path = DOCS / page.doc_path
    current_hash = file_hash(path)
    if not previous:
        return True, False, current_hash
    local_modified = current_hash is not None and current_hash != previous.get("generated_hash")
    upstream_changed = page.upstream_hash != previous.get("upstream_hash")
    return upstream_changed, local_modified, current_hash


def asset_status(asset: AssetSnapshot, previous: dict | None) -> tuple[bool, bool, str | None]:
    path = DOCS / asset.doc_path
    current_hash = file_hash(path)
    if not previous:
        return True, False, current_hash
    local_modified = current_hash is not None and current_hash != previous.get("generated_hash")
    upstream_changed = asset.sha256 != previous.get("upstream_hash")
    return upstream_changed, local_modified, current_hash


def report_inventory(pages: dict[str, PageSnapshot], assets: list[AssetSnapshot]) -> None:
    code_blocks = sum(len(re.findall(r"<pre\b", page.fragment_html, re.I)) for page in pages.values())
    tables = sum(len(re.findall(r"<table\b", page.fragment_html, re.I)) for page in pages.values())
    image_refs = sum(len(re.findall(r"<img\b", page.fragment_html, re.I)) for page in pages.values())
    total_assets = sum(len(asset.content) for asset in assets)
    print(
        f"上游清单：{len(pages)} 个发布页面，{len(assets)} 个资源，"
        f"{code_blocks} 个代码块，{tables} 个表格，{image_refs} 个图片引用，"
        f"资源共 {total_assets / 1024 / 1024:.2f} MiB"
    )


def check_changes(pages: dict[str, PageSnapshot], assets: list[AssetSnapshot], state: dict) -> int:
    changes = 0
    conflicts = 0
    previous_pages = state.get("pages", {})
    previous_assets = state.get("assets", {})
    for key, page in sorted(pages.items()):
        upstream, local, current = page_status(page, previous_pages.get(key))
        if not previous_pages.get(key):
            print(f"NEW page {key}")
            changes += 1
        elif upstream and local:
            print(f"CONFLICT page {key}: 上游与本地都已修改")
            changes += 1
            conflicts += 1
        elif upstream:
            print(f"UPDATE page {key}")
            changes += 1
        elif local:
            print(f"LOCAL page {key}: 保留本地修改")
        elif current is None:
            print(f"MISSING page {key}: 本地文件缺失")
            changes += 1
    for key in sorted(set(previous_pages) - set(pages)):
        print(f"DELETED-UPSTREAM page {key}: 不自动删除本地文件")
        changes += 1

    current_assets = {asset.source_path: asset for asset in assets}
    for key, asset in sorted(current_assets.items()):
        upstream, local, current = asset_status(asset, previous_assets.get(key))
        if not previous_assets.get(key):
            print(f"NEW asset {key}")
            changes += 1
        elif upstream and local:
            print(f"CONFLICT asset {key}: 上游与本地都已修改")
            changes += 1
            conflicts += 1
        elif upstream:
            print(f"UPDATE asset {key}")
            changes += 1
        elif local:
            print(f"LOCAL asset {key}: 保留本地修改")
        elif current is None:
            print(f"MISSING asset {key}: 本地文件缺失")
            changes += 1
    for key in sorted(set(previous_assets) - set(current_assets)):
        print(f"DELETED-UPSTREAM asset {key}: 不自动删除本地文件")
        changes += 1
    if not changes:
        print("同步检查完成：上游没有需要应用的变化。")
    else:
        print(f"同步检查完成：发现 {changes} 项变化，其中 {conflicts} 项冲突。")
    return 2 if conflicts else (1 if changes else 0)


def sync(
    pages: dict[str, PageSnapshot],
    assets: list[AssetSnapshot],
    navigation: list[dict],
    state: dict,
    accepted: set[str],
) -> int:
    previous_pages = state.get("pages", {})
    previous_assets = state.get("assets", {})
    snapshot_hash = json_hash(
        {
            "pages": {key: page.upstream_hash for key, page in sorted(pages.items())},
            "assets": {asset.source_path: asset.sha256 for asset in assets},
        }
    )
    generated_at = (
        state.get("generated_at")
        if state.get("snapshot_hash") == snapshot_hash and state.get("generated_at")
        else datetime.now(timezone.utc).isoformat()
    )
    next_state = {
        "version": 1,
        "source": state.get("source", DEFAULT_SOURCE),
        "converter_version": CONVERTER_VERSION,
        "snapshot_hash": snapshot_hash,
        "generated_at": generated_at,
        "pages": dict(previous_pages),
        "assets": dict(previous_assets),
    }
    conflicts: list[str] = []

    archive_manifest = {
        "source": state.get("source", DEFAULT_SOURCE),
        "captured_at": generated_at,
        "excluded_pages": sorted(EXCLUDED_PAGES),
        "pages": {},
        "assets": {},
    }

    for key, page in sorted(pages.items()):
        previous = previous_pages.get(key)
        upstream_changed, local_modified, _ = page_status(page, previous)
        accept = key in accepted or page.doc_path.removesuffix(".md") in accepted
        archive_path = ARCHIVE / "pages" / ("home.html" if page.route == "/" else f"{key}.html")
        atomic_write(archive_path, page.raw_html)
        archive_manifest["pages"][key] = {
            **page.metadata,
            "route": page.route,
            "archive_path": archive_path.relative_to(ROOT).as_posix(),
            "raw_sha256": page.raw_hash,
            "content_sha256": page.upstream_hash,
        }

        if previous and upstream_changed and local_modified and not accept:
            conflicts.append(f"page {key}")
            print(f"CONFLICT page {key}: 保留本地 Markdown；已保存最新原始快照")
            continue
        if previous and local_modified and not accept:
            print(f"LOCAL page {key}: 保留本地 Markdown")
            continue
        if upstream_changed or not (DOCS / page.doc_path).is_file() or accept:
            write_text(DOCS / page.doc_path, page.markdown)
            print(f"WRITE page {key}")
        generated_hash = file_hash(DOCS / page.doc_path)
        next_state["pages"][key] = {
            "route": page.route,
            "doc_path": page.doc_path,
            "upstream_hash": page.upstream_hash,
            "raw_hash": page.raw_hash,
            "generated_hash": generated_hash,
            "updated_at": page.metadata.get("updatedAt"),
        }

    current_assets = {asset.source_path: asset for asset in assets}
    for key, asset in sorted(current_assets.items()):
        previous = previous_assets.get(key)
        upstream_changed, local_modified, _ = asset_status(asset, previous)
        accept = key in accepted or asset.doc_path in accepted
        if previous and upstream_changed and local_modified and not accept:
            conflicts.append(f"asset {key}")
            print(f"CONFLICT asset {key}: 保留本地资源")
            continue
        if previous and local_modified and not accept:
            print(f"LOCAL asset {key}: 保留本地资源")
            continue
        if upstream_changed or not (DOCS / asset.doc_path).is_file() or accept:
            atomic_write(DOCS / asset.doc_path, asset.content)
            print(f"WRITE asset {key}")
        generated_hash = file_hash(DOCS / asset.doc_path)
        next_state["assets"][key] = {
            "doc_path": asset.doc_path,
            "upstream_hash": asset.sha256,
            "generated_hash": generated_hash,
            "file_size": len(asset.content),
            "mime": asset.metadata.get("mime"),
            "updated_at": asset.metadata.get("updatedAt"),
        }
        archive_manifest["assets"][key] = next_state["assets"][key]

    deleted_pages = sorted(set(previous_pages) - set(pages))
    deleted_assets = sorted(set(previous_assets) - set(current_assets))
    for key in deleted_pages:
        print(f"DELETED-UPSTREAM page {key}: 本地文件未删除")
    for key in deleted_assets:
        print(f"DELETED-UPSTREAM asset {key}: 本地文件未删除")

    nav = build_nav(navigation, pages)
    write_text(MKDOCS_FILE, replace_auto_nav(MKDOCS_FILE.read_text(encoding="utf-8"), nav))
    write_text(ARCHIVE / "manifest.json", json.dumps(archive_manifest, ensure_ascii=False, indent=2) + "\n")
    write_text(STATE_FILE, json.dumps(next_state, ensure_ascii=False, indent=2) + "\n")

    if conflicts:
        print("以下冲突需要人工处理或通过 --accept-upstream 明确接受：")
        for conflict in conflicts:
            print(f"  - {conflict}")
        return 2
    print(f"同步完成：{len(pages)} 个页面，{len(assets)} 个资源。")
    return 0


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("check", "sync"))
    parser.add_argument("--source", default=DEFAULT_SOURCE, help="Wiki.js 根地址")
    parser.add_argument("--timeout", type=float, default=30.0, help="单次 HTTP 请求超时秒数")
    parser.add_argument(
        "--accept-upstream",
        action="append",
        default=[],
        metavar="PAGE_OR_ASSET",
        help="允许旧 Wiki 覆盖指定本地页面或资源，可重复传入",
    )
    return parser.parse_args(argv)


def main(argv: Iterable[str] | None = None) -> int:
    args = parse_args(argv)
    state = load_state()
    if state.get("source") not in {None, args.source.rstrip("/")} and state.get("pages"):
        raise SyncError(
            f"同步状态属于 {state.get('source')}，不能直接改为 {args.source.rstrip('/')}"
        )
    state["source"] = args.source.rstrip("/")
    client = WikiClient(args.source, args.timeout)
    pages, assets, navigation = build_snapshots(client)
    report_inventory(pages, assets)
    if args.command == "check":
        return check_changes(pages, assets, state)
    return sync(pages, assets, navigation, state, set(args.accept_upstream))


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SyncError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(3)
