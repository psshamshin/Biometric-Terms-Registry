"""Шаг 4: разбор статьи на поля.

Заголовок — до первого «): ». В нём: русские варианты через «/», русская аббревиатура после «; »,
английские варианты в скобках (через «/»), английская аббревиатура после «, »,
устаревшие термины «исключен «...»», пометка «(синоним)».
Русские и английские варианты сопоставляются по порядку.

Необязательные ключи конфига (без них — разбор как у ГОСТ ISO/IEC 2382-37):
  markers.short_forms — после «; » аббревиатура (по шаблону) или краткая форма термина (→ синонимы);
  markers.qualifier   — кириллическая скобка после английской — уточнение области применения;
  markers.groups      — пары скобок групп (по умолчанию только круглые), например квадратные для английской группы;
  markers.parameters  — скобка с параметрами «ВЛОИ (N, R, T)» — обозначение, не синоним (→ «Примечания»);
  markers.note_list   — «Примечания» с пунктами «1 …», «2 …» на отдельных строках;
  markers.example_list — то же для «Примеры»;
  abbreviations       — разбор раздела «Сокращения».
"""
import re

CYRILLIC = re.compile(r"[А-Яа-яЁё]")
LATIN = re.compile(r"[A-Za-z]")


def _join(lines):
    return re.sub(r" {2,}", " ", " ".join(lines)).strip()


def _tokens(head, synonym_marker, qualifier=False, groups=None, params=None):
    """Заголовок → последовательность ('text', s) / ('en', s) / ('mark', s) / ('qualifier', s) / ('params', s)
    по скобкам верхнего уровня. groups — пары скобок {открывающая: закрывающая}."""
    groups = groups or {"(": ")"}
    tokens, buf, depth, group, opening = [], "", 0, "", None
    for ch in head:
        if depth == 0 and ch in groups:
            if buf.strip():
                tokens.append(("text", buf.strip()))
            buf, group, opening, depth = "", "", ch, 1
        elif depth and ch == opening:
            group += ch
            depth += 1
        elif depth and ch == groups[opening]:
            depth -= 1
            if depth == 0:
                g = group.strip()
                if g == synonym_marker:
                    tokens.append(("mark", g))
                elif params and re.fullmatch(params, g):
                    tokens.append(("params", g))
                elif LATIN.search(g):
                    tokens.append(("en", g))
                elif qualifier and tokens and tokens[-1][0] == "en":
                    tokens.append(("qualifier", g))
                else:  # кириллическая скобка — часть русского наименования
                    buf = (tokens.pop()[1] if tokens and tokens[-1][0] == "text" else "") + f" ({g})"
            else:
                group += ch
        elif depth:
            group += ch
        else:
            buf += ch
    if depth:
        raise ValueError("непарные скобки")
    if buf.strip():
        tokens.append(("text", buf.strip()))
    return tokens


def parse_header(head, num, cfg):
    """Возвращает dict с полями заголовка. ValueError — заголовок не разобран."""
    m = cfg["markers"]
    short = m.get("short_forms")
    params = (m.get("parameters") or {}).get("pattern")
    param_form = re.compile(r"^(?P<base>\S+) \((?P<p>[^()]+)\)$")
    chunks = []  # каждый фрагмент: русские варианты + английская скобка
    for kind, value in _tokens(head, m["synonym_marker"], bool(m.get("qualifier")), m.get("groups"), params):
        if kind == "text":
            names = [v.strip() for v in value.split(m["variant_sep"]) if v.strip()]
            if not names:
                raise ValueError(f"пустой русский вариант: {value!r}")
            chunks.append({"ru": names, "en": [], "abbr_en": None, "synonym_mark": False,
                           "ru_short": [], "en_short": [], "qualifier": None, "ru_params": [], "en_params": []})
        elif not chunks:
            raise ValueError(f"скобка до русского наименования: {value!r}")
        elif kind == "mark":
            chunks[-1]["synonym_mark"] = True
        elif kind == "qualifier":
            chunks[-1]["qualifier"] = value
        elif kind == "params":  # «… ; ВЛОИ (N, R, T)» — обозначение относится к последней части перед скобкой
            name = chunks[-1]["ru"][-1]
            head_part, _, base = name.rpartition(m["abbr_ru_sep"])
            if not head_part:
                raise ValueError(f"скобка с параметрами без обозначения: {value!r}")
            chunks[-1]["ru"][-1] = head_part
            chunks[-1]["ru_params"].append((base, f"{base} ({value})"))
        else:
            if chunks[-1]["en"]:
                raise ValueError(f"две английские скобки подряд: {value!r}")
            parts = value.split("; ")
            en, excluded, abbr_en = parts[0], [], None
            for extra in parts[1:]:
                pm = param_form.match(extra) if params else None
                if re.match(m["excluded"], extra):
                    excluded += re.findall(m["excluded_term"], extra)
                elif pm and re.fullmatch(params, pm.group("p")):
                    chunks[-1]["en_params"].append((pm.group("base"), extra))
                elif short and re.fullmatch(short["abbr_en"], extra) and abbr_en is None:
                    abbr_en = extra
                elif short:
                    chunks[-1]["en_short"].append(extra)
                else:
                    raise ValueError(f"неизвестная часть в скобках: {extra!r}")
            if m.get("abbr_en_sep") and m["abbr_en_sep"] in en:
                en, abbr_en = en.rsplit(m["abbr_en_sep"], 1)
            chunks[-1].update(en=[v.strip() for v in en.split(m["variant_sep"])],
                              abbr_en=abbr_en, excluded=excluded)
    if not chunks or not chunks[0]["en"]:
        raise ValueError("нет английского эквивалента")

    override = (cfg.get("header_overrides") or {}).get(num)
    if override and "en_variants" in override:
        if sorted(override["en_variants"]) != sorted(chunks[0]["en"]):
            raise ValueError(f"header_overrides: {override['en_variants']} ≠ {chunks[0]['en']}")
        chunks[0]["en"] = list(override["en_variants"])

    first = chunks[0]
    term_ru, abbr_ru = first["ru"][0], None
    if m["abbr_ru_sep"] in term_ru and not short:
        term_ru, abbr_ru = term_ru.split(m["abbr_ru_sep"], 1)
    elif m["abbr_ru_sep"] in term_ru:  # после «; » — аббревиатура (по шаблону) или краткая форма, частей может быть несколько
        term_ru, *tails = term_ru.split(m["abbr_ru_sep"])
        for tail in tails:
            if re.fullmatch(short["abbr_ru"], tail) and abbr_ru is None:
                abbr_ru = tail
            else:
                first["ru_short"].append(tail)

    # Обычной аббревиатуры нет — основа обозначения с параметрами (СЕЛ (N, R, T) → СЕЛ).
    if abbr_ru is None and short:
        abbr_ru = next((b for c in chunks for b, _ in c["ru_params"] if re.fullmatch(short["abbr_ru"], b)), None)
    abbr_en = next((c["abbr_en"] for c in chunks if c["abbr_en"]), None)
    if abbr_en is None and short:
        abbr_en = next((b for c in chunks for b, _ in c["en_params"] if re.fullmatch(short["abbr_en"], b)), None)

    syn_ru, syn_en, synonyms = [], [], []
    for i, ch in enumerate(chunks):
        for j, name in enumerate(ch["ru"] + ch["ru_short"]):
            if (i, j) != (0, 0):
                syn_ru.append(name)
                synonyms.append(name)
        for j, name in enumerate(ch["en"] + ch["en_short"]):
            if (i, j) != (0, 0):
                syn_en.append(name)
                synonyms.append(name)
    return {
        "term_ru": term_ru,
        "abbr_ru": abbr_ru,
        "term_en": first["en"][0],
        "abbr_en": abbr_en,
        "synonyms": synonyms,
        "synonyms_ru": syn_ru,
        "synonyms_en": syn_en,
        "synonym_marked": [n for c in chunks if c["synonym_mark"] for n in c["ru"]],
        "excluded": [e for c in chunks for e in c.get("excluded", [])],
        "qualifier": next((c["qualifier"] for c in chunks if c["qualifier"]), None),
        "param_forms": [f for c in chunks for _, f in c["ru_params"] + c["en_params"]],
    }


def parse_article(article, cfg, log):
    m = cfg["markers"]
    lines = [l for _, l in article["lines"]]
    flags = []

    note_list = m.get("note_list")
    example_list = m.get("example_list")

    def list_cfg(line):
        for cfg_list, target in ((note_list, "notes"), (example_list, "examples")):
            if cfg_list and re.match(cfg_list["heading"], line):
                return cfg_list, target
        return None

    def is_list_heading(line):
        return list_cfg(line) is not None

    # Блоки «Пример» / «Примечание» / «Примечания» начинаются с новой строки.
    starts = [i for i, l in enumerate(lines)
              if re.match(m["example"], l) or re.match(m["note"], l) or is_list_heading(l)]
    head_end = starts[0] if starts else len(lines)
    head_text = _join(lines[:head_end])

    examples, notes = [], []
    for k, i in enumerate(starts):
        end = starts[k + 1] if k + 1 < len(starts) else len(lines)
        if is_list_heading(lines[i]):  # «Примечания» / «Примеры»: каждый пункт «1 …», «2 …» — отдельная запись
            cfg_list, target = list_cfg(lines[i])
            items = []
            for line in lines[i + 1:end]:
                if re.match(cfg_list["item"], line):
                    items.append([re.sub(cfg_list["item"], "", line, count=1)])
                elif items:
                    items[-1].append(line)
                else:
                    raise ValueError(f"{article['num']}: текст между «{lines[i]}» и первым пунктом: {line!r}")
            (notes if target == "notes" else examples).extend(_join(item) for item in items)
            continue
        block = _join(lines[i:end])
        if re.match(m["note"], block):
            notes.append(re.sub(m["note"], "", block, count=1))
        else:
            examples.append(re.sub(m["example"], "", block, count=1))

    result = {
        "num": article["num"],
        "section": article["section"],
        "page": article["page"],
        "raw": "\n".join(lines),
        "term_ru": None, "abbr_ru": None, "term_en": None, "abbr_en": None,
        "synonyms": [], "synonyms_ru": [], "synonyms_en": [], "synonym_marked": [], "excluded": [],
        "qualifier": None, "param_forms": [],
        "definition": None,
        "examples": examples,
        "notes": notes,   # нумерация — по порядку появления
        "corrections": article.get("corrections", []),
        "flags": flags,
        "flag_reasons": {},
    }

    hm = re.match(m["header"], head_text)
    try:
        if not hm:
            raise ValueError("не найден конец заголовка «): »")
        result.update(parse_header(hm.group("head"), article["num"], cfg))
        result["definition"] = hm.group("definition").strip() or None
    except ValueError as e:
        flags.append("header_unparsed")
        result["flag_reasons"]["header_unparsed"] = str(e)

    # Угаданный перенос в заголовке или определении (поля реестра) — флаг; в примерах и примечаниях — только журнал.
    guessed = [w for _, w in log.hyphen_guesses if w in head_text]
    if guessed:
        flags.append("hyphen_guess")
        result["flag_reasons"]["hyphen_guess"] = "перенос дефисом угадан: " + ", ".join(guessed)

    # Первыми пунктами «Примечаний»: уточнение области, затем обозначения с параметрами.
    prefix = []
    if result["qualifier"]:
        prefix.append(m["qualifier"]["note_label"] + result["qualifier"])
    if result["param_forms"]:
        prefix.append(m["parameters"]["note_label"] + "; ".join(result["param_forms"]))
    notes[:0] = prefix

    if result["term_ru"]:
        t = result["term_ru"]
        cap = t[:1].upper() + t[1:]
        if cap != t:
            log.add(article["page"], t, cap, f"первая буква заглавная ({article['num']})")
        result["term_ru"] = cap

    if result["corrections"]:
        flags.append("ocr_fixed")
        result["flag_reasons"]["ocr_fixed"] = "; ".join(f"{c['было']} → {c['стало']}" for c in result["corrections"])

    suspects = [v for v in [result["term_en"], result["abbr_en"], *result["synonyms_en"], *result["excluded"]]
                if v and CYRILLIC.search(v)]
    suspects += [v for v in [result["term_ru"], result["abbr_ru"], *result["synonyms_ru"]]
                 if v and LATIN.search(v)]
    if suspects:
        flags.append("ocr_suspect")
        result["flag_reasons"]["ocr_suspect"] = ", ".join(suspects)
    return result


def parse_abbreviations(lines, cfg):
    """Раздел «Сокращения» → [{abbr_ru, abbr_en, text_ru, text_en, page}].
    Запись начинается строкой по шаблону abbreviations.entry; следующие строки — её продолжение."""
    a = cfg["abbreviations"]
    entries = []
    for page, line in lines:
        m = re.match(a["entry"], line)
        if m:
            abbr_en = m.groupdict().get("abbr_en")  # у некоторых стандартов в разделе только русские сокращения
            entries.append({"abbr_ru": m.group("abbr_ru").strip(), "abbr_en": abbr_en.strip() if abbr_en else None,
                            "text": m.group("text"), "page": page})
        elif entries:
            entries[-1]["text"] += " " + line
        else:
            raise ValueError(f"строка до первой записи сокращений (стр. {page}): {line}")
    out = []
    for e in entries:
        x = re.match(a["expansion_en"], _join([e["text"]]))
        out.append({"abbr_ru": e["abbr_ru"], "abbr_en": e["abbr_en"],
                    "text_ru": x.group("ru").strip(), "text_en": x.group("en"), "page": e["page"]})
    return out


def apply_abbreviations(parsed, abbreviations):
    """Сопоставляет сокращения со статьями по Наименованию ru или en (без учёта регистра).
    Нет аббревиатуры в статье — заполняется из раздела; есть и отличается — только строка в отчёт.
    Возвращает (действия [(пункт, поле, из раздела, в статье, действие)], несопоставленные сокращения)."""
    actions, unmatched = [], []
    for a in abbreviations:
        rec = next((p for p in parsed
                    if (p["term_ru"] or "").lower() == a["text_ru"].lower()
                    or (a["text_en"] and (p["term_en"] or "").lower() == a["text_en"].lower())), None)
        if rec is None:
            unmatched.append(a)
            continue
        for field, value in (("abbr_ru", a["abbr_ru"]), ("abbr_en", a["abbr_en"])):
            if not value:
                continue
            if not rec[field]:
                rec[field] = value
                actions.append((rec["num"], field, value, None, "заполнено из раздела «Сокращения»"))
            elif rec[field] != value:
                actions.append((rec["num"], field, value, rec[field], "отличается от статьи, не изменено"))
    return actions, unmatched
