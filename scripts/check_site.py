#!/usr/bin/env python3
"""Validate internal links, assets, anchors and unwanted Wiki.js dependencies."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from urllib.parse import unquote, urljoin, urlsplit

from bs4 import BeautifulSoup


def route_for_file(root: Path, path: Path) -> str:
    relative = path.relative_to(root).as_posix()
    if relative == "index.html":
        return "/"
    if relative.endswith("/index.html"):
        return "/" + relative[: -len("index.html")]
    return "/" + relative


def resolve_target(root: Path, url_path: str) -> Path:
    decoded = unquote(url_path)
    relative = decoded.lstrip("/")
    candidate = root / relative
    if decoded.endswith("/") or not candidate.suffix:
        candidate = candidate / "index.html"
    return candidate


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("site", nargs="?", default="site")
    args = parser.parse_args()
    root = Path(args.site).resolve()
    if not root.is_dir():
        print(f"ERROR: 构建目录不存在: {root}", file=sys.stderr)
        return 2

    html_files = sorted(root.rglob("*.html"))
    errors: list[str] = []
    checked = 0
    parsed_cache: dict[Path, BeautifulSoup] = {}

    def soup_for(path: Path) -> BeautifulSoup:
        if path not in parsed_cache:
            parsed_cache[path] = BeautifulSoup(path.read_text(encoding="utf-8"), "html.parser")
        return parsed_cache[path]

    for source in html_files:
        soup = soup_for(source)
        route = route_for_file(root, source)
        for tag, attr in (("a", "href"), ("img", "src"), ("script", "src"), ("link", "href")):
            for node in soup.find_all(tag):
                if tag == "link" and "canonical" in (node.get("rel") or []):
                    continue
                value = (node.get(attr) or "").strip()
                if not value or value.startswith(("mailto:", "tel:", "javascript:", "data:")):
                    continue
                parsed = urlsplit(value)
                if parsed.scheme in {"http", "https"}:
                    if parsed.hostname == "redteam-wiki.org":
                        errors.append(f"{source.relative_to(root)}: 仍依赖旧站 URL {value}")
                    continue
                if parsed.scheme or value.startswith("//"):
                    continue
                absolute = urljoin(f"https://redteam-wiki.org{route}", value)
                target_url = urlsplit(absolute)
                target = resolve_target(root, target_url.path)
                checked += 1
                if not target.is_file():
                    errors.append(
                        f"{source.relative_to(root)}: {value} -> 缺少 {target.relative_to(root)}"
                    )
                    continue
                if target_url.fragment and target.suffix.lower() == ".html":
                    ids = {item.get("id") for item in soup_for(target).find_all(id=True)}
                    fragment = unquote(target_url.fragment)
                    if fragment not in ids:
                        errors.append(
                            f"{source.relative_to(root)}: {value} -> 缺少锚点 #{fragment}"
                        )

        source_text = source.read_text(encoding="utf-8")
        for forbidden in ("/graphql", "/_assets/js/", "/_assets/css/"):
            if forbidden in source_text:
                errors.append(f"{source.relative_to(root)}: 包含 Wiki.js 运行时依赖 {forbidden}")

    if errors:
        print(f"站点检查失败：{len(errors)} 个问题（检查 {checked} 个内部引用）")
        for error in errors[:200]:
            print(f"  - {error}")
        if len(errors) > 200:
            print(f"  ... 另有 {len(errors) - 200} 个问题")
        return 1
    print(f"站点检查通过：{len(html_files)} 个 HTML 文件，{checked} 个内部引用。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
