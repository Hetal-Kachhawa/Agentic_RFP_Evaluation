import re
import fitz  # PyMuPDF

MAX_CHARS = 30000  # keeps the prompt within a sensible size


def extract_text(source, filename="document.pdf"):
    """
    source: file path (str) OR raw bytes (Streamlit uploads).
    Returns {"text", "pages", "chars", "warnings"}.
    """
    warnings = []
    try:
        doc = fitz.open(stream=source, filetype="pdf") if isinstance(source, (bytes, bytearray)) else fitz.open(source)
    except Exception as e:
        return {"text": "", "pages": 0, "chars": 0, "warnings": [f"{filename}: cannot open PDF ({e})"]}

    parts = []
    for i, page in enumerate(doc, start=1):
        parts.append(f"--- Page {i} ---\n{page.get_text('text')}")
    pages = len(doc)
    doc.close()

    text = "\n".join(parts)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()

    if len(text) < 300:
        warnings.append(f"{filename}: very little text extracted. It may be a scanned/image PDF.")
    if pages > 4:
        warnings.append(f"{filename}: {pages} pages (brief expects 2-4).")
    if len(text) > MAX_CHARS:
        warnings.append(f"{filename}: text truncated to {MAX_CHARS} characters.")
        text = text[:MAX_CHARS]

    return {"text": text, "pages": pages, "chars": len(text), "warnings": warnings}
