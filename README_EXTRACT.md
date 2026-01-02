提取 bilibili 链接说明

简要：
1. 确保你已使用 QQ Chat Exporter 导出群聊为 "chunked-jsonl" 格式（包含 manifest.json 与 chunks/*.jsonl）。
2. 将导出目录路径作为 `-i` 参数传给脚本 `extract_bilibili_from_qce.py`。

示例：

# 仅生成 CSV
python extract_bilibili_from_qce.py -i "C:\Users\ASUS\.qq-chat-exporter\exports\group_鸭大中术同好会_910096846_20260103_034954_chunked_jsonl" -o bilibili_links.csv

# 同时生成 Excel
python extract_bilibili_from_qce.py -i "C:\Users\ASUS\.qq-chat-exporter\exports\group_鸭大中术同好会_910096846_20260103_034954_chunked_jsonl" -o bilibili_links.csv --excel bilibili_links.xlsx

注意：
- 脚本会按 manifest 中列出的 chunk 顺序逐个处理大型 jsonl 分片，并在找到包含 https://www.bilibili.com 的消息时写入 CSV。
- 如果希望脚本在本机运行，请在你本地的终端中执行（工具无法直接访问你用户目录外的文件）。
- 若要过滤特定用户或时间段，我可以帮你扩展脚本（请说明筛选规则）。

- 输出 CSV 现在包含额外列 `link_type`，用于区分链接类型（示例值：`video`（包含 /video/ 或 BV/AV 的页面）、`short`（b23.tv 短链）、`mobile`（m.bilibili 子域）或 `other`）。

## 开发与调试

- 运行测试（在项目根目录）：
  - python -m pip install --upgrade pytest
  - python -m pytest -q

- 运行脚本示例：
  - python extract_bilibili_from_qce.py -i "path/to/export_dir" -o out.csv

- 调试：
  - 使用 pdb（在终端）：
    - python -m pdb extract_bilibili_from_qce.py -i "path/to/export_dir" -o out.csv
  - 在 VS Code 中：打开 `extract_bilibili_from_qce.py`，设置断点，使用“运行和调试”运行当前文件（或使用下列简易 `launch.json` 配置）：

```json
{
  "name": "Python: Current File",
  "type": "python",
  "request": "launch",
  "program": "${file}",
  "console": "integratedTerminal"
}
```

如果需要我添加示例单元测试、CI 或更细粒度的调试说明，请告诉我你的偏好和要覆盖的输入样例。
