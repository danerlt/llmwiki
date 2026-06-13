import re


def parse_to_text(filename: str, content_type: str, data: bytes) -> str:
    """文件字节 → 纯文本。MD/TXT 直接解码；PDF 用 pypdf 提取文本层。"""
    lower = filename.lower()
    if lower.endswith(".pdf") or content_type == "application/pdf":
        import io

        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(data))
        return "\n".join((page.extract_text() or "") for page in reader.pages)
    return data.decode("utf-8", errors="replace")


def slugify(text: str) -> str:
    """生成 slug：去首尾空白，ASCII 转小写，非字母数字（CJK 等 \\w 字符保留）转连字符。"""
    text = text.strip().lower()
    text = re.sub(r"[^\w]+", "-", text)
    return text.strip("-")
