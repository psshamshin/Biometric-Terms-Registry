"""Генератор черновика конфига для нового стандарта (шаг 0–1 prompts/add_gost.md). Детерминированный, без LLM.

    python -m src.new_standard data/raw/NNNNN.pdf [--out config/<std_id>.yaml]

Из PDF определяет обозначение, ISO/IEC и вид соответствия, «взамен», страницы разделов, шаблон нумерации,
границы разделов, колонку, url, место в priority и какие из уже существующих ключей конфига нужны
(short_forms, qualifier, groups, parameters, note_list, example_list, abbr_en_sep, footnote_lines, …).
Пишет черновик конфига и печатает сводку: найденные ключи и статьи с header_unparsed.

Чего из файла не вывести и что остаётся вручную: corrections (по скану), known_ocr_errors, known_gaps,
header_overrides, исключения областей, эталон. Область в черновике — «биометрия · общее» для каждого раздела:
предложить значение по смыслу и записать в docs/DECISIONS.md.
Существующий конфиг не перезаписывается (правило 5 prompts/add_gost.md).
"""
import argparse
import re
import sys
from collections import Counter
from pathlib import Path

import yaml

from src.clean import CleaningLog, clean, normalize_spaces, strip_page_furniture
from src.extract import extract_pages
from src.parse import _join, _tokens, parse_abbreviations, parse_article
from src.recon import recon_dir
from src.split import split_articles

ROOT = Path(__file__).resolve().parent.parent

NUMBER_LINE = re.compile(r"^(\d+(?:\.\d+)+)(?:\s|$)")
HEADER_END = re.compile(r"^(?P<num>\S+) (?P<head>.*?[)\]])\s*:\s*(?P<definition>.*)$")
EXAMPLE = r"^Пример(ы)?( \d+)? ?— ?"
NOTE = r"^П ?р ?и ?м ?е ?ч ?а ?н ?и ?е( \S{1,2})? ?— ?"
NOTE_HEADING = r"^П ?р ?и ?м ?е ?ч ?а ?н ?и ?я$"
EXAMPLE_HEADING = r"^Примеры$"
EXCLUDED = r"^исключен[ыа]? "
PARAM_IN_HEAD = re.compile(r"[А-ЯЁA-Z]{2,8} \([A-Z](?:, [A-Z])*\)")
PARAM_FORM = re.compile(r"^\S+ \([A-Z](?:, [A-Z])*\)$")
ABBR_RU = {"simple": r"^[А-ЯЁ]{2,8}$", "extended": r"^[А-ЯЁ][А-ЯЁа-яё0-9-]{1,7}$"}
ABBR_EN = {"simple": r"^[A-Z]{2,8}$", "extended": r"^[A-Z][A-Za-z0-9-]{1,7}$"}
BIBLIOGRAPHY = r"^\[ ?\d+\](, \[ ?\d+\])*\.?$"
ABBR_HEADING = re.compile(r"^\d+ (?:Обозначения и )?сокращения$", re.IGNORECASE)
INDEX_HEADINGS = {"index_ru": "Алфавитный указатель терминов на русском языке",
                  "index_en": "Алфавитный указатель терминов на английском языке"}
ENTRY_WITH_EN = r"^(?P<abbr_ru>[^()—]+?) \((?P<abbr_en>[^()]+)\) — (?P<text>.*)$"
ENTRY_RU_ONLY = r"^(?P<abbr_ru>[А-ЯЁ]{2,8}) — (?P<text>.*)$"
EXPANSION_EN = r"^(?P<ru>.*?)(?: \((?P<en>[^()]*[A-Za-z][^()]*)\))?[;.]?$"
DEFAULT_AREA = "биометрия · общее"

# Ключи конфига, которые генератор определяет по тексту (для сравнения с подключёнными стандартами).
FEATURE_KEYS = ["markers.short_forms", "markers.qualifier", "markers.groups", "markers.parameters",
                "markers.note_list", "markers.example_list", "cleaning.footnote_lines",
                "cleaning.service_fragments", "cleaning.service_lines", "bounds.abbreviations",
                "bounds.index_ru", "bounds.index_en", "abbreviations"]


def esc(s):
    """Строка → шаблон: пробелы и дефисы без экранирования, как в существующих конфигах."""
    return re.escape(s).replace("\\ ", " ").replace("\\-", "-")


def _norm(s):
    return re.sub(r"\s+", " ", s.replace("­", "")).strip()


# ---------------------------------------------------------------- обозначение, ISO/IEC, «взамен»

def identify(pages):
    counts = Counter()
    for text in pages:
        for line in text.splitlines():
            m = re.match(r"^(ГОСТ(?: Р)?) (.+?)\s*[—–]\s*(\d{4})$", _norm(line))
            if m:
                counts[f"{m.group(1)} {m.group(2)}-{m.group(3)}"] += 1
    if not counts:
        return None
    designation = counts.most_common(1)[0][0]
    front = _norm(" ".join(pages[:3]))
    iso = re.search(r"ISO/IEC\s+(\d+(?:-\d+)?)\s*:\s*(\d{4})", " ".join(_norm(p) for p in pages[:2]))
    kind = re.search(r"\b(MOD|IDT|NEQ)\)", " ".join(_norm(p) for p in pages[:2]))
    replaces = re.search(r"ВЗАМЕН\s+(.+?)(?:\s+\d+\s+[А-ЯЁ]|$)", front, re.IGNORECASE)
    title = None
    if iso:
        t = re.search(rf"(?:ИСО/МЭК|ISO/IEC)\s+{re.escape(iso.group(1))}\s*:\s*\d{{4}}\s*«([^»]+)»", front)
        title = t.group(1) if t else None
    column = designation
    if iso and "ISO/IEC" not in designation:
        column = f"{designation} ({'ИСО/МЭК' if 'ИСО/МЭК' in front else 'ISO/IEC'} {iso.group(1)})"
    return {
        "designation": designation, "column": column,
        "iso": f"ISO/IEC {iso.group(1)}:{iso.group(2)}" if iso else None,
        "kind": kind.group(1) if kind else None,
        "replaces": replaces.group(1).strip() if replaces else None,
        "title": title,
    }


def slug(designation):
    s = re.sub(r"\b(ISO|IEC)\b", "", designation.replace("ISO/IEC", ""))
    s = s.replace("ГОСТ", "gost").replace("Р ", "r ")
    return re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")


def meganorm_url(pdf):
    name = Path(pdf).stem
    return f"https://meganorm.ru/Data/{name[:3]}/{name}.pdf"


# ---------------------------------------------------------------- нумерация и границы

def find_numbering(lines):
    """Статьи — группы строк от строки с номером «3.1.1» до следующей, где есть конец заголовка «): ».
    Возвращает (numbering, терминов start, end, номера статей) или None."""
    marks = [i for i, (_, l) in enumerate(lines) if NUMBER_LINE.match(l)]
    cands = []
    for k, i in enumerate(marks):
        stop = marks[k + 1] if k + 1 < len(marks) else len(lines)
        text = " ".join(l for _, l in lines[i:stop])
        if re.search(r"[)\]]\s*:", text):
            cands.append((i, NUMBER_LINE.match(lines[i][1]).group(1)))
    if not cands:
        return None
    prefix = Counter(n.split(".")[0] for _, n in cands).most_common(1)[0][0]
    depth = Counter(len(n.split(".")) for _, n in cands if n.split(".")[0] == prefix).most_common(1)[0][0]
    fit = [(i, n) for i, n in cands if n.split(".")[0] == prefix and len(n.split(".")) == depth]
    first = next(((i, n) for i, n in fit if all(int(c) == 1 for c in n.split(".")[1:])), fit[0])
    start = first[0]
    heading = re.compile(rf"^{int(prefix) + 1} [А-ЯЁ][^:]*$")
    index_ru = re.compile("^" + esc(INDEX_HEADINGS["index_ru"]) + "$")
    end = next((i for i in range(start + 1, len(lines))
                if heading.match(lines[i][1]) or index_ru.match(lines[i][1])), len(lines))
    nums = [n.split(".") for i, n in fit if start <= i < end]
    parts = [esc(prefix)]
    for pos in range(1, depth):
        widths = {len(n[pos]) for n in nums}
        parts.append(rf"\d{{{widths.pop()}}}" if len(widths) == 1 and len(nums[0][pos]) >= 2 else r"\d+")
    body = r"\.".join(parts)
    section = r"^(" + r"\.".join([r"\d+"] * (depth - 1)) + r")\."
    numbering = {"anchor": rf"^{body}\b", "section": section, "any": rf"\b{body}\b"}
    return numbering, start, end, [".".join(n) for n in nums], first[1]


def find_other_bounds(lines, start, end):
    """Разделы «Сокращения» и алфавитные указатели → bounds и страницы."""
    bounds, pages = {}, {}
    heading = next((i for i in range(start, len(lines)) if ABBR_HEADING.match(lines[i][1])), None)
    if heading is not None and heading + 1 < len(lines) and lines[heading + 1][1].endswith(":"):
        nxt = re.compile(r"^\d+ [А-ЯЁ][^:]*$")
        stop = next((i for i in range(heading + 2, len(lines)) if nxt.match(lines[i][1])), None)
        if stop is not None:
            bounds["abbreviations"] = {"start": "^" + esc(lines[heading + 1][1]) + "$",
                                       "end": "^" + esc(lines[stop][1]) + "$"}
            pages["abbreviations"] = (lines[heading + 1][0], lines[stop][0])
    last = None
    for name, text in INDEX_HEADINGS.items():
        pos = next((i for i in range(start, len(lines)) if lines[i][1] == text), None)
        if pos is None:
            continue
        if last is not None:
            bounds[last[0]]["end"] = "^" + esc(text) + "$"
            pages[last[0]] = (pages[last[0]][0], lines[pos][0])
        bounds[name] = {"start": "^" + esc(text) + "$", "end": None}
        pages[name] = (lines[pos][0], None)
        last = (name, pos)
    if last is not None:
        stop = next((i for i in range(last[1] + 1, len(lines))
                     if re.match(r"^(Библиография|Приложение\b.*)$", lines[i][1])), None)
        if stop is None:
            del bounds[last[0]], pages[last[0]]
        else:
            bounds[last[0]]["end"] = "^" + esc(lines[stop][1]) + "$"
            pages[last[0]] = (pages[last[0]][0], lines[stop][0])
    return bounds, pages


def find_cleaning(window, numbering):
    """Служебные строки внутри раздела терминов: подзаголовки, «Издание официальное», библиография,
    сноски и их знак, верх рамки."""
    anchor = re.compile(numbering["anchor"])
    marks = [i for i, (_, l) in enumerate(window) if NUMBER_LINE.match(l)]
    service = []
    for k, i in enumerate(marks):
        stop = marks[k + 1] if k + 1 < len(marks) else len(window)
        line = window[i][1]
        if stop - i == 1 and not anchor.match(line) and not re.search(r"[)\]]\s*:", line):
            service.append("^" + esc(line) + "$")
    texts = [l for _, l in window]
    if any(l == "Издание официальное" for l in texts):
        service.append("^Издание официальное$")
    if any(re.match(BIBLIOGRAPHY, l) for l in texts):
        service.append(BIBLIOGRAPHY)
    footnotes = ["^" + esc(l) + "$" for l in dict.fromkeys(texts) if re.match(r"^\* \S", l)]
    fragments = ([r"\*"] if footnotes else []) + ([r"\s+_{5,}$"] if any(re.search(r"\s+_{5,}$", l) for l in texts) else [])
    return list(dict.fromkeys(service)), footnotes, fragments


# ---------------------------------------------------------------- ключи разбора статьи

def head_of(article):
    lines = [l for _, l in article["lines"]]
    stop = next((i for i, l in enumerate(lines)
                 if any(re.match(p, l) for p in (EXAMPLE, NOTE, NOTE_HEADING, EXAMPLE_HEADING))), len(lines))
    return _join(lines[:stop])


def detect_features(articles):
    """Какие необязательные ключи нужны по тексту заголовков и абзацев статей."""
    f = {"short_forms": False, "qualifier": False, "groups": False, "parameters": False, "note_list": False,
         "example_list": False, "abbr_en_comma": False, "bracket_end": False, "ru_abbr": [], "en_abbr": []}
    for a in articles:
        lines = [l for _, l in a["lines"]]
        f["note_list"] |= any(re.match(NOTE_HEADING, l) for l in lines)
        f["example_list"] |= any(re.match(EXAMPLE_HEADING, l) for l in lines)
        m = HEADER_END.match(head_of(a))
        if not m:
            continue
        head = m.group("head")
        f["bracket_end"] |= head.endswith("]")
        f["groups"] |= bool(re.search(r"\[[^\]]*[A-Za-z]", head))
        f["parameters"] |= bool(PARAM_IN_HEAD.search(head))
        try:
            tokens = _tokens(head, "синоним", True, {"(": ")", "[": "]"}, None)
        except ValueError:
            continue
        for kind, value in tokens:
            if kind == "qualifier":
                f["qualifier"] = True
            elif kind == "en":
                first, *extras = value.split("; ")
                tail = re.search(r", ([A-Z][A-Za-z0-9-]{1,7})$", first)
                if tail:
                    f["abbr_en_comma"] = True
                    f["en_abbr"].append(tail.group(1))
                for extra in extras:
                    if re.match(EXCLUDED, extra) or PARAM_FORM.match(extra):
                        continue
                    f["short_forms"] = True
                    if re.fullmatch(r"[A-Z]\S{1,7}", extra):
                        f["en_abbr"].append(extra)
            elif kind == "text":
                for variant in value.split("/"):
                    for tail in variant.split("; ")[1:]:
                        if re.fullmatch(r"[А-ЯЁ]\S{1,7}", tail):
                            f["ru_abbr"].append(tail)
                        else:
                            f["short_forms"] = True
    return f


def _abbr_pattern(candidates, patterns):
    return patterns["simple"] if all(re.fullmatch(patterns["simple"], c) for c in candidates) else patterns["extended"]


def abbreviation_entry(lines):
    with_en = sum(bool(re.match(ENTRY_WITH_EN, l)) for _, l in lines)
    ru_only = sum(bool(re.match(ENTRY_RU_ONLY, l)) for _, l in lines)
    if not with_en and not ru_only:
        return None
    return ENTRY_WITH_EN if with_en >= ru_only else ENTRY_RU_ONLY


# ---------------------------------------------------------------- сборка

def config_features(cfg):
    """Набор ключей конфига стандарта (для сравнения с тем, что нашёл генератор): ключи-признаки и их вид."""
    def get(path):
        node = cfg
        for part in path.split("."):
            node = node.get(part) if isinstance(node, dict) else None
        return node
    found = {k for k in FEATURE_KEYS if get(k)}
    found.add("markers.abbr_en_sep=" + repr(get("markers.abbr_en_sep")))
    if "]" in cfg["markers"]["header"]:
        found.add("markers.header=brackets")
    if get("abbreviations.entry"):
        found.add("abbreviations.entry=" + ("ru+en" if "abbr_en" in get("abbreviations.entry") else "ru"))
    return found


def analyze(pdf, work_dir=None):
    """PDF → результат разведки: info, cfg (черновик конфига), features, pages, articles, unparsed, problems."""
    pdf = Path(pdf)
    work_dir = Path(work_dir) if work_dir else recon_dir(pdf)
    pages = extract_pages(pdf, work_dir / "pages")
    problems = []
    info = identify(pages)
    if info is None:
        raise SystemExit("не найдено обозначение «ГОСТ … —ГГГГ» в колонтитулах")

    log = CleaningLog()
    base = {"cleaning": {"repeated_line_min_share": 0.5, "page_number": r"^(\d+( \d+)?|[IVXLC]+)$",
                         "hyphens": ["-"], "soft_hyphen": "­"}}
    lines, _ = strip_page_furniture(pages, base, log)
    lines = normalize_spaces(lines, base, log)
    found = find_numbering(lines)
    if found is None:
        raise SystemExit("не найдены статьи: нет строк вида «3.1 … (…): определение»")
    numbering, start, end, nums, first_num = found
    window = lines[start:end]
    bounds = {"terms": {"start": "^" + esc(first_num) + r"\b", "end": None}}
    stop_line = lines[end][1] if end < len(lines) else None
    bounds["terms"]["end"] = "^" + esc(stop_line) + "$" if stop_line else None
    other, spans = find_other_bounds(lines, start, end)
    bounds.update(other)
    service, footnotes, fragments = find_cleaning(window, numbering)

    cleaning = dict(base["cleaning"], service_lines=service)
    if footnotes:
        cleaning["footnote_lines"] = footnotes
    if fragments:
        cleaning["service_fragments"] = fragments
    cfg = {"numbering": numbering, "bounds": bounds, "cleaning": cleaning}
    parts, _ = clean(pages, cfg, CleaningLog())
    articles = split_articles(parts["terms"], cfg)
    feats = detect_features(articles)

    markers = {
        "header": (r"^(?P<num>\S+) (?P<head>.*?[)\]])\s*:\s*(?P<definition>.*)$" if feats["bracket_end"]
                   else r"^(?P<num>\S+) (?P<head>.*?\))\s*:\s*(?P<definition>.*)$"),
        "example": EXAMPLE, "note": NOTE, "synonym_marker": "синоним", "excluded": EXCLUDED,
        "excluded_term": "«([^»]+)»", "abbr_ru_sep": "; ",
        "abbr_en_sep": ", " if feats["abbr_en_comma"] else None, "variant_sep": "/",
    }
    if feats["short_forms"]:
        markers["short_forms"] = {"abbr_ru": _abbr_pattern(feats["ru_abbr"], ABBR_RU),
                                  "abbr_en": _abbr_pattern(feats["en_abbr"], ABBR_EN)}
    if feats["qualifier"]:
        markers["qualifier"] = {"note_label": "Область применения термина: "}
    if feats["groups"]:
        markers["groups"] = {"(": ")", "[": "]"}
    if feats["parameters"]:
        markers["parameters"] = {"pattern": r"^[A-Z](, [A-Z])*$", "note_label": "Обозначение с параметрами: "}
    if feats["example_list"]:
        markers["example_list"] = {"heading": EXAMPLE_HEADING, "item": r"^\d+ "}
    if feats["note_list"]:
        markers["note_list"] = {"heading": NOTE_HEADING, "item": r"^\d+ "}
    cfg["markers"] = markers

    if "abbreviations" in parts:
        entry = abbreviation_entry(parts["abbreviations"])
        if entry:
            cfg["abbreviations"] = {"entry": entry, "expansion_en": EXPANSION_EN}
        else:
            problems.append("раздел «Сокращения» найден, но записи не похожи ни на «А (A) — …», ни на «А — …»")

    unparsed = []
    for a in articles:
        parsed = parse_article(a, cfg, CleaningLog())
        if "header_unparsed" in parsed["flags"]:
            unparsed.append((parsed["num"], parsed["page"], parsed["flag_reasons"]["header_unparsed"]))
    if "abbreviations" in cfg:
        try:
            parse_abbreviations(parts["abbreviations"], cfg)
        except ValueError as e:
            problems.append(f"«Сокращения» не разобраны: {e}")

    section_codes = list(dict.fromkeys(a["section"] for a in articles))
    cfg_full = {
        "standard": {"designation": info["column"], "source_column": info["column"],
                     "url": meganorm_url(pdf), "pdf": f"data/raw/{pdf.name}"},
        **cfg,
        "corrections": [], "header_overrides": {},
        "areas": {"sections": {c: DEFAULT_AREA for c in section_codes}, "exceptions": {}},
    }
    spans.update({"terms": (window[0][0], window[-1][0])})
    return {"info": info, "cfg": cfg_full, "features": config_features(cfg_full), "pages": spans,
            "articles": articles, "unparsed": unparsed, "problems": problems,
            "sid": slug(info["designation"]), "work_dir": work_dir}


def draft_yaml(result):
    info = result["info"]
    head = [f"# ЧЕРНОВИК конфига {info['designation']}"
            + (f" ({info['iso']}, {info['kind']})" if info["iso"] else "") + ". Создан: python -m src.new_standard.",
            f"# std_id = {result['sid']}. Определено по тексту; вручную: corrections (по скану), known_ocr_errors, "
            "known_gaps, header_overrides, areas.",
            "# Область — предложение «биометрия · общее» для каждого раздела: заменить по смыслу и записать в docs/DECISIONS.md.",
            ""]
    body = yaml.safe_dump(result["cfg"], allow_unicode=True, sort_keys=False, width=1000)
    return "\n".join(head) + "\n" + body


def summary(result, merge_cfg):
    info, cfg, pages = result["info"], result["cfg"], result["pages"]
    names = {"terms": "термины и определения", "abbreviations": "сокращения",
             "index_ru": "указатель ru", "index_en": "указатель en"}
    out = [f"Обозначение: {info['designation']}", f"Колонка источника: {info['column']}",
           f"ISO/IEC: {info['iso'] or 'не найден'}; вид соответствия: {info['kind'] or 'не найден'}",
           f"Название: {info['title'] or 'не найдено'}", f"Взамен: {info['replaces'] or 'нет'}",
           f"std_id: {result['sid']}; url: {cfg['standard']['url']}",
           "Страницы разделов (PDF): " + "; ".join(
               f"{names[k]} {a}–{b}" for k, (a, b) in pages.items() if k in names),
           f"Нумерация: anchor {cfg['numbering']['anchor']}, section {cfg['numbering']['section']}, "
           f"any {cfg['numbering']['any']}",
           f"priority: {merge_cfg['priority']} + [{result['sid']}] (в конец)", ""]
    used = sorted(result["features"])
    out.append(f"Найденные ключи ({len([k for k in used if k in FEATURE_KEYS])} из {len(FEATURE_KEYS)} необязательных): "
               + ", ".join(used))
    out.append(f"Статей: {len(result['articles'])}; header_unparsed: {len(result['unparsed'])}")
    for num, page, why in result["unparsed"]:
        out.append(f"  {num} (стр. {page}): {why}")
    for p in result["problems"]:
        out.append(f"Проблема: {p}")
    if result["unparsed"] or result["problems"]:
        out.append("Есть неразобранное: нужен новый ключ конфига (с тестом на статью-пример) или header_overrides. "
                   "Больше трёх новых ключей — остановиться и спросить.")
    out.append("Ключей использовано: см. выше; добавлено: 0 (дописать вручную, если добавлен новый ключ).")
    return "\n".join(out)


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("pdf")
    ap.add_argument("--out", help="куда писать черновик (по умолчанию config/<std_id>.yaml)")
    args = ap.parse_args(argv)
    if not Path(args.pdf).exists():
        sys.exit(f"нет файла {args.pdf}")
    result = analyze(args.pdf)
    out = Path(args.out) if args.out else ROOT / "config" / f"{result['sid']}.yaml"
    if out.exists():
        sys.exit(f"{out} уже есть — существующий конфиг не перезаписывается; укажи --out")
    out.write_text(draft_yaml(result), encoding="utf-8")
    with open(ROOT / "config/merge.yaml", encoding="utf-8") as f:
        merge_cfg = yaml.safe_load(f)
    print(summary(result, merge_cfg))
    print(f"\nЧерновик: {out}")


if __name__ == "__main__":
    main(sys.argv[1:])
