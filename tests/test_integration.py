import csv
import json
import os
from pathlib import Path
from extract_bilibili_from_qce import process_export_dir


def test_process_export_dir_integration(tmp_path):
    # 构造临时导出目录
    export_dir = tmp_path / "export_chunked"
    chunks_dir = export_dir / "chunks"
    chunks_dir.mkdir(parents=True)

    # 创建 manifest.json，指定 chunks 列表
    manifest = {
        "chatInfo": {"name": "test_chat"},
        "chunked": {
            "chunksDir": "chunks",
            "chunks": [{"fileName": "chunk1.jsonl"}]
        }
    }
    (export_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False), encoding='utf-8')

    # 创建 chunk1.jsonl，包含一个带 bilibili 链接的消息
    chunk_path = chunks_dir / "chunk1.jsonl"
    msg = {"sender": {"name": "Alice"}, "time": "2026-01-03T00:00:00", "text": "hello https://www.bilibili.com/video/ABC"}
    with chunk_path.open('w', encoding='utf-8') as f:
        f.write(json.dumps(msg, ensure_ascii=False) + "\n")

    out_csv = tmp_path / "out.csv"

    # 运行处理函数
    ret = process_export_dir(export_dir, out_csv, excel_path=None)
    assert ret == 0

    # 验证 CSV 存在并包含预期行
    assert out_csv.exists()
    with out_csv.open('r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    assert len(rows) == 1
    row = rows[0]
    assert row['chat_name'] == 'test_chat'
    assert 'bilibili.com' in row['link']
    assert row['sender'] == 'Alice'
