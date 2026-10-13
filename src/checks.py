"""Шаг 9: проверки. Все ограничения читаются из config/registry_schema.yaml."""
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = ROOT / "config/registry_schema.yaml"
MERGE_PATH = ROOT / "config/merge.yaml"

# Правила, которые проверяются не по одному значению, а по строке или таблице целиком.
ROW_OR_TABLE_RULES = {"unique", "links_exist", "links_cover_sources"}


def _yaml(path):
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def source_columns(extra=None):
    """Колонки источников — по одной на стандарт из merge.yaml, в его порядке (правило 3 prompts/add_gost.md).
    extra — колонка стандарта, который ещё не внесён в merge.yaml (прогон одного стандарта): ставится в конец."""
    names = [_yaml(ROOT / e["config"])["standard"]["source_column"] for e in _yaml(MERGE_PATH)["standards"]]
    if extra and extra not in names:
        names.append(extra)
    return names


def load_schema(path=SCHEMA_PATH, extra_source=None):
    """Схема с раскрытыми колонками источников и номерами колонок по порядку."""
    schema = _yaml(path)
    columns = []
    for col in schema["columns"]:
        if col.get("source_template"):
            template = {k: v for k, v in col.items() if k != "source_template"}
            columns += [dict(template, name=name) for name in source_columns(extra_source)]
        else:
            columns.append(col)
    for n, col in enumerate(columns, start=1):
        col["n"] = n
    schema["columns"] = columns
    return schema


def column_spec(schema, name):
    for col in schema["columns"]:
        if col["name"] == name:
            return col
    raise KeyError(name)


def _items(value, sep):
    return value.split(sep)


def check_rule(schema, rule, value, flags=()):
    """Проверяет одно правило для непустого значения. Возвращает текст нарушения или None."""
    if "pattern" in rule:
        if not re.fullmatch(rule["pattern"], value):
            return f"не соответствует шаблону {rule['pattern']}"
    elif "max_len" in rule:
        if len(value) > rule["max_len"]:
            return f"длина {len(value)} > {rule['max_len']}"
    elif "min_len" in rule:
        if len(value) < rule["min_len"]:
            return f"длина {len(value)} < {rule['min_len']}"
    elif "first_upper" in rule:
        if not value[:1].isupper():
            return "первая буква не заглавная"
    elif "enum" in rule:
        allowed = schema["dictionaries"][rule["enum"]]
        if value not in allowed:
            return f"значение вне справочника {rule['enum']}"
    elif "list" in rule:
        spec = rule["list"]
        items = _items(value, spec["sep"])
        if "max_items" in spec and len(items) > spec["max_items"]:
            return f"элементов {len(items)} > {spec['max_items']}"
        if "item_pattern" in spec:
            bad = [i for i in items if not re.fullmatch(spec["item_pattern"], i)]
            if bad:
                return f"элементы не соответствуют шаблону {spec['item_pattern']}: {bad}"
    elif "max_words" in rule:
        spec = rule["max_words"]
        words = [w for w in value.split() if w not in spec.get("ignore_tokens", [])]
        if len(words) > spec["max"]:
            return f"слов {len(words)} > {spec['max']}"
    elif "ends_with_any" in rule:
        if not any(value.endswith(e) for e in rule["ends_with_any"]):
            return f"не оканчивается на одно из {rule['ends_with_any']}"
    elif "min_link_type" in rule:
        if rule.get("exempt_flag") in flags:
            return None
        spec = rule["min_link_type"]
        sep = _list_sep(schema, "Связанные термины")
        n = sum(1 for i in _items(value, sep) if i.endswith(" — " + spec["type"]))
        if n < spec["min"]:
            return f"связей «{spec['type']}» {n} < {spec['min']}"
    elif ROW_OR_TABLE_RULES & rule.keys():
        return None
    else:
        raise ValueError(f"неизвестное правило в схеме: {rule}")
    return None


def _list_sep(schema, column_name):
    for rule in column_spec(schema, column_name)["rules"]:
        if "list" in rule:
            return rule["list"]["sep"]
    raise KeyError(column_name)


def validate_value(schema, col, value, entity_type, flags=()):
    """Проверяет значение колонки по правилам схемы. Пустое значение здесь не проверяется
    (обязательность — отдельная проверка). Возвращает список нарушений."""
    if value is None or value == schema["empty"]:
        return []
    errors = []
    for rule in col["rules"]:
        applies_to = rule.get("applies_to")
        if applies_to and entity_type not in applies_to:
            continue
        err = check_rule(schema, rule, value, flags)
        if err:
            errors.append(err)
    return errors


# ---------------------------------------------------------------- 9.1, 9.6, 9.7: схема и связи

def _flags(row, schema):
    """Флаги строки; у общего реестра флаги стандартов с префиксом «std_id: » — префикс отбрасывается."""
    if row["Флаги"] == schema["empty"]:
        return set()
    return {f.rsplit(": ", 1)[-1] for f in row["Флаги"].split(", ")}


def check_schema(rows, schema, id_col="Пункт"):
    """Возвращает (нарушения [(пункт, колонка, правило, значение)], счётчик «ждёт LLM» {колонка: n})."""
    empty = schema["empty"]
    violations, waiting = [], {c["name"]: 0 for c in schema["columns"] if c["filled_by"] == "llm"}
    source_cols = [c["name"] for c in schema["columns"] if c["filled_by"] == "source"]
    for row in rows:
        num, etype, status = row[id_col], row["Тип сущности"], row["Статус"]
        flags = _flags(row, schema)
        for col in schema["columns"]:
            name, req, value = col["name"], col["required"], row[col["name"]]
            if value == empty:
                if req == "always" or (req == "metric" and etype == "метрика"
                                       and col.get("required_exempt_flag") not in flags):
                    violations.append((num, name, "обязательно", value))
                elif req in ("for_approved", "metric_for_approved"):
                    applies = ((req == "for_approved" or etype == "метрика")
                               and col.get("required_exempt_flag") not in flags)
                    if applies and status == "утвержден":
                        violations.append((num, name, "обязательно к статусу «утвержден»", value))
                    elif applies and status == "черновик" and name in waiting:
                        waiting[name] += 1
                continue
            for err in validate_value(schema, col, value, etype, flags):
                violations.append((num, name, err, value))
        filled = [c for c in source_cols if row[c] != empty]
        for rule in schema.get("row_rules", []):
            if rule.get("at_least_one_source") and not filled:
                violations.append((num, "колонки источника", "хотя бы одна заполнена", empty))
        links_col = column_spec(schema, "Ссылки для проверки")
        if any(r.get("links_cover_sources") for r in links_col["rules"]):
            sep = _list_sep(schema, "Ссылки для проверки")
            links = [] if row[links_col["name"]] == empty else row[links_col["name"]].split(sep)
            designations = sorted(l.split(": ", 1)[0] for l in links)
            if designations != sorted(filled):
                violations.append((num, links_col["name"], "ссылка на каждую заполненную колонку источника",
                                   row[links_col["name"]]))
    violations += check_table_rules(rows, schema, id_col)
    return violations, waiting


def check_table_rules(rows, schema, id_col="Пункт"):
    empty = schema["empty"]
    out = []
    for col in schema["columns"]:
        for rule in col["rules"]:
            if rule.get("unique"):
                seen = {}
                for row in rows:
                    v = row[col["name"]]
                    if v != empty and v in seen:
                        out.append((row[id_col], col["name"], f"уникален (повтор с {seen[v]})", v))
                    seen.setdefault(v, row[id_col])
            if rule.get("links_exist"):
                known = {row["Аббревиатура en"] for row in rows} | {row["Наименование ru"] for row in rows}
                known.discard(empty)
                sep = _list_sep(schema, col["name"])
                for row in rows:
                    if row[col["name"]] == empty:
                        continue
                    for item in row[col["name"]].split(sep):
                        target = item.rsplit(" — ", 1)[0]
                        if target not in known:
                            out.append((row[id_col], col["name"], "запись есть в реестре", item))
    return out


def unpaired_metrics(rows, schema, id_col="Пункт"):
    return [r[id_col] for r in rows if r["Тип сущности"] == "метрика" and "no_pair" in _flags(r, schema)]


# ---------------------------------------------------------------- 9.2: справочники

def check_dictionaries(rows, schema, id_col="Пункт", free_status_keys=()):
    """Значения справочников. Парсер ставит только parser_allowed; любой статус из справочника допустим,
    только если он пришёл из curated-файла (free_status_keys — ключи таких строк общего реестра)."""
    out = []
    targets = {"Тип сущности": "entity_type", "Статус": "status", "Область (часть ключа)": "area"}
    for row in rows:
        for col, dict_name in targets.items():
            v = row[col]
            allowed = schema["parser_allowed"].get(dict_name, schema["dictionaries"][dict_name])
            if col == "Статус" and row.get("Ключ") in free_status_keys:
                allowed = schema["dictionaries"][dict_name]
            if v not in allowed:
                out.append((row[id_col], col, v))
    return out


# ---------------------------------------------------------------- 9.6: дубли ключа

def mark_key_duplicates(records):
    by_key = {}
    for r in records:
        by_key.setdefault(r["key"], []).append(r["num"])
    for r in records:
        others = [n for n in by_key[r["key"]] if n != r["num"]]
        if others:
            if "key_duplicate" not in r["flags"]:
                r["flags"].append("key_duplicate")
            r["flag_reasons"]["key_duplicate"] = f"ключ «{r['key']}» также у {', '.join(others)}"


# ---------------------------------------------------------------- 9.3: полнота по указателям

def parse_index(lines, cfg):
    entries = []
    unparsed = []
    for page, line in lines:
        m = re.match(cfg["index"]["entry"], line)
        if not m:
            unparsed.append((page, line))
            continue
        term = m.group("term")
        abbr = None
        am = re.match(r"^(.*?) \(([A-ZА-ЯЁ]{2,8})\)$", term)
        if am:
            term, abbr = am.groups()
        entries.append({"term": term, "abbr": abbr, "num": re.sub(r"\.+", ".", m.group("num")), "page": page})
    return entries, unparsed


def _bag(s):
    return tuple(sorted(re.sub(r"[«»,]", " ", s.lower()).split()))


def check_index(parsed, index_lines, cfg):
    """Расхождения: [(пункт, указатель, направление, термин, объяснение или None)]."""
    by_num = {p["num"]: p for p in parsed}
    gaps = {(str(g["пункт"]), g["указатель"], g["термин"].lower()): g["причина"]
            for g in cfg["index"].get("known_gaps", [])}
    out, unparsed_all = [], []
    for lang, lines in index_lines.items():
        entries, unparsed = parse_index(lines, cfg)
        unparsed_all += [(lang, page, line) for page, line in unparsed]
        norm = (_bag if lang == "ru" and cfg["index"].get("ru_word_order_free") else lambda s: s.lower())

        def names(p):
            if lang == "ru":
                return [p["term_ru"]] + p["synonyms_ru"]
            return [p["term_en"]] + p["synonyms_en"]

        covered = set()
        for e in entries:
            p = by_num.get(e["num"])
            if p is None:
                out.append((e["num"], lang, "в указателе, нет статьи", e["term"], None))
                continue
            article_names = {norm(n): n for n in names(p) if n}
            parts = e["term"].split(cfg["markers"]["variant_sep"]) if lang == "en" else [e["term"]]
            hits = [article_names.get(norm(part)) for part in parts]
            if not all(hits):
                out.append((e["num"], lang, "в указателе, нет в статье", e["term"],
                            gaps.get((e["num"], lang, e["term"].lower()))))
            covered.update((e["num"], h) for h in hits if h)
            abbr = p["abbr_ru"] if lang == "ru" else p["abbr_en"]
            if e["abbr"] and e["abbr"] != abbr:
                out.append((e["num"], lang, "аббревиатура указателя не совпадает", e["abbr"], None))
        for p in parsed:
            for n in names(p):
                if n and (p["num"], n) not in covered:
                    out.append((p["num"], lang, "в статье, нет в указателе", n, gaps.get((p["num"], lang, n.lower()))))
    return out, unparsed_all


# ---------------------------------------------------------------- 9.4: нумерация

def check_numbering(parsed):
    counts, problems = {}, []
    by_section = {}
    for p in parsed:
        by_section.setdefault(p["section"], []).append(p["num"])
    for section, nums in by_section.items():
        counts[section] = len(nums)
        seq = [int(n.rsplit(".", 1)[1]) for n in nums]
        dupes = sorted({n for n in nums if nums.count(n) > 1})
        if dupes:
            problems.append((section, f"дубли: {', '.join(dupes)}"))
        expected = list(range(1, max(seq) + 1))
        missing = sorted(set(expected) - set(seq))
        if missing:
            problems.append((section, f"пропуски: {', '.join(f'{section}.{m:02d}' for m in missing)}"))
        if seq != sorted(seq):
            problems.append((section, "нарушен порядок"))
    return counts, problems


# ---------------------------------------------------------------- 9.5: целостность статьи

def check_integrity(parsed, cfg, schema, furniture_keys):
    rules = schema["integrity"]
    page_number = re.compile(cfg["cleaning"]["page_number"])
    service = [re.compile(p.strip("^$")) for p in cfg["cleaning"]["service_lines"]]
    out = []
    for p in parsed:
        d = p["definition"] or ""
        foreign = [n for n in re.findall(cfg["numbering"]["any"], d) if n != p["num"]]
        if foreign:
            out.append((p["num"], "чужой номер в определении", ", ".join(foreign)))
        compact = re.sub(r"\s+", "", d)
        if any(k in compact for k in furniture_keys) or any(s.search(d) for s in service):
            out.append((p["num"], "остаток колонтитула или служебной строки", d))
        stray = [l for l in p["raw"].split("\n") if page_number.match(l)]
        if stray:
            out.append((p["num"], "строка — номер страницы", ", ".join(stray)))
        if d[-1:] in rules["bad_endings"]:
            out.append((p["num"], "определение заканчивается на «" + d[-1:] + "»", d[-40:]))
        if not rules["definition_min_len"] <= len(d) <= rules["definition_max_len"]:
            out.append((p["num"], f"длина определения {len(d)}", d[:60]))
    return out


# ---------------------------------------------------------------- 9.8: сверка с Miro

def _miro_norm(s):
    return re.sub(r"\s+", "", s).rstrip(".")


def check_miro(parsed, fixture):
    by_num = {p["num"]: p for p in parsed}
    out = []
    for item in fixture:
        num = str(item["пункт"])
        p = by_num.get(num)
        ours = (p or {}).get("definition") or ""
        if _miro_norm(ours) != _miro_norm(item["текст"]):
            out.append((num, item["текст"], ours or "— (нет статьи)"))
    return out


# ---------------------------------------------------------------- 9.9: эталон

def check_golden(rows, golden):
    by_num = {r["Пункт"]: r for r in rows}
    filled, mismatches = 0, []
    for entry in golden or []:
        for field, expected in entry.items():
            if field == "пункт" or expected is None:
                continue
            filled += 1
            got = by_num.get(entry["пункт"], {}).get(field)
            if got != str(expected):
                mismatches.append((entry["пункт"], field, str(expected), got))
    return filled, mismatches


# ---------------------------------------------------------------- отчёт

NO_INDEX = "не выполнялась: алфавитного указателя в стандарте нет"
NO_MIRO = "не выполнялась: стандарта нет в Miro"


def _md(v):
    v = "—" if v is None else str(v)
    return v.replace("|", "\\|").replace("\n", "<br>")


def _table(header, rows):
    if not rows:
        return "нет\n"
    out = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    out += ["| " + " | ".join(_md(c) for c in r) + " |" for r in rows]
    return "\n".join(out) + "\n"


def write_report(path, ctx):
    """ctx: schema, cfg, rows, parsed, violations, waiting, dict_errors, index, index_unparsed,
    numbering, integrity, miro, golden, golden_path, cleaning_counts, cleaning_log_path, abbreviations.
    index = None — указателя нет; miro = None — стандарта нет в Miro; abbreviations = None — раздела нет."""
    schema, rows, parsed = ctx["schema"], ctx["rows"], ctx["parsed"]
    metrics = [r for r in rows if r["Тип сущности"] == "метрика"]
    terms = [r for r in rows if r["Тип сущности"] == "термин"]
    conflicts = [r for r in terms if "type_conflict" in _flags(r, schema)]
    explained_flags = schema["flags"]
    flag_rows = [(p["num"], f, explained_flags.get(f, "НЕТ ОБЪЯСНЕНИЯ В СХЕМЕ"), p["flag_reasons"].get(f))
                 for p in parsed for f in p["flags"]]
    no_index, no_miro = ctx["index"] is None, ctx["miro"] is None
    unexplained_index = [] if no_index else [d for d in ctx["index"] if d[4] is None]
    counts, num_problems = ctx["numbering"]
    golden_filled, golden_bad = ctx["golden"]

    s = [f"# Отчёт: {ctx['cfg']['standard']['designation']} → черновой реестр\n"]
    s.append("## Сводка проверок\n")
    s.append(_table(["Проверка", "Результат"], [
        ("9.1 Схема", f"нарушений: {len(ctx['violations'])}"),
        ("9.2 Справочники", f"значений вне справочника: {len(ctx['dict_errors'])}"),
        ("9.3 Полнота по указателям", NO_INDEX if no_index else
            f"расхождений: {len(ctx['index'])}, из них без объяснения: "
            f"{len(unexplained_index)}; нераспознанных строк указателя: {len(ctx['index_unparsed'])}"),
        ("9.4 Нумерация", f"проблем: {len(num_problems)}"),
        ("9.5 Целостность статьи", f"проблем: {len(ctx['integrity'])}"),
        ("9.6 Дубли ключа", f"записей с key_duplicate: {sum('key_duplicate' in p['flags'] for p in parsed)}"),
        ("9.7 Связи", f"метрик без пары: {len(unpaired_metrics(rows, schema))}"),
        ("9.8 Сверка с Miro", NO_MIRO if no_miro else f"расхождений: {len(ctx['miro'])}"),
        ("9.9 Эталон", f"заполнено полей: {golden_filled}, расхождений: {len(golden_bad)}"),
        ("Флаги без объяснения", str(sum(f[2] == 'НЕТ ОБЪЯСНЕНИЯ В СХЕМЕ' for f in flag_rows))),
    ]))

    s.append("\n## Воронка\n")
    s.append(_table(["Этап", "Число"], [
        ("Статей найдено", len(parsed)),
        ("Исключено целиком", 0),
        ("Метрик (черновик)", len(metrics)),
        ("Терминов (отложено)", len(terms)),
        ("— из них с type_conflict", len(conflicts)),
    ]))

    s.append("\n## Флаги\n")
    s.append(_table(["Пункт", "Флаг", "Что значит", "Причина"], flag_rows))

    s.append("\n## Нарушения схемы\n")
    s.append(_table(["Пункт", "Колонка", "Правило", "Значение"], ctx["violations"]))

    s.append("\n## Справочники\n")
    s.append(_table(["Пункт", "Колонка", "Значение"], ctx["dict_errors"]))

    s.append("\n## Ждёт LLM (статус «черновик», поле «—»)\n")
    s.append(_table(["Колонка", "Записей"], list(ctx["waiting"].items())))

    s.append("\n## Нумерация\n")
    s.append(_table(["Раздел", "Статей"], list(counts.items())))
    s.append("\nПроблемы нумерации:\n\n" + _table(["Раздел", "Проблема"], num_problems))

    s.append("\n## Целостность статьи\n")
    s.append(_table(["Пункт", "Проблема", "Фрагмент"], ctx["integrity"]))

    s.append("\n## Сверка с алфавитными указателями\n")
    if no_index:
        s.append(NO_INDEX + ".\n")
    else:
        s.append(_table(["Пункт", "Указатель", "Расхождение", "Термин", "Объяснение"],
                        [d[:4] + (d[4] or "НЕ ОБЪЯСНЕНО",) for d in ctx["index"]]))
    if ctx["index_unparsed"]:
        s.append("\nНераспознанные строки указателей:\n\n" +
                 _table(["Указатель", "Стр.", "Строка"], ctx["index_unparsed"]))

    s.append("\n## Связи\n")
    s.append("Метрики без пары: " + (", ".join(unpaired_metrics(rows, schema)) or "нет") + "\n")

    if ctx.get("abbreviations") is not None:
        actions, unmatched, total = ctx["abbreviations"]
        s.append("\n## Раздел «Сокращения»\n")
        s.append(f"Сокращений в разделе: {total}; сокращений без определения в стандарте: {len(unmatched)} "
                 "(список — abbreviations.csv).\n")
        if actions:
            s.append("\nСопоставлены со статьями:\n\n" +
                     _table(["Пункт", "Поле", "В разделе", "В статье", "Действие"], actions))

    known_ocr = ctx["cfg"].get("known_ocr_errors") or []
    if known_ocr:
        s.append("\n## Известные ошибки распознавания (не исправлены)\n")
        s.append(_table(["Раздел", "В тексте", "На скане"],
                        [(e["раздел"], e["было"], e["на_скане"]) for e in known_ocr]))

    s.append("\n## Сверка с Miro\n")
    if no_miro:
        s.append(NO_MIRO + ".\n")
    else:
        s.append(_table(["Пункт", "Miro", "Разобрано"], ctx["miro"]))

    s.append(f"\n## Эталон ({ctx['golden_path']})\n")
    s.append(f"Заполнено полей: {golden_filled}.\n\n" +
             _table(["Пункт", "Колонка", "Эталон", "Разобрано"], golden_bad))

    s.append(f"\n## Журнал очистки ({ctx['cleaning_log_path']})\n")
    s.append(_table(["Правило", "Записей"], list(ctx["cleaning_counts"].items())))

    s.append("\n## Метрики — все колонки реестра\n")
    cols = [c["name"] for c in schema["columns"]] + schema["service_columns"]
    s.append(_table(["Колонка"] + [m["Пункт"] for m in metrics],
                    [[c] + [m[c] for m in metrics] for c in cols]))
    path.write_text("\n".join(s), encoding="utf-8")
