# Redteam Wiki 静态版

这是 <https://redteam-wiki.org/> 从 Wiki.js 迁移得到的可维护静态版本。文章、图片和导航由本地同步工具从公开前台读取，站点使用 MkDocs Material 构建并部署到 GitHub Pages。

## 本地使用

需要 Python 3.11 或更高版本：

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python scripts/sync_wikijs.py check
python scripts/sync_wikijs.py sync
mkdocs serve
```

严格构建及链接检查：

```powershell
mkdocs build --strict
python scripts/check_site.py site
python scripts/audit_content.py
```

## 同步规则

- `check` 只访问旧站并报告差异，不写入文件。
- `sync` 更新未被本地修改的文章和资源。
- 如果 Markdown 已在 Git 中手工修改，本地版本优先；当旧站也有更新时，命令会报告冲突并以状态码 `2` 结束。
- 确认需要接受旧站版本时，运行 `python scripts/sync_wikijs.py sync --accept-upstream en/<slug>`。
- 上游删除不会自动删除本地文章或资源，只会在报告中标记。
- `en/Introduction` 和 `en/quick-start` 是已确认的测试页，不抓取、不归档、不发布。

原始页面快照位于 `archive/raw/pages/`，同步状态和哈希位于 `.wikijs-sync/state.json`。

## GitHub Pages 与域名

推送 `main` 分支后，工作流会构建并发布站点。首次配置时在仓库 Settings → Pages 中选择 GitHub Actions，并把自定义域名设为 `redteam-wiki.org`。

域名验证完成后，将根域当前的服务器 A 记录替换为：

```text
185.199.108.153
185.199.109.153
185.199.110.153
185.199.111.153
```

先通过 GitHub Pages 临时地址验收，DNS 生效且证书签发后再启用 Enforce HTTPS。旧 Wiki.js 建议继续保留 48–72 小时。

## 许可

文章和原创媒体使用 CC BY-SA 4.0；工具代码和配置使用 MIT。详见 `LICENSE-CONTENT.md`、`LICENSE-CODE` 和 `NOTICE.md`。
