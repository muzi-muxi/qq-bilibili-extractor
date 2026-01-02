import pandas as pd
import tempfile
from pathlib import Path
from extract_bilibili_from_qce import write_aggregated_excel


def test_write_aggregated_excel(tmp_path: Path):
    csv_path = tmp_path / 'sample.csv'
    agg_path = tmp_path / 'agg.xlsx'

    data = [
        {'time': '2021-01-01T00:00:00', 'sender': 'Alice', 'link': 'https://www.bilibili.com/video/BV1', 'link_type': 'video', 'video_id': 'BV1', 'bili_title': 'Funny Cats', 'bili_uploader': 'UpA', 'context': 'ctx1'},
        {'time': '2021-01-02T00:00:00', 'sender': 'Bob', 'link': 'https://b23.tv/short1', 'link_type': 'short', 'video_id': '', 'bili_title': 'Funny Cats', 'bili_uploader': 'UpA', 'context': 'ctx2'},
        {'time': '2021-01-03T00:00:00', 'sender': 'Carol', 'link': 'https://www.bilibili.com/other', 'link_type': 'other', 'video_id': '', 'bili_title': '', 'bili_uploader': '', 'context': 'ctx3'},
    ]
    pd.DataFrame(data).to_csv(csv_path, index=False)

    ok = write_aggregated_excel(csv_path, agg_path)
    assert ok

    df = pd.read_excel(agg_path)
    # Expect one merged row for 'Funny Cats'
    merged = df[df['bili_title'] == 'Funny Cats'].iloc[0]
    # senders combined
    assert 'Alice' in merged['sender'] and 'Bob' in merged['sender']
    # video_id should contain BV1
    assert 'BV1' in str(merged['video_id'])
    # empty-title row preserved (consider NaN readback from Excel)
    empty_count = int(df['bili_title'].isna().sum()) + int((df['bili_title'] == '').sum())
    assert empty_count == 1
