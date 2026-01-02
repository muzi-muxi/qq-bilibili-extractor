import json
from extract_bilibili_from_qce import extract_strings, find_links_in_message, guess_sender, guess_time, fetch_bilibili_metadata, extract_video_id


def test_extract_strings_nested():
    obj = {"a": ["hello", {"b": "world", "c": 123}], "d": None}
    res = list(extract_strings(obj))
    assert "hello" in res
    assert "world" in res
    assert "123" in res


def test_find_links_in_message_single_link():
    msg = {"text": "check this https://www.bilibili.com/video/BV1xK4y1x7x7 and more", "meta": {"desc": "no link"}}
    links = find_links_in_message(msg)
    assert len(links) == 1
    link, ctx, ltype = links[0]
    assert "bilibili.com" in link
    assert "check this" in ctx
    assert ltype == 'video'


def test_find_links_in_message_multiple_and_context():
    msg = {"parts": ["before https://bilibili.com/video/123 ", " middle ", "and https://www.bilibili.com/video/456 end"]}
    links = find_links_in_message(msg)
    assert len(links) == 2
    assert any("video/123" in l for l, _, _ in links)
    assert any("video/456" in l for l, _, _ in links)


def test_find_links_in_message_short_link():
    msg = {"text": "short link https://b23.tv/abc123"}
    links = find_links_in_message(msg)
    assert len(links) == 1
    link, ctx, ltype = links[0]
    assert "b23.tv" in link
    assert ltype == 'short'


def test_extract_video_id_from_bv_and_av():
    assert extract_video_id('https://www.bilibili.com/video/BV1xK4y1x7x7') == 'BV1xK4y1x7x7'
    assert extract_video_id('https://www.bilibili.com/video/av12345') == 'av12345'
    assert extract_video_id('https://m.bilibili.com/video/BV2abc') == 'BV2abc'
    assert extract_video_id('https://www.bilibili.com/watch?v=BV3def') == 'BV3def'

def test_guess_sender_various_fields():
    assert guess_sender({"sender": {"name": "Alice"}}) == "Alice"
    assert guess_sender({"senderName": "Bob"}) == "Bob"
    assert guess_sender({"nickname": "Nick"}) == "Nick"


def test_guess_time_fields():
    assert guess_time({"time": "2026-01-03T00:00:00"}) == "2026-01-03T00:00:00"
    v = guess_time({"timeMs": 1600000000000})
    assert isinstance(v, str) and "-" in v


def test_fetch_bilibili_metadata_video(monkeypatch):
    sample_html = '<html><head><meta property="og:title" content="Sample Video Title"><meta name="author" content="UploaderName"></head><body></body></html>'

    class DummyResp:
        def __init__(self, text):
            self.text = text
        def raise_for_status(self):
            return

    def fake_get(url, timeout=6, headers=None, allow_redirects=True):
        return DummyResp(sample_html)

    import sys, types
    fake_requests = types.SimpleNamespace(get=fake_get)
    monkeypatch.setitem(sys.modules, 'requests', fake_requests)
    title, uploader = fetch_bilibili_metadata('https://www.bilibili.com/video/ABC')
    assert title == 'Sample Video Title'
    assert uploader == 'UploaderName'


def test_fetch_bilibili_metadata_short_link(monkeypatch):
    sample_html = '<html><head><title>Short Link Title</title><meta name="author" content="ShortUploader"></head><body></body></html>'

    class DummyResp:
        def __init__(self, text):
            self.text = text
        def raise_for_status(self):
            return

    def fake_get(url, timeout=6, headers=None, allow_redirects=True):
        return DummyResp(sample_html)

    import sys, types
    fake_requests = types.SimpleNamespace(get=fake_get)
    monkeypatch.setitem(sys.modules, 'requests', fake_requests)
    title, uploader = fetch_bilibili_metadata('https://b23.tv/xyz')
    assert title == 'Short Link Title'
    assert uploader == 'ShortUploader'