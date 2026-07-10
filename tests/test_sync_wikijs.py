from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.sync_wikijs import HtmlToMarkdown, PageSnapshot, page_status


class ConverterTests(unittest.TestCase):
    def converter(self) -> HtmlToMarkdown:
        return HtmlToMarkdown(
            "https://redteam-wiki.org",
            "en/example.md",
            {"/en/target": "en/target.md"},
            {"/image.png": "assets/media/image.png"},
        )

    def test_core_wikijs_elements_are_preserved(self) -> None:
        fragment = """
        <h2 id="标题" class="toc-header"><a class="toc-anchor" href="#标题">¶</a> 标题</h2>
        <p><strong>粗体</strong>与<a href="/en/target#目标">内部链接</a></p>
        <pre class="prismjs"><code class="language-python">print("ok")\n</code></pre>
        <table><thead><tr><th>A</th><th>B</th></tr></thead>
        <tbody><tr><td>1</td><td>2</td></tr></tbody></table>
        <img src="/image.png" alt="示例">
        """
        result = self.converter().convert(fragment)
        self.assertIn("## 标题 {#标题}", result)
        self.assertIn("**粗体**", result)
        self.assertIn("[内部链接](target.md#目标)", result)
        self.assertIn('```python\nprint("ok")\n```', result)
        self.assertIn("| A | B |", result)
        self.assertIn("![示例](../assets/media/image.png)", result)

    def test_invalid_fragment_becomes_plain_text(self) -> None:
        result = self.converter().convert('<p><a href="#不存在">保留文字</a></p>')
        self.assertEqual(result, "保留文字\n")

    def test_residual_invalid_markdown_link_becomes_plain_text(self) -> None:
        result = self.converter().convert('<p>参见[坏锚点](#不存在)。</p>')
        self.assertEqual(result, "参见坏锚点。\n")

    def test_mathml_tail_tex_is_preserved(self) -> None:
        fragment = (
            '<p><span class="katex"><span class="katex-mathml">'
            '<math><mrow><mo>→</mo></mrow>\\rightarrow</math></span></span></p>'
        )
        self.assertIn("$\\rightarrow$", self.converter().convert(fragment))

    def test_list_before_rule_keeps_list_structure(self) -> None:
        result = self.converter().convert("<ul><li>唯一条目</li></ul><hr>")
        self.assertEqual(result, "- 唯一条目\n\n---\n")

    def test_table_does_not_double_escape_existing_pipe(self) -> None:
        fragment = "<table><tr><th>调用</th></tr><tr><td>foo\\|bar</td></tr></table>"
        self.assertIn("| foo\\|bar |", self.converter().convert(fragment))


class ConflictTests(unittest.TestCase):
    def snapshot(self) -> PageSnapshot:
        return PageSnapshot(
            key="en/example",
            route="/en/example",
            doc_path="en/example.md",
            title="Example",
            metadata={},
            raw_html=b"raw",
            fragment_html="<p>new</p>",
            markdown="new\n",
            upstream_hash="new-upstream",
            raw_hash="raw-hash",
        )

    def test_local_and_upstream_changes_are_a_conflict(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            docs = Path(directory)
            path = docs / "en" / "example.md"
            path.parent.mkdir(parents=True)
            path.write_text("local edit\n", encoding="utf-8")
            previous = {"upstream_hash": "old-upstream", "generated_hash": "not-current"}
            with patch("scripts.sync_wikijs.DOCS", docs):
                upstream_changed, local_modified, _ = page_status(self.snapshot(), previous)
            self.assertTrue(upstream_changed)
            self.assertTrue(local_modified)

    def test_missing_generated_file_is_not_considered_a_local_edit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            previous = {"upstream_hash": "new-upstream", "generated_hash": "old-file"}
            with patch("scripts.sync_wikijs.DOCS", Path(directory)):
                upstream_changed, local_modified, current = page_status(self.snapshot(), previous)
            self.assertFalse(upstream_changed)
            self.assertFalse(local_modified)
            self.assertIsNone(current)


if __name__ == "__main__":
    unittest.main()
