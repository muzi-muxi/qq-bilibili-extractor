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
    - 'video'：包含 '/video/' 的视频页或含 BV/AV 标识
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


def extract_video_id(link: str) -> str:
    """从链接中提取 BV/AV 视频 ID（若存在）。返回字符串如 'BV1xxx' 或 'av1234'，若无则返回空字符串。"""
    import re
    l = link
    # 常见格式： /video/BV... , BV... 也可能出现在路径
    m = re.search(r'BV[0-9A-Za-z]+', l)
    if m:
        return m.group(0)
    m2 = re.search(r'av(\d+)', l, re.I)
    if m2:
        return 'av' + m2.group(1)
    # 也尝试从查询参数或片段中查找
    m3 = re.search(r'(?:video/)(BV[0-9A-Za-z]+)', l)
    if m3:
        return m3.group(1)
    return ''


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


def fetch_bilibili_metadata(link: str):
    """Try to fetch and extract title and uploader from a bilibili link.
    Returns (title, uploader, final_url) or ('','','') if not available or on error.
    Uses a short timeout and best-effort HTML parsing (og:title, meta name=author, <title>).
    final_url is the resolved URL after redirects (useful for short links like b23.tv)."""
    try:
        import requests
        from bs4 import BeautifulSoup
        have_bs4 = True
    except Exception:
        # we'll fall back to regex parsing if bs4 not installed
        have_bs4 = False

    try:
        resp = requests.get(link, timeout=6, headers={"User-Agent": "qq-bili-extractor/1.0"}, allow_redirects=True)
        resp.raise_for_status()
        final_url = getattr(resp, 'url', link)
        text = resp.text
        title = ''
        uploader = ''
        if have_bs4:
            soup = BeautifulSoup(text, 'html.parser')
            t = soup.find('meta', property='og:title') or soup.find('meta', attrs={'name': 'title'})
            if t and t.get('content'):
                title = t['content']
            if not title and soup.title and soup.title.string:
                title = soup.title.string.strip()
            a = soup.find('meta', attrs={'name': 'author'})
            if a and a.get('content'):
                uploader = a['content']
            if not uploader:
                sel = soup.select_one('.username, .user-name, .up-name')
                if sel:
                    uploader = sel.get_text(strip=True)
        else:
            # simple regex fallbacks
            import re
            m = re.search(r'<meta[^>]*property=["\']og:title["\'][^>]*content=["\']([^"\']+)["\']', text, re.I)
            if not m:
                m = re.search(r'<meta[^>]*name=["\']title["\'][^>]*content=["\']([^"\']+)["\']', text, re.I)
            if m:
                title = m.group(1)
            if not title:
                m = re.search(r'<title[^>]*>([^<]+)</title>', text, re.I)
                if m:
                    title = m.group(1).strip()
            m2 = re.search(r'<meta[^>]*name=["\']author["\'][^>]*content=["\']([^"\']+)["\']', text, re.I)
            if m2:
                uploader = m2.group(1)
        return (title or '', uploader or '', final_url)
    except Exception:
        return ('', '', '')


def write_aggregated_excel(csv_path: Path, agg_path: Path):
    """生成聚合 Excel：按 `bili_title` 合并行，发送者列表合并为分号分隔。
    输出列顺序：time, sender, link, link_type, video_id, bili_title, bili_uploader, context
    返回 True on success, False on failure（例如缺少 pandas）"""
    try:
        import pandas as pd
    except Exception:
        print("生成聚合 Excel 失败（未安装 pandas）。请安装：pip install pandas openpyxl")
        return False

    df = pd.read_csv(csv_path, dtype=str).fillna('')
    cols = ['time', 'sender', 'link', 'link_type', 'video_id', 'bili_title', 'bili_uploader', 'context']
    missing = [c for c in cols if c not in df.columns]
    if missing:
        print(f"生成聚合 Excel 失败：缺少列 {missing}，无法聚合。")
        return False

    grouped_rows = []
    # 保持原顺序：按第一次出现的 bili_title 的顺序分组
    seen_titles = []
    for _, row in df.iterrows():
        t = (row.get('bili_title') or '').strip()
        if t not in seen_titles:
            seen_titles.append(t)

    for title in seen_titles:
        sub = df[df['bili_title'].fillna('') == title]
        if title == '':
            # 对于无标题的行，保留原行（不合并）
            for _, r in sub.iterrows():
                grouped_rows.append({c: r.get(c, '') for c in cols})
            continue

        def combine(col, sep='; '):
            vals = [str(x).strip() for x in sub[col].astype(str).fillna('') if str(x).strip()]
            uniq = []
            for v in vals:
                if v not in uniq:
                    uniq.append(v)
            return sep.join(uniq)

        time_val = ''
        times = [t for t in sub['time'].astype(str).fillna('') if t]
        if times:
            time_val = sorted(times)[0]
        grouped_rows.append({
            'time': time_val,
            'sender': combine('sender', '; '),
            'link': combine('link', '; '),
            'link_type': combine('link_type', '; '),
            'video_id': combine('video_id', '; '),
            'bili_title': title,
            'bili_uploader': combine('bili_uploader', '; '),
            'context': ' || '.join([c for c in pd.unique(sub['context'].astype(str)) if c and c != 'nan']),
        })

    out_df = __import__('pandas').DataFrame(grouped_rows, columns=cols)
    try:
        out_df.to_excel(agg_path, index=False)
        print(f"已生成聚合 Excel：{agg_path}")
        return True
    except Exception as e:
        print(f"写入聚合 Excel 失败：{e}")
        return False


def process_export_dir(export_dir: Path, out_csv: Path, excel_path: Path = None, fetch_meta: bool = False):
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
        # 新增列：bili_title, bili_uploader，video_id（如未启用元数据抓取则留空）
        writer = csv.DictWriter(csvf, fieldnames=['chat_name', 'chunk', 'time', 'sender', 'link', 'link_type', 'video_id', 'bili_title', 'bili_uploader', 'context', 'raw_message'])
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
                        video_id = extract_video_id(link)
                        bili_title = ''
                        bili_uploader = ''
                        if fetch_meta:
                            t, u, resolved = fetch_bilibili_metadata(link)
                            bili_title = t
                            bili_uploader = u
                            # 如果未直接从 URL 提取到视频 ID，尝试从重定向后的 URL 提取
                            if not video_id and resolved:
                                video_id = extract_video_id(resolved)
                        writer.writerow({
                            'chat_name': chat_name,
                            'chunk': chunk_path.name,
                            'time': time,
                            'sender': sender,
                            'link': link,
                            'link_type': ltype,
                            'video_id': video_id,
                            'bili_title': bili_title,
                            'bili_uploader': bili_uploader,
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

    # 可选：生成聚合 Excel（按 bili_title 合并并合并发送者）
    agg_path = export_dir and None
    # 由 CLI 设置的全局变量会在 main 中传入；如果存在环境变量 AGGREGATE_EXCEL 则也支持
    try:
        agg_arg = getattr(process_export_dir, '_aggregate_excel_arg', None)
    except Exception:
        agg_arg = None
    if agg_arg:
        write_aggregated_excel(out_csv, Path(agg_arg))

    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('-i', '--input', required=True, help='导出目录（chunked-jsonl 的文件夹）路径')
    ap.add_argument('-o', '--output', default='bilibili_links.csv', help='输出 CSV 文件路径')
    ap.add_argument('--excel', help='可选：输出 Excel 文件路径 (.xlsx)')
    ap.add_argument('--fetch-meta', action='store_true', help='可选：为每个 bilibili 链接抓取标题与投稿人（依赖 requests & beautifulsoup4，可能较慢）')
    ap.add_argument('--aggregate-excel', help='可选：生成按标题聚合的 Excel 文件（按 bili_title 合并并合并发送者）')
    args = ap.parse_args()

    input_dir = Path(args.input)
    out_csv = Path(args.output)
    excel_path = Path(args.excel) if args.excel else None

    # 将聚合参数暂存到函数属性，方便 process_export_dir 取用（保持 API 向后兼容）
    if args.aggregate_excel:
        setattr(process_export_dir, '_aggregate_excel_arg', args.aggregate_excel)

    return process_export_dir(input_dir, out_csv, excel_path, fetch_meta=args.fetch_meta)


if __name__ == '__main__':
    raise SystemExit(main())
