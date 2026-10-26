"""Записи реестра, названные в формулировке источника: связь «используется в определении».

Строится автоматически по тексту колонок источников (build.py); проверка полноты — блок «д» в validation.py.
"""
import re

USED_IN_DEFINITION = "используется в определении"


def _tokens(text):
    return re.findall(r"[a-zа-я0-9]+", text.lower().replace("ё", "е"))


def _stem(token):
    """Основа слова для сравнения падежей: без последних трёх букв, но не короче четырёх."""
    return token[:max(4, len(token) - 3)]


MODIFIER_ENDINGS = ("ий", "ый", "ой", "ая", "ое", "ие", "ые", "ть")  # одиночные прилагательные и глаголы — слишком общие


def mentions(text, rows, self_id, empty):
    """Записи реестра, чьё наименование (или синоним) встречается в тексте источника.
    Слова сравниваются по основе (падежи); совпадения внутри более длинных отбрасываются."""
    toks = [_stem(t) for t in _tokens(text)]
    hits = []
    for r in rows:
        if r["id"] == self_id:
            continue
        names = [r["Наименование ru"]] + ([] if r["Синонимы"] == empty else r["Синонимы"].split(", "))
        for name in names:
            raw = _tokens(name)
            name_toks = [_stem(t) for t in raw]
            if not raw or (len(raw) == 1 and (len(raw[0]) < 8 or raw[0].endswith(MODIFIER_ENDINGS))):
                continue
            n = len(name_toks)
            for i in range(len(toks) - n + 1):
                if toks[i:i + n] == name_toks:
                    hits.append((i, i + n, r))
                    break
    keep = [h for h in hits if not any(o is not h and o[0] <= h[0] and h[1] <= o[1] and (o[1] - o[0]) > (h[1] - h[0])
                                       for o in hits)]
    return list(dict.fromkeys(h[2]["id"] for h in keep))


def label(row, empty):
    """Как запись называется в «Связанных терминах»: Аббревиатура en или Наименование ru."""
    return row["Аббревиатура en"] if row["Аббревиатура en"] != empty else row["Наименование ru"]


def definition_links(row, rows, empty, source_cols, linked):
    """Элементы «запись — используется в определении» для записей, названных в источниках row.
    linked — подписи, уже стоящие в «Связанных терминах» (повторно не добавляются)."""
    text = "\n".join(row[c] for c in source_cols if row[c] != empty)
    by_id = {r["id"]: r for r in rows}
    out = []
    for rid in mentions(text, rows, row["id"], empty):
        name = label(by_id[rid], empty)
        if name not in linked and not any(name == o.split(" — ")[0] for o in out):
            out.append(f"{name} — {USED_IN_DEFINITION}")
    return out
