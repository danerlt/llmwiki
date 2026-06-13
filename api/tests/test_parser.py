from app.ingest.parser import parse_to_text, slugify


def test_parse_markdown_and_txt():
    assert parse_to_text("a.md", "text/markdown", "# 标题\n正文".encode()) == "# 标题\n正文"
    assert parse_to_text("a.txt", "text/plain", b"hello") == "hello"


def test_parse_unknown_falls_back_to_utf8():
    assert parse_to_text("a.bin", "application/octet-stream", b"raw") == "raw"


def test_slugify():
    assert slugify("Hello World") == "hello-world"
    assert slugify("技术部") == "技术部"  # 中文保留
    assert slugify("  A / B  ") == "a-b"
