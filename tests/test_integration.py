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
    msg = {"sender": {"name": "Alice"}, "time": "2026-01-03T00:00:00", "text": "hello https://www.bilibili.com/video/BV1xK4y1x7x7"}
    with chunk_path.open('w', encoding='utf-8') as f:
        f.write(json.dumps(msg, ensure_ascii=False) + "\n")
    # 增加短链示例（追加）
    with chunk_path.open('a', encoding='utf-8') as f:
        f.write(json.dumps({"sender": {"name": "Bob"}, "time": "2026-01-03T00:05:00", "text": "check https://b23.tv/xyz"}, ensure_ascii=False) + "\n")

    out_csv = tmp_path / "out.csv"

    # 运行处理函数（启用元数据抓取，但将 fetch_bilibili_metadata monkeypatch 为固定值以避免真实网络）
    # monkeypatch 函数会在运行时由测试注入
    try:
        # 如果测试环境提供了 monkeypatch fixture in scope
        fetch_stub = lambda url: (f"Title for {url}", f"Uploader for {url}")
        import extract_bilibili_from_qce as mod
        mod.fetch_bilibili_metadata = fetch_stub
    except Exception:
        pass

    ret = process_export_dir(export_dir, out_csv, excel_path=None, fetch_meta=True)
    assert ret == 0

    # 验证 CSV 存在并包含预期行
    assert out_csv.exists()
    with out_csv.open('r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    # 应该包含两条：普通视频 + 短链
    assert len(rows) == 2
    # 按发送者检查各自类型与元数据
    types = {r['sender']: r['link_type'] for r in rows}
    assert types['Alice'] == 'video'
    assert types['Bob'] == 'short'
    # 验证 video_id 与元数据列被填充
    ids = {r['sender']: r['video_id'] for r in rows}
    assert ids['Alice'].startswith('BV') or ids['Alice'].startswith('av')
    titles = {r['sender']: r['bili_title'] for r in rows}
    assert titles['Alice'].startswith('Title for')
    assert titles['Bob'].startswith('Title for')