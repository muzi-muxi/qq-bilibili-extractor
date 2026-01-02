# Copilot / Agent Instructions for qq-bilibili-extractor

**Purpose:** 简短、可操作的提示，帮助 AI 代码代理在本仓库中快速做出准确的改动。

## 快速概览 ✅
- 功能：从 QQ Chat Exporter 的 chunked-jsonl 导出中提取包含 `bilibili` 链接的消息并导出为 CSV/Excel。
- 主要文件：`extract_bilibili_from_qce.py`（唯一主脚本）、`README_EXTRACT.md`（使用示例和说明）。
- 运行环境：Python 3.x；CSV 输出无额外依赖；导出 Excel 需要 `pandas`（和 `openpyxl`）。

## 重要实现细节（必读） 🔧
- `process_export_dir(export_dir, out_csv, excel_path)`
  - 从 `export_dir/manifest.json` 读取 `manifest['chunked']`：优先使用 `chunks` 中给出的顺序和 `chunksDir`（默认 `chunks`）。
  - 若 manifest 未列出 chunk 则回退为按文件名排序的 `chunks/*.jsonl`。
- JSONL 处理：`iter_jsonl_messages(chunk_path)` 是生成器，按行解析 JSON，解析错误会被忽略（跳过该行）。
- 链接检测：`BILI_RE` 在文件顶部定义（匹配 `https?://(www.)?bilibili.com`），`find_links_in_message` 会从消息中递归提取所有字符串并搜索链接，同时返回上下文片段。
- 发送者与时间猜测：`guess_sender` 和 `guess_time` 对常见字段做启发式判断（查看函数以获取具体字段顺序）。
- 输出 CSV 字段：`chat_name, chunk, time, sender, link, context, raw_message`（`raw_message` 被截断为前 2000 字符）。
- Excel 支持：脚本尝试导入 `pandas` 并写入 `.xlsx`；若缺少依赖会捕获异常并提示 `pip install pandas openpyxl`。

## 开发与变更策略 💡
- 新功能优先保持 CLI 向后兼容：新增筛选参数应添加 `--flag` 并在 `argparse` 中注册，同时更新 `README_EXTRACT.md` 示例。
- 代码风格：保持函数小而单一（例如 `extract_strings`, `find_links_in_message`），便于针对这些函数编写单元测试。
- 日志/输出：当前使用 `print()` 打印进度/错误；若需要改为 `logging`，请同时保留原有的终端可读输出以兼容用户体验。

## 测试建议 (可直接实现) 🧪
- 添加单元测试覆盖：
  - `extract_strings()`（嵌套 dict/list、非字符串值）
  - `find_links_in_message()`（多链接、上下文截取）
  - `guess_sender()` / `guess_time()`（不同字段组合）
  - 小型 `process_export_dir()` 集成测试：合成 `manifest.json` + `chunks/*.jsonl` 并校验生成 CSV 内容。

## PR / Review 要点 ✅
- 变更应保留 CSV 列名不变，除非在 PR 描述中明确说明并更新 `README_EXTRACT.md`。
- 若更改时间格式或发送者解析逻辑，请在说明中列出示例输入与预期输出（1–3 个用例）。
- 任何新增依赖（如 `pandas`）必须在 README 中记录并给出安装示例。

## 参考文件/位置 📁
- 业务代码: `extract_bilibili_from_qce.py`
- 使用说明: `README_EXTRACT.md`
- License: `LICENSE` (GPL-3.0) — 注意衍生与分发限制。

## 测试与 CI 🧪
- 本地运行测试：`python -m pytest -q`（建议先 `pip install --upgrade pytest`）。
- 我已添加示例测试：`tests/test_extract.py`（覆盖 `extract_strings`, `find_links_in_message`, `guess_sender`, `guess_time`）。
- 已添加 GitHub Actions 工作流：`.github/workflows/python-tests.yml`（在 Python 3.8–3.11 上运行 `pytest`，触发于 `push` 与 `pull_request`）。
- 如需更多测试用例（例如针对大数据分片或不同 manifest 变体的集成测试），请提供样本导出或期望的行为。

---

如果你希望我把这个内容合并到仓库（或需要补充示例用例、测试样本等），告诉我你想要的细节，我会立刻更新文件并提交。