import re


def parse_to_text(filename: str, content_type: str, data: bytes) -> str:
    """文件字节 → 纯文本。MD/TXT 直接解码；PDF 走 PDFium 提取文本层。"""
    lower = filename.lower()
    if lower.endswith(".pdf") or content_type == "application/pdf":
        return _parse_pdf(data)
    return data.decode("utf-8", errors="replace")


def _parse_pdf(data: bytes) -> str:
    """PDF 文本层提取：优先 liteparse(PDFium，比 pypdf 更鲁棒、容错无 xref)，
    异常时回退 pypdf。MVP 仅取文本层，OCR 关闭（扫描件 OCR 属 V2）。"""
    try:
        from liteparse import LiteParse

        return LiteParse(ocr_enabled=False).parse(data).text
    except Exception:  # noqa: BLE001 — liteparse 失败则降级到 pypdf，仍失败由上层置 failed
        import io

        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(data))
        return "\n".join((page.extract_text() or "") for page in reader.pages)


def slugify(text: str) -> str:
    """生成 slug：去首尾空白，ASCII 转小写，非字母数字（CJK 等 \\w 字符保留）转连字符。"""
    text = text.strip().lower()
    text = re.sub(r"[^\w]+", "-", text)
    return text.strip("-")
