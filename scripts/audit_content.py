#!/usr/bin/env python3
"""Compare generated article structure and content with archived Wiki.js HTML."""

from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "archive" / "raw" / "pages"
SITE = ROOT / "site"


def normalized_code(value: str) -> list[str]:
    return [line.rstrip() for line in value.strip("\n").splitlines()]


def site_path(raw: Path) -> Path:
    relative = raw.relative_to(RAW).as_posix()
    if relative == "home.html":
        return SITE / "index.html"
    return SITE / relative.removesuffix(".html") / "index.html"


def main() -> int:
    errors: list[str] = []
    totals = {"pages": 0, "code": 0, "tables": 0, "images": 0, "lists": 0, "headings": 0}
    raw_files = sorted(RAW.rglob("*.html"))
    if not raw_files:
        print("ERROR: 未找到 archive/raw/pages 原始快照", file=sys.stderr)
        return 2

    for raw in raw_files:
        output = site_path(raw)
        if not output.is_file():
            errors.append(f"{raw.relative_to(RAW)}: 缺少构建页面 {output.relative_to(ROOT)}")
            continue
        source_text = raw.read_text(encoding="utf-8")
        match = re.search(
            r'<template slot="contents"><div>(.*?)</div></template>', source_text, re.DOTALL
        )
        if not match:
            errors.append(f"{raw.relative_to(RAW)}: 原始快照缺少正文")
            continue
        source = BeautifulSoup(match.group(1), "html.parser")
        generated_doc = BeautifulSoup(output.read_text(encoding="utf-8"), "html.parser")
        generated = generated_doc.select_one(".md-content__inner")
        if generated is None:
            errors.append(f"{output.relative_to(ROOT)}: 缺少文章容器")
            continue

        totals["pages"] += 1
        source_code = [normalized_code(tag.get_text()) for tag in source.find_all("pre")]
        generated_code = [normalized_code(tag.get_text()) for tag in generated.find_all("pre")]
        totals["code"] += len(source_code)
        if source_code != generated_code:
            errors.append(f"{raw.relative_to(RAW)}: 代码块文本或顺序不一致")

        source_cells = [tag.get_text(" ", strip=True) for tag in source.find_all(["th", "td"])]
        generated_cells = [tag.get_text(" ", strip=True) for tag in generated.find_all(["th", "td"])]
        totals["tables"] += len(source.find_all("table"))
        if source_cells != generated_cells:
            errors.append(f"{raw.relative_to(RAW)}: 表格单元格文本或顺序不一致")

        source_lists = len(source.find_all("li"))
        generated_lists = len(generated.find_all("li"))
        totals["lists"] += source_lists
        if source_lists != generated_lists:
            errors.append(
                f"{raw.relative_to(RAW)}: 列表项数量不一致 {source_lists} != {generated_lists}"
            )

        source_images = len(source.find_all("img"))
        generated_images = len(
            [tag for tag in generated.find_all("img") if "assets/media/" in tag.get("src", "")]
        )
        totals["images"] += source_images
        if source_images != generated_images:
            errors.append(
                f"{raw.relative_to(RAW)}: 正文图片数量不一致 {source_images} != {generated_images}"
            )

        source_ids = [
            tag.get("id")
            for tag in source.find_all(re.compile(r"^h[1-6]$"))
            if tag.get("id")
        ]
        generated_ids = {tag.get("id") for tag in generated.find_all(re.compile(r"^h[1-6]$"))}
        totals["headings"] += len(source_ids)
        missing_ids = [ident for ident in source_ids if ident not in generated_ids]
        if missing_ids:
            errors.append(
                f"{raw.relative_to(RAW)}: 丢失标题锚点 {', '.join(missing_ids[:5])}"
            )
        if generated.find("h1") is None:
            errors.append(f"{raw.relative_to(RAW)}: 生成页面缺少一级标题")

    if errors:
        print(f"内容审计失败：{len(errors)} 个问题")
        for error in errors:
            print(f"  - {error}")
        return 1
    print(
        "内容审计通过："
        f"{totals['pages']} 页、{totals['code']} 个代码块、{totals['tables']} 个表格、"
        f"{totals['images']} 个图片引用、{totals['lists']} 个列表项、"
        f"{totals['headings']} 个原始标题锚点。"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

