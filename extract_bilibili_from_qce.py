#!/usr/bin/env python3
"""extract_bilibili_from_qce.py
从 QQ Chat Exporter（chunked-jsonl）导出的目录中提取包含 https://www.bilibili.com 的消息并导出为 CSV/Excel。
用法示例：
  python extract_bilibili_from_qce.py -i "C:/Users/ASUS/.qq-chat-exporter/exports/group_..." -o bilibili.csv --excel bilibili.xlsx
"""
import argparse
import csv
import json
import os
import re
from pathlib import Path
from typing import Any, Dict, Iterable

# 匹配 bilibili 的多种域名（含子域）以及短域名 b23.tv
BILI_RE = re.compile(r"https?://(?:[\w.-]+\.)?(?:bilibili\.com|b23\.tv)[^\s,，；;\"'<>]*", re.I)


def iter_jsonl_messages(chunk_path: Path) -> Iterable[Dict[str, Any]]:
    with chunk_path.open('r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except Exception:
                # 忽略解析错误的行
                continue


def extract_strings(obj: Any) -> Iterable[str]:
    """递归提取对象中的所有字符串，用于搜索链接和构建上下文。"""
    if obj is None:
        return
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        for v in obj.values():
            yield from extract_strings(v)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            yield from extract_strings(v)
    else:
        try:
            yield str(obj)
        except Exception:
            return


def classify_bili_link(link: str) -> str:
    """简单分类 b站 链接类型：
    - 'short'：b23.tv 短链
    - 'video'：包含 '/video/' 的视频页
    - 'mobile'：m.bilibili.com 或 t.bilibili.com 等移动/社交子域
    - 'other'：其他 bilibili 链接
    """
    l = link.lower()
    if 'b23.tv' in l:
        return 'short'
    if '/video/' in l or '/bv' in l or '/av' in l:
        return 'video'
    if l.startswith('https://m.') or l.startswith('https://t.') or '.m.bilibili.' in l:
        return 'mobile'
    return 'other'


def find_links_in_message(msg: Dict[str, Any]):
    text = "\n".join([s for s in extract_strings(msg)])
    results = []
    for m in BILI_RE.finditer(text):
        link = m.group(0)
        start = max(0, m.start() - 120)
        end = min(len(text), m.end() + 120)
        ctx = text[start:end].replace('\n', ' ')
        ltype = classify_bili_link(link)
        results.append((link, ctx, ltype))
    return results


def guess_sender(msg: Dict[str, Any]):
    # 常见字段
    candidates = []
    if isinstance(msg, dict):
        s = msg.get('sender') or msg.get('author') or msg.get('sender_profile') or {}
        if isinstance(s, dict):
            candidates.append(s.get('name'))
            candidates.append(s.get('nickname'))
            candidates.append(s.get('sender_name'))
            candidates.append(s.get('uin'))
        else:
            candidates.append(s)
        candidates.append(msg.get('senderName'))
        candidates.append(msg.get('nickname'))
        candidates.append(msg.get('sender_uin'))
        candidates.append(msg.get('sender_qq'))
    for c in candidates:
        if c and isinstance(c, str) and c.strip():
            return c
    return ''


def guess_time(msg: Dict[str, Any]):
    for key in ('time', 'timestamp', 'date', 'created_at', 'msg_time'):
        v = msg.get(key)
        if v:
            return v
    # 有些导出会把时间放成 number 字段
    if isinstance(msg.get('timeMs'), int):
        import datetime

        try:
            return datetime.datetime.utcfromtimestamp(msg['timeMs'] / 1000).isoformat()
        except Exception:
            pass
    return ''


def process_export_dir(export_dir: Path, out_csv: Path, excel_path: Path = None):
    manifest_path = export_dir / 'manifest.json'
    if not manifest_path.exists():
        print(f"找不到 manifest.json (期望在 {manifest_path})，请确认你传入了正确的导出目录。")
        return 1

    with manifest_path.open('r', encoding='utf-8') as f:
        manifest = json.load(f)

    chat_name = manifest.get('chatInfo', {}).get('name') or export_dir.name
    chunked = manifest.get('chunked') or {}
    chunks_dir = export_dir / chunked.get('chunksDir', 'chunks')

    # 获取 chunk 列表（优先使用 manifest 中列出的顺序）
    chunk_files = []
    for c in chunked.get('chunks', []):
        p = chunks_dir / c.get('fileName')
        chunk_files.append(p)

    # 若 manifest 没有列出则回退为查找目录中的 .jsonl 文件（按名排序）
    if not chunk_files:
        if chunks_dir.exists():
            chunk_files = sorted(chunks_dir.glob('*.jsonl'))

    if not chunk_files:
        print(f"未找到任何 chunk jsonl 文件，检查 {chunks_dir} 是否存在。")
        return 1

    # 输出 CSV
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with out_csv.open('w', encoding='utf-8', newline='') as csvf:
        # 新增列：link_type（分类：short/video/mobile/other），保持向后兼容，放在 link 后面
        writer = csv.DictWriter(csvf, fieldnames=['chat_name', 'chunk', 'time', 'sender', 'link', 'link_type', 'context', 'raw_message'])
        writer.writeheader()

        total_found = 0
        for chunk_path in chunk_files:
            if not chunk_path.exists():
                print(f"跳过不存在的文件: {chunk_path}")
                continue
            print(f"处理 {chunk_path} ...")
            try:
                for msg in iter_jsonl_messages(chunk_path):
                    links = find_links_in_message(msg)
                    if not links:
                        continue
                    time = guess_time(msg)
                    sender = guess_sender(msg)
                    raw = json.dumps(msg, ensure_ascii=False)
                    for link, ctx, ltype in links:
                        writer.writerow({
                            'chat_name': chat_name,
                            'chunk': chunk_path.name,
                            'time': time,
                            'sender': sender,
                            'link': link,
                            'link_type': ltype,
                            'context': ctx,
                            'raw_message': raw[:2000],
                        })
                        total_found += 1
            except Exception as e:
                print(f"处理 {chunk_path} 时出错: {e}")
        print(f"完成：共找到 {total_found} 条包含 bilibili 链接的消息，已写入 {out_csv}")

    if excel_path:
        try:
            import pandas as pd
            df = pd.read_csv(out_csv)
            df.to_excel(excel_path, index=False)
            print(f"已导出 Excel：{excel_path}")
        except Exception as e:
            print(f"生成 Excel 失败（未安装 pandas 或出错）：{e}。可以用 `pip install pandas openpyxl` 后重试。")

    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('-i', '--input', required=True, help='导出目录（chunked-jsonl 的文件夹）路径')
    ap.add_argument('-o', '--output', default='bilibili_links.csv', help='输出 CSV 文件路径')
    ap.add_argument('--excel', help='可选：输出 Excel 文件路径 (.xlsx)')
    args = ap.parse_args()

    input_dir = Path(args.input)
    out_csv = Path(args.output)
    excel_path = Path(args.excel) if args.excel else None

    return process_export_dir(input_dir, out_csv, excel_path)


if __name__ == '__main__':
    raise SystemExit(main())
