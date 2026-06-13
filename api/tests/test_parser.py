from app.ingest.parser import parse_to_text, slugify

# 最小单页 PDF，正文文本层含 HelloLiteParse（用于验证 PDFium 文本层提取）
_MINIMAL_PDF = b"""%PDF-1.4
1 0 obj
<< /Type /Catalog /Pages 2 0 R >>
endobj
2 0 obj
<< /Type /Pages /Kids [3 0 R] /Count 1 >>
endobj
3 0 obj
<< /Type /Page /Parent 2 0 R /Resources << /Font << /F1 4 0 R >> >> /MediaBox [0 0 612 792] /Contents 5 0 R >>
endobj
4 0 obj
<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>
endobj
5 0 obj
<< /Length 47 >>
stream
BT /F1 24 Tf 100 700 Td (HelloLiteParse) Tj ET
endstream
endobj
trailer
<< /Root 1 0 R >>
%%EOF
"""


def test_parse_pdf_extracts_text_layer():
    text = parse_to_text("a.pdf", "application/pdf", _MINIMAL_PDF)
    assert "HelloLiteParse" in text


def test_parse_markdown_and_txt():
    assert parse_to_text("a.md", "text/markdown", "# 标题\n正文".encode()) == "# 标题\n正文"
    assert parse_to_text("a.txt", "text/plain", b"hello") == "hello"


def test_parse_unknown_falls_back_to_utf8():
    assert parse_to_text("a.bin", "application/octet-stream", b"raw") == "raw"


def test_slugify():
    assert slugify("Hello World") == "hello-world"
    assert slugify("技术部") == "技术部"  # 中文保留
    assert slugify("  A / B  ") == "a-b"
