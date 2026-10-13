"""Разведка нового PDF (шаг 0 prompts/add_gost.md) — без правки кода и без произвольного Python.

    python -m src.recon text  data/raw/<файл>.pdf            # текст по страницам + сводка по PDF
    python -m src.recon scan  data/raw/<файл>.pdf <стр> [..]  # полосы скана страниц в PNG — открыть и сверить глазами
    python -m src.recon mixed data/raw/<файл>.pdf <стр>-<стр>  # подозрения на ошибки распознавания: смесь алфавитов
                                                             # и короткие слова из одних букв-двойников (РА, Т, Р)

Всё пишется в data/interim/_recon_<имя файла>/ (не в git). Номера страниц — как в PDF, с 1.
"""
import io
import re
import sys
from pathlib import Path

import fitz

from src.extract import extract_pages

ROOT = Path(__file__).resolve().parent.parent
STRIP_STEP, STRIP_HEIGHT = 850, 1050      # полосы с перекрытием, чтобы строка на границе была целиком хотя бы в одной
CYR, LAT = re.compile(r"[А-Яа-яЁё]"), re.compile(r"[A-Za-z]")
LOOKALIKE = re.compile(r"^[АВЕКМНОРСТХУ]{1,3}$")  # кириллические заглавные, неотличимые от латинских на скане


def recon_dir(pdf):
    return ROOT / "data/interim" / f"_recon_{Path(pdf).stem}"


def cmd_text(pdf):
    out = recon_dir(pdf) / "pages"
    pages = extract_pages(pdf, out)
    with fitz.open(pdf) as doc:
        print(f"{pdf}: страниц {doc.page_count}; текст — {out.relative_to(ROOT)}/NNN.txt")
        for i, page in enumerate(doc, start=1):
            imgs = page.get_images(full=True)
            full = [im for im in imgs if im[2] > 1500 and im[3] > 2000]
            kind = "скан с текстовым слоем" if full and pages[i - 1].strip() else (
                "скан без текста" if full else "текст")
            soft = pages[i - 1].count("­")
            print(f"  стр. {i:3}: символов {len(pages[i - 1]):5}, {kind}, мягких переносов {soft}")


def _page_image(doc, pno):
    """Изображение страницы: встроенный скан (без текстового слоя) или, если скана нет, рендер страницы."""
    from PIL import Image

    page = doc[pno - 1]
    imgs = [im for im in page.get_images(full=True) if im[2] > 1500 and im[3] > 2000]
    if imgs:
        return Image.open(io.BytesIO(doc.extract_image(imgs[0][0])["image"])).convert("L"), "скан"
    pix = page.get_pixmap(dpi=200)
    return Image.open(io.BytesIO(pix.tobytes("png"))).convert("L"), "рендер"


def cmd_scan(pdf, pages):
    out = recon_dir(pdf) / "crops"
    out.mkdir(parents=True, exist_ok=True)
    with fitz.open(pdf) as doc:
        for pno in pages:
            img, kind = _page_image(doc, pno)
            w, h = img.size
            names = []
            for i, top in enumerate(range(0, h, STRIP_STEP)):
                name = out / f"p{pno:02d}_{i:02d}.png"
                img.crop((0, top, w, min(top + STRIP_HEIGHT, h))).save(name)
                names.append(name.name)
            print(f"стр. {pno} ({kind}, {w}×{h}): {out.relative_to(ROOT)}/{names[0]} … {names[-1]}")


def cmd_mixed(pdf, first, last):
    with fitz.open(pdf) as doc:
        for pno in range(first, last + 1):
            text = doc[pno - 1].get_text("text", sort=True)
            for tok in sorted(set(re.findall(r"[^\s()\[\],.;:«»]+", text))):
                if CYR.search(tok) and LAT.search(tok):
                    why = "смесь алфавитов"
                elif LOOKALIKE.match(tok):
                    why = "только буквы-двойники — латиница или кириллица?"
                else:
                    continue
                print(f"  стр. {pno}: {tok!r} — {why}: " + " ".join(
                    f"{c}:{'кир' if CYR.match(c) else 'лат' if LAT.match(c) else '·'}" for c in tok))


def _pages(args):
    out = []
    for a in args:
        lo, _, hi = a.partition("-")
        out += list(range(int(lo), int(hi or lo) + 1))
    return out


def main(argv):
    if len(argv) < 2 or argv[0] not in ("text", "scan", "mixed"):
        sys.exit(__doc__)
    cmd, pdf = argv[0], argv[1]
    if not Path(pdf).exists():
        sys.exit(f"нет файла {pdf}")
    if cmd == "text":
        cmd_text(pdf)
    elif cmd == "scan":
        cmd_scan(pdf, _pages(argv[2:]))
    else:
        pages = _pages(argv[2:])
        cmd_mixed(pdf, min(pages), max(pages))


if __name__ == "__main__":
    main(sys.argv[1:])
