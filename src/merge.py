"""Шаг 5: объединение реестров подключённых стандартов в общий реестр.

Правила — в config/merge.yaml (priority, служебные колонки, нормализация Наименования en).
Одна строка на ключ — и для записей разных стандартов, и для повторов внутри одного стандарта:
  - Аббревиатура en и Область совпали — одна строка;
  - аббревиатуры нет ни у одной записи, совпали Наименование en и Область — одна строка;
  - Аббревиатура en совпала, Область разная — не объединять, флаг area_conflict;
  - Наименование en совпало, аббревиатура или область разные — не объединять, флаг merge_candidate.
"""
import json
import re

from src import checks
from src.build import write_outputs
from src.curated import apply_curated


def _empty(v, empty):
    return v is None or v == empty


def norm_en(name, rules):
    s = name or ""
    if rules.get("lowercase"):
        s = s.lower()
    if rules.get("hyphen_as_space"):
        s = s.replace("-", " ")
    return re.sub(r"\s+", " ", s).strip()


def load_records(merge_cfg, schema, out_dir):
    """Строки реестров стандартов из data/out/{std_id}/registry.json в порядке priority."""
    empty = schema["empty"]
    records = []
    for sid in merge_cfg["priority"]:
        rows = json.loads((out_dir / sid / "registry.json").read_text(encoding="utf-8"))
        for row in rows:
            records.append({"sid": sid, "row": {k: (empty if v is None else v) for k, v in row.items()}})
    return records


def _group_key(rec, rules, empty):
    row = rec["row"]
    if not _empty(row["Аббревиатура en"], empty):
        return ("abbr", row["Аббревиатура en"], row["Область (часть ключа)"])
    return ("name", norm_en(row["Наименование en"], rules), row["Область (часть ключа)"])


def group_records(records, merge_cfg, empty):
    """Группы записей для объединения: одинаковый ключ — одна группа, в том числе внутри одного стандарта."""
    rules = merge_cfg["name_en_normalize"]
    groups, by_key = [], {}
    for rec in records:
        key = _group_key(rec, rules, empty)
        if key not in by_key:
            by_key[key] = []
            groups.append(by_key[key])
        by_key[key].append(rec)
    return groups


def find_conflicts(groups, merge_cfg, empty):
    """area_conflict и merge_candidate между записями разных стандартов в разных группах."""
    rules = merge_cfg["name_en_normalize"]
    conflicts = []
    flat = [(gi, rec) for gi, g in enumerate(groups) for rec in g]
    for i, (gi, a) in enumerate(flat):
        for gj, b in flat[i + 1:]:
            if gi == gj:
                continue
            ra, rb = a["row"], b["row"]
            same_abbr = not _empty(ra["Аббревиатура en"], empty) and ra["Аббревиатура en"] == rb["Аббревиатура en"]
            same_area = ra["Область (часть ключа)"] == rb["Область (часть ключа)"]
            same_name = norm_en(ra["Наименование en"], rules) == norm_en(rb["Наименование en"], rules)
            if same_abbr and not same_area:
                flag = "area_conflict"
                detail = f"{ra['Аббревиатура en']}: «{ra['Область (часть ключа)']}» ≠ «{rb['Область (часть ключа)']}»"
            elif same_name and not _empty(ra["Наименование en"], empty):
                flag = "merge_candidate"
                detail = (f"{ra['Наименование en']}: аббревиатура {ra['Аббревиатура en']} / {rb['Аббревиатура en']}, "
                          f"область «{ra['Область (часть ключа)']}» / «{rb['Область (часть ключа)']}»")
            else:
                continue
            conflicts.append({"flag": flag, "groups": (gi, gj), "a": a, "b": b, "detail": detail})
    return conflicts


def _dedupe(values, empty):
    seen, out = set(), []
    for v in values:
        if _empty(v, empty) or v.lower() in seen:
            continue
        seen.add(v.lower())
        out.append(v)
    return out


def source_text(values, empty):
    """Формулировки одного источника из нескольких записей: «п. 3.23 — текст» + «п. 3.35 — текст».
    Тексты совпадают — «п. 3.23, 3.35 — текст»; различаются — «п. 3.23 — …; п. 3.35 — …»."""
    if not values:
        return empty
    if len(values) == 1:
        return values[0]
    parsed = [re.match(r"^п\. (?P<num>\S+) — (?P<text>.*)$", v, re.S) for v in values]
    if all(parsed) and len({p.group("text") for p in parsed}) == 1:
        return f"п. {', '.join(p.group('num') for p in parsed)} — {parsed[0].group('text')}"
    return "; ".join(values)


def _split(value, sep, empty):
    return [] if _empty(value, empty) else value.split(sep)


def merge_group(group, schema, merge_cfg, conflict_flags):
    """Одна строка общего реестра из группы записей (записи — в порядке priority)."""
    empty = schema["empty"]
    rules = merge_cfg["name_en_normalize"]
    sep = merge_cfg["list_sep"]
    flags, reasons = list(conflict_flags), {}
    row = {c["name"]: empty for c in schema["columns"]}
    primary = group[0]["row"]

    for col in (c["name"] for c in schema["columns"] if c["filled_by"] == "source"):
        row[col] = source_text([r["row"][col] for r in group if not _empty(r["row"][col], empty)], empty)
    row["Ссылки для проверки"] = "; ".join(
        _dedupe([l for r in group for l in _split(r["row"]["Ссылки для проверки"], "; ", empty)], empty)) or empty

    extra_synonyms = []
    for col, same in (("Наименование ru", lambda a, b: a.lower() == b.lower()),
                      ("Аббревиатура ru", lambda a, b: a == b),
                      ("Наименование en", lambda a, b: norm_en(a, rules) == norm_en(b, rules))):
        values = [(r["sid"], r["row"][col]) for r in group if not _empty(r["row"][col], empty)]
        row[col] = values[0][1] if values else empty
        for sid, v in values[1:]:
            if not same(row[col], v):
                extra_synonyms.append(v)
                flags.append("name_conflict")
                reasons.setdefault("name_conflict", []).append(f"{col}: «{row[col]}» / {sid}: «{v}»")

    for col in ("id", "Аббревиатура en", "Область (часть ключа)"):
        row[col] = primary[col]
    syn_sep = ", "
    chosen = {row[c].lower() for c in ("Наименование ru", "Наименование en", "Аббревиатура ru")
              if not _empty(row[c], empty)}
    synonyms = [s for s in _dedupe([s for r in group for s in _split(r["row"]["Синонимы (все)"], syn_sep, empty)]
                                   + extra_synonyms, empty) if s.lower() not in chosen]
    max_syn = next(r["list"]["max_items"] for r in checks.column_spec(schema, "Синонимы")["rules"] if "list" in r)
    if len(synonyms) > max_syn:
        flags.append("synonyms_over_limit")
    row["Синонимы"] = syn_sep.join(synonyms[:max_syn]) or empty

    types = {r["row"]["Тип сущности"] for r in group}
    if len(types) == 1:
        row["Тип сущности"] = types.pop()
    else:
        row["Тип сущности"] = "термин"
        flags.append("type_conflict")
        reasons["type_conflict"] = [", ".join(f"{r['sid']}: {r['row']['Тип сущности']}" for r in group)]
    row["Статус"] = "черновик" if row["Тип сущности"] == "метрика" else "отложено"

    link_sep = checks._list_sep(schema, "Связанные термины")
    row["Связанные термины"] = link_sep.join(
        _dedupe([l for r in group for l in _split(r["row"]["Связанные термины"], link_sep, empty)], empty)) or empty

    source_flags = [f"{r['sid']}{merge_cfg['flag_prefix_sep']}{f}"
                    for r in group for f in _split(r["row"]["Флаги"], ", ", empty)]
    row.update({
        "Ключ": primary["Ключ"],
        "Источники": sep.join(dict.fromkeys(r["sid"] for r in group)),
        "Синонимы (все)": syn_sep.join(synonyms) or empty,
        "Флаги": sep.join(_dedupe(flags + source_flags, empty)) or empty,
    })
    return row, reasons


def merge_registries(merge_cfg, schema, out_dir, curated_dir=None):
    """curated_dir — папка слоя curated (data/curated/); None — без подмешивания."""
    empty = schema["empty"]
    records = load_records(merge_cfg, schema, out_dir)
    groups = group_records(records, merge_cfg, empty)
    conflicts = find_conflicts(groups, merge_cfg, empty)
    group_flags = {}
    for c in conflicts:
        for gi in c["groups"]:
            group_flags.setdefault(gi, []).append(c["flag"])

    merged = []
    for gi, group in enumerate(groups):
        row, reasons = merge_group(group, schema, merge_cfg, group_flags.get(gi, []))
        merged.append({"row": row, "group": group, "reasons": reasons})
    merged.sort(key=lambda m: (m["row"]["Ключ"], m["row"]["Источники"], m["group"][0]["row"]["Пункт"]))

    used, id_collisions = {}, []
    for m in merged:  # id — из первого по priority источника; совпал — суффикс
        base, rid, n = m["row"]["id"], m["row"]["id"], 1
        while rid in used:
            n += 1
            rid = f"{base}-{n}"
        if rid != base:
            m["row"]["Флаги"] = ", ".join(["id_collision"] + _split(m["row"]["Флаги"], ", ", empty))
            id_collisions.append((m, used[base], rid))
        used[rid] = m
        m["row"]["id"] = rid

    rows = [m["row"] for m in merged]
    curated = apply_curated(rows, schema, curated_dir) if curated_dir is not None else None
    columns = [c["name"] for c in schema["columns"]] + merge_cfg["service_columns"]
    write_outputs(rows, schema, out_dir, columns)

    violations, _ = checks.check_schema(rows, schema, id_col="Ключ")
    result = {
        "rows": rows, "merged": merged, "records": records, "conflicts": conflicts,
        "id_collisions": id_collisions, "violations": violations, "curated": curated,
        "dict_errors": checks.check_dictionaries(rows, schema, id_col="Ключ",
                                                 free_status_keys=curated["status_keys"] if curated else ()),
        "key_duplicates": sorted({r["Ключ"] for r in rows if sum(x["Ключ"] == r["Ключ"] for x in rows) > 1}),
    }
    write_merge_report(out_dir / "merge_report.md", result, schema, merge_cfg)
    return result


def _ref(rec):
    return f"{rec['sid']} п. {rec['row']['Пункт']}"


def write_merge_report(path, res, schema, merge_cfg):
    t, empty = checks._table, schema["empty"]
    rows, merged = res["rows"], res["merged"]
    s = ["# Отчёт объединения → общий реестр\n"]
    s.append(f"Порядок источников (priority): {', '.join(merge_cfg['priority'])}.\n")

    s.append("\n## Записи по стандартам\n")
    per_std = {sid: sum(r["sid"] == sid for r in res["records"]) for sid in merge_cfg["priority"]}
    only = {sid: sum({r["sid"] for r in m["group"]} == {sid} for m in merged) for sid in merge_cfg["priority"]}
    s.append(t(["Стандарт", "Записей", "Строк только из него"], [(k, v, only[k]) for k, v in per_std.items()]))
    s.append(f"\nСтрок в общем реестре: {len(rows)}; объединено из нескольких стандартов: "
             f"{sum(len({r['sid'] for r in m['group']}) > 1 for m in merged)}; "
             f"из повторов внутри одного стандарта: {sum(len(m['group']) > len({r['sid'] for r in m['group']}) for m in merged)}.\n")

    s.append("\n## Объединённые строки\n")
    s.append(t(["Ключ", "Записи"], [(m["row"]["Ключ"], ", ".join(_ref(r) for r in m["group"]))
                                    for m in merged if len(m["group"]) > 1]))

    s.append("\n## Конфликты объединения\n")
    conf_rows = [(c["flag"], _ref(c["a"]), _ref(c["b"]), c["detail"]) for c in res["conflicts"]]
    for m in merged:
        for flag, reasons in m["reasons"].items():
            for reason in reasons:
                conf_rows.append((flag, ", ".join(_ref(r) for r in m["group"]), "", reason))
    for m, other, rid in res["id_collisions"]:
        conf_rows.append(("id_collision", _ref(m["group"][0]), _ref(other["group"][0]),
                          f"id «{other['row']['id']}» занят; выдан «{rid}»"))
    s.append(t(["Флаг", "Запись", "Другая запись", "Подробности"], conf_rows))

    s.append("\n## Проверки общего реестра\n")
    s.append(t(["Проверка", "Результат"], [
        ("Схема", f"нарушений: {len(res['violations'])}"),
        ("Справочники", f"значений вне справочника: {len(res['dict_errors'])}"),
        ("Дубли ключа", ", ".join(res["key_duplicates"]) or "нет"),
        ("Связи", f"метрик без пары: {len(checks.unpaired_metrics(rows, schema, id_col='Ключ'))}"),
    ]))
    if res["violations"]:
        s.append("\n" + t(["Ключ", "Колонка", "Правило", "Значение"], res["violations"]))
    if res["dict_errors"]:
        s.append("\n" + t(["Ключ", "Колонка", "Значение"], res["dict_errors"]))

    cur = res["curated"]
    if cur is not None:
        s.append("\n## Слой curated (data/curated/)\n")
        s.append(f"Файлов: {cur['files']}; применено: {len(cur['applied'])}; llm_stale: {len(cur['stale'])}; "
                 f"curated_orphan: {len(cur['orphans'])}; ошибок в файлах: {len(cur['problems'])}.\n")
        if cur["stale"]:
            s.append("\nllm_stale — тексты нужно перегенерировать:\n\n" + t(["id", "Причина"], cur["stale"]))
        if cur["orphans"]:
            s.append("\ncurated_orphan — нет строки с таким id:\n\n" + t(["Файл", "id"], cur["orphans"]))
        if cur["problems"]:
            s.append("\nОшибки в curated-файлах:\n\n" + t(["Файл", "Поле", "Проблема"], cur["problems"]))

    s.append("\n## Метрики общего реестра\n")
    source_cols = [c["name"] for c in schema["columns"] if c["filled_by"] == "source"]
    metric_rows = [r for r in rows if r["Тип сущности"] == "метрика"]
    s.append(t(["Ключ", "Наименование ru", "Наименование en", "Источники"] + source_cols,
               [[r["Ключ"], r["Наименование ru"], r["Наименование en"], r["Источники"]] + [r[c] for c in source_cols]
                for r in metric_rows]))
    path.write_text("\n".join(s), encoding="utf-8")
