"""Шаг 2: очистка текста, выделение раздела терминов и указателей.

Каждое изменение текста пишется в журнал: страница, было, стало, правило.
Опечатки, формулировки, кавычки, тире, «е/ё» и регистр не трогаются.
Отступы и пустые строки — вёрстка, а не текст: убираются без записи в журнал.
"""
import csv
import re
from collections import Counter

NBSP = " "
CYRILLIC = re.compile(r"[А-Яа-яЁё]")


def visible(s):
    """Невидимые символы в журнале — явными обозначениями."""
    return s.replace("­", "<U+00AD>").replace(NBSP, "<U+00A0>").replace("\n", "⏎")


class CleaningLog:
    def __init__(self):
        self.rows = []
        self.hyphen_guesses = []  # (страница, склеенный фрагмент) — для флага hyphen_guess на статье

    def add(self, page, before, after, rule):
        self.rows.append((page, visible(before), visible(after), rule))

    def write(self, path):
        with open(path, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.writer(f)
            w.writerow(["страница", "было", "стало", "правило"])
            w.writerows(self.rows)


def _key(line):
    return re.sub(r"\s+", "", line)


def strip_page_furniture(pages, cfg, log):
    """Удаляет колонтитулы (строки на ≥ N% страниц) и номера страниц.
    Возвращает [(страница, строка)] и множество колонтитулов (без пробелов)."""
    c = cfg["cleaning"]
    counts = Counter()
    for text in pages:
        counts.update({_key(l) for l in text.splitlines() if l.strip()})
    repeated = {k for k, v in counts.items() if v / len(pages) >= c["repeated_line_min_share"]}
    page_number = re.compile(c["page_number"])

    out = []
    for page, text in enumerate(pages, start=1):
        lines = [l.strip() for l in text.splitlines() if l.strip()]
        for i, line in enumerate(lines):
            if _key(line) in repeated:
                log.add(page, line, "", "колонтитул")
            elif i == len(lines) - 1 and page_number.match(line):
                log.add(page, line, "", "номер страницы")
            else:
                out.append((page, line))
    return out, repeated


def normalize_spaces(lines, cfg, log):
    """Неразрывные пробелы → обычные, двойные пробелы → один, мягкий перенос внутри строки → удалить."""
    soft = cfg["cleaning"]["soft_hyphen"]
    out = []
    for page, line in lines:
        new = line.replace(NBSP, " ")
        if NBSP in line:
            log.add(page, line, new, "неразрывный пробел")
        body, tail = (new[:-1], new[-1]) if new.endswith(soft) else (new, "")
        if soft in body:
            cleaned = body.replace(soft, "")
            log.add(page, body, cleaned, "мягкий перенос внутри строки")
            body = cleaned
        collapsed = re.sub(r" {2,}", " ", body)
        if collapsed != body:
            log.add(page, body, collapsed, "двойной пробел")
        out.append((page, collapsed + tail))
    return out


def find_bounds(lines, bounds):
    """Индексы [start, end) фрагмента по шаблонам начала и конца."""
    start = next(i for i, (_, l) in enumerate(lines) if re.match(bounds["start"], l))
    end = next(i for i in range(start + 1, len(lines)) if re.match(bounds["end"], lines[i][1]))
    return start, end


def _word_in(corpus, word):
    return re.search(r"(?<![\w-])" + re.escape(word) + r"(?![\w-])", corpus, re.IGNORECASE) is not None


def hyphen_decision(tail, head, corpus):
    """Строка кончается на дефис. Возвращает (сохранить дефис?, пояснение для журнала):
    слово с дефисом есть в тексте стандарта — сохранить; есть слитно — склеить;
    нет ни так, ни так — латиница: сохранить, кириллица: склеить (hyphen_guess)."""
    a = re.search(r"\w+$", tail[:-1])
    b = re.match(r"\w+", head)
    a, b = (a.group(0) if a else ""), (b.group(0) if b else "")
    if _word_in(corpus, f"{a}-{b}"):
        return True, "в тексте с дефисом"
    if _word_in(corpus, a + b):
        return False, "в тексте слитно"
    if CYRILLIC.search(a + b):
        return False, "hyphen_guess: нет в тексте, кириллица — склеено"
    return True, "hyphen_guess: нет в тексте, латиница — дефис сохранён"


def join_hyphenated(lines, cfg, log, corpus):
    """Склейка переносов. Мягкий перенос в конце строки — склеить без него.
    Дефис в конце строки, следующая начинается с буквы — по hyphen_decision (corpus — весь текст стандарта)."""
    c = cfg["cleaning"]
    soft = c["soft_hyphen"]
    out = []
    for page, line in lines:
        if out:
            prev_page, prev = out[-1]
            head, word_tail = _last_word(prev)
            word_head, rest = _first_word(line)
            if prev.endswith(soft):
                rule, keep = "мягкий перенос в конце строки", False
            elif prev[-1:] in c["hyphens"] and line[:1].isalpha():
                keep, why = hyphen_decision(word_tail, word_head, corpus)
                rule = f"перенос дефисом ({why})"
            else:
                rule = None
            if rule:
                joined = (word_tail if keep else word_tail[:-1]) + word_head
                log.add(prev_page, word_tail + "\n" + word_head, joined, rule)
                if "hyphen_guess" in rule:
                    log.hyphen_guesses.append((prev_page, joined))
                out[-1] = (prev_page, head + joined + rest)
                continue
        out.append((page, line))
    return out


def _last_word(s):
    i = s.rfind(" ") + 1
    return s[:i], s[i:]


def _first_word(s):
    i = s.find(" ")
    return (s, "") if i < 0 else (s[:i], s[i:])


def drop_service_lines(lines, cfg, log):
    patterns = [re.compile(p) for p in cfg["cleaning"]["service_lines"]]
    fragments = [re.compile(p) for p in cfg["cleaning"].get("service_fragments", [])]  # служебный хвост внутри строки
    out = []
    for page, line in lines:
        if any(p.match(line) for p in patterns):
            log.add(page, line, "", "служебная строка")
            continue
        for p in fragments:
            cut = p.sub("", line).rstrip()
            if cut != line:
                log.add(page, line, cut, "служебный фрагмент строки")
                line = cut
        out.append((page, line))
    return out


def clean(pages, cfg, log):
    """Возвращает ({имя фрагмента из bounds: [(страница, строка)]}, колонтитулы).
    Фрагменты: terms — раздел терминов; index_* — указатели; abbreviations — раздел «Сокращения»."""
    lines, furniture = strip_page_furniture(pages, cfg, log)
    lines = normalize_spaces(lines, cfg, log)
    corpus = "\n".join(line for _, line in lines)  # весь текст стандарта — для решения о дефисе
    parts = {}
    for name, bounds in cfg["bounds"].items():
        start, end = find_bounds(lines, bounds)
        if name != "terms":
            start += 1  # заголовок указателя или раздела — не запись
        part = join_hyphenated(lines[start:end], cfg, log, corpus)
        if name == "terms":
            part = drop_service_lines(part, cfg, log)
        parts[name] = part
    return parts, furniture


def apply_corrections(articles, cfg, log):
    """Исправления ошибок распознавания из таблицы конфига. Каждое «было» должно встретиться ровно один раз."""
    by_num = {a["num"]: a for a in articles}
    for fix in cfg.get("corrections", []):
        art = by_num[str(fix["пункт"])]
        hits = [i for i, (_, l) in enumerate(art["lines"]) for _ in range(l.count(fix["было"]))]
        if len(hits) != 1:
            raise ValueError(f"исправление {fix} найдено {len(hits)} раз(а) в {art['num']}")
        page, line = art["lines"][hits[0]]
        art["lines"][hits[0]] = (page, line.replace(fix["было"], fix["стало"]))
        art.setdefault("corrections", []).append(fix)
        log.add(page, fix["было"], fix["стало"], f"ошибка распознавания ({art['num']})")
