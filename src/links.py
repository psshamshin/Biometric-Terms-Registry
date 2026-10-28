"""Записи реестра, названные в формулировке источника: связь «используется в определении».

Строится автоматически по тексту колонок источников (build.py); проверка полноты — блок «д» в validation.py.
Сопоставление детерминированное: словоформы (падеж, число), сокращения (из записи и из раздела «Сокращения»
стандартов), синонимы записи. Каждая связь подтверждается словом (словами) из формулировки.
"""
import re

USED_IN_DEFINITION = "используется в определении"


def _tokens(text):
    return re.findall(r"[a-zа-я0-9]+", text.lower().replace("ё", "е"))


def _stem(token):
    """Основа слова для сравнения падежей: без последних трёх букв, но не короче четырёх."""
    return token[:max(4, len(token) - 3)]


def _same_word(a, b):
    """Одно слово в разных словоформах: совпали основы или общее начало почти всего более короткого слова
    (вид — вида — видом; инструмент — инструментов; биометрическое — биометрическими)."""
    if a == b or _stem(a) == _stem(b):
        return True
    if abs(len(a) - len(b)) > 4:
        return False
    common = 0
    for x, y in zip(a, b):
        if x != y:
            break
        common += 1
    shortest = min(len(a), len(b))
    if max(len(a), len(b)) - common > 3:  # после общего начала — только окончание, а не другой корень (заявку ≠ заявитель)
        return False
    if shortest < 4:
        return common == shortest >= 3
    return common >= max(4, shortest - 3)


MODIFIER_ENDINGS = ("ий", "ый", "ой", "ая", "ое", "ие", "ые", "ть")  # одиночные прилагательные и глаголы — слишком общие
ADJECTIVE_ENDINGS = ("ой", "ый", "ий", "ая", "ое", "ие", "ые", "ого", "ых", "ым", "ими", "ыми", "ую")  # слово внутри названия


def _find(toks, name_toks):
    """Позиция названия в тексте: слова по порядку; между словами названия допускается одно прилагательное
    («транзакций биометрической идентификации» для «транзакция идентификации»)."""
    n = len(name_toks)
    for allow_gap in (False, True):  # сначала дословный порядок слов, потом — с одним прилагательным внутри
        for i in range(len(toks)):
            j, k, gap = i, 0, False
            while k < n and j < len(toks):
                if _same_word(toks[j], name_toks[k]):
                    j, k = j + 1, k + 1
                elif allow_gap and k and not gap and toks[j].endswith(ADJECTIVE_ENDINGS) and j + 1 < len(toks):
                    j, gap = j + 1, True
                else:
                    break
            if k == n:
                return i, j, gap
    return None


def abbreviation_aliases(rows, abbreviations, empty):
    """Раздел «Сокращения» стандартов → {id записи: [сокращения]}: расшифровка сокращения совпала с наименованием записи
    (ВИАБП — «вид инструмента атаки на биометрическое предъявление» = «Вид инструментов атаки на …»).
    abbreviations — список словарей с ключами abbr_ru, abbr_en, text_ru."""
    aliases = {}
    for a in abbreviations:
        exp = _tokens(a["text_ru"])
        if not exp:
            continue
        for r in rows:
            names = [r["Наименование ru"]] + ([] if r["Синонимы"] == empty else r["Синонимы"].split(", "))
            if any(len(t) == len(exp) and all(map(_same_word, t, exp)) for t in map(_tokens, names)):
                found = [x for x in (a["abbr_ru"], a["abbr_en"]) if x and x != empty]
                known = aliases.setdefault(r["id"], [])
                known.extend(x for x in found if x not in known)
    return aliases


def _abbreviations(r, aliases, empty):
    own = [r[c] for c in ("Аббревиатура en", "Аббревиатура ru") if r[c] != empty]
    return [a for a in own + list((aliases or {}).get(r["id"], [])) if len(a) >= 3]


def abbreviation_hits(text, rows, self_id, empty, aliases=None):
    """[(запись, сокращение)] — записи реестра, чьё сокращение (ru или en, в том числе из раздела «Сокращения»)
    стоит в тексте целым словом с тем же регистром. Порядок — как в rows; на запись одно сокращение."""
    words = set(re.findall(r"[A-Za-zА-Яа-яЁё0-9\-]+", text))
    hits = []
    for r in rows:
        if r["id"] == self_id:
            continue
        found = next((a for a in _abbreviations(r, aliases, empty) if a in words), None)
        if found:
            hits.append((r, found))
    return hits


def mentions(text, rows, self_id, empty, aliases=None):
    """Записи реестра, чьё наименование, синоним или сокращение встречается в тексте источника.
    Слова сравниваются по словоформам (падежи, число); совпадения внутри более длинных отбрасываются;
    сокращения — целым словом с тем же регистром (ОАБП, PAD)."""
    toks = _tokens(text)
    words = set(re.findall(r"[A-Za-zА-Яа-яЁё0-9\-]+", text))
    hits, abbr_ids = [], []
    for r in rows:
        if r["id"] == self_id:
            continue
        if any(a in words for a in _abbreviations(r, aliases, empty)):
            abbr_ids.append(r["id"])
            continue
        names = [r["Наименование ru"]] + ([] if r["Синонимы"] == empty else r["Синонимы"].split(", "))
        for name in names:
            raw = _tokens(name)
            if not raw or (len(raw) == 1 and (len(raw[0]) < 8 or raw[0].endswith(MODIFIER_ENDINGS))):
                continue
            found = _find(toks, raw)
            if found:
                hits.append((*found, r))
                break
    keep = [h for h in hits
            if not any(o is not h and o[0] <= h[0] and h[1] <= o[1] and (o[1] - o[0]) > (h[1] - h[0]) for o in hits)
            and not (h[2] and any(not o[2] and o[0] < h[1] and h[0] < o[1] for o in hits))]  # с вставкой — только если слова не заняты
    return list(dict.fromkeys([h[3]["id"] for h in keep] + abbr_ids))


def label(row, empty):
    """Как запись называется в «Связанных терминах»: Аббревиатура en или Наименование ru."""
    return row["Аббревиатура en"] if row["Аббревиатура en"] != empty else row["Наименование ru"]


def definition_links(row, rows, empty, source_cols, linked, aliases=None):
    """Элементы «запись — используется в определении» для записей, названных в источниках row.
    linked — подписи, уже стоящие в «Связанных терминах» (повторно не добавляются)."""
    text = "\n".join(row[c] for c in source_cols if row[c] != empty)
    by_id = {r["id"]: r for r in rows}
    out = []
    for rid in mentions(text, rows, row["id"], empty, aliases):
        name = label(by_id[rid], empty)
        if name not in linked and not any(name == o.split(" — ")[0] for o in out):
            out.append(f"{name} — {USED_IN_DEFINITION}")
    return out
