"""Шаг 0/2: постраничное извлечение текста из PDF (PyMuPDF).

Текст сохраняется как есть, без очистки: data/interim/pages/NNN.txt.
"""
from pathlib import Path

import fitz  # PyMuPDF


def extract_pages(pdf_path, pages_dir):
    """Извлекает текст каждой страницы. Возвращает список строк-страниц (индекс 0 = стр. 1)."""
    pdf_path = Path(pdf_path)
    pages_dir = Path(pages_dir)
    pages_dir.mkdir(parents=True, exist_ok=True)
    for old in pages_dir.glob("*.txt"):
        old.unlink()

    pages = []
    with fitz.open(pdf_path) as doc:
        for i, page in enumerate(doc, start=1):
            # sort=True — порядок чтения сверху вниз, слева направо
            text = page.get_text("text", sort=True)
            pages.append(text)
            (pages_dir / f"{i:03d}.txt").write_text(text, encoding="utf-8")
    return pages


if __name__ == "__main__":
    import sys

    root = Path(__file__).resolve().parent.parent
    pdf = Path(sys.argv[1]) if len(sys.argv) > 1 else root / "data/raw/gost_iso_iec_2382-37-2016.pdf"
    result = extract_pages(pdf, root / "data/interim/pages")
    print(f"{len(result)} страниц → {root / 'data/interim/pages'}")
