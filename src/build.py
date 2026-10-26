"""Шаги 6–8: id, ключ, строки реестра, выходные файлы.

Колонки и их порядок — из registry_schema.yaml (columns + service_columns).
"""
import csv
import json
import re
import sqlite3

from src.checks import mark_key_duplicates
from src.classify import _flag, area, classify, find_pairs
from src.links import definition_links

def make_id(rec, used, max_len):
    if rec["abbr_en"]:
        base = rec["abbr_en"].lower()
    else:
        base = re.sub(r"[^a-z0-9]+", "-", (rec["term_en"] or "").lower()).strip("-")
        if len(base) > max_len:
            cut = base[:max_len + 1].rsplit("-", 1)[0]
            _flag(rec, "id_truncated", f"{base} → {cut}")
            base = cut
    rid, n = base, 1
    while rid in used:
        n += 1
        rid = f"{base}-{n}"
    if rid != base:
        _flag(rec, "id_collision", f"id «{base}» уже выдан записи {used[base]}; выдан «{rid}»")
    used[rid] = rec["num"]
    return rid


def _norm(s):
    return re.sub(r"\s+", " ", s).strip().lower()


def mark_synonym_clashes(records):
    """Синоним совпадает с наименованием или синонимом другой записи → synonym_clash (синоним не удаляется)."""
    owners = {}
    for r in records:
        for kind, names in (("наименование", [r["term_ru"], r["term_en"]]), ("синоним", r["synonyms"])):
            for name in names:
                if name:
                    owners.setdefault(_norm(name), []).append((r["num"], kind, name))
    for r in records:
        clashes = []
        for syn in r["synonyms"]:
            for num, kind, name in owners[_norm(syn)]:
                if num != r["num"]:
                    clashes.append(f"«{syn}» — {kind} записи {num}")
        if clashes:
            _flag(r, "synonym_clash", "; ".join(clashes))


def build_rows(parsed, cfg, schema):
    empty = schema["empty"]
    std = cfg["standard"]
    source_cols = [c["name"] for c in schema["columns"] if c["filled_by"] == "source"]
    if std["source_column"] not in source_cols:
        raise ValueError(f"колонки источника {std['source_column']!r} нет в схеме")

    for rec in parsed:
        rec["entity_type"], rec["status"] = classify(rec, schema)
        rec["area"] = area(rec, cfg, schema)
    mark_synonym_clashes(parsed)

    metrics = [r for r in parsed if r["entity_type"] == "метрика"]
    pairs = find_pairs(metrics, schema["pairs"])
    for m in metrics:
        if m["num"] not in pairs:
            _flag(m, "no_pair", f"для «{m['term_en']}» не найдена метрика с non-/accept-reject")

    complements = find_pairs(metrics, schema.get("complements", []))

    id_max_len = next(c for c in schema["columns"] if c["name"] == "id")["id_rule"]["max_len"]
    used = {}
    for rec in parsed:
        rec["id"] = make_id(rec, used, id_max_len)
        key_name = rec["abbr_en"] or rec["term_en"] or empty
        rec["key"] = schema["key_format"].format(name=key_name, area=rec["area"] or empty)
    mark_key_duplicates(parsed)

    rows = []
    for rec in parsed:
        related = ". ".join(dict.fromkeys(  # без повторов: пара может встретиться в стандарте дважды
            [f"{p['abbr_en'] or p['term_ru']} — парная метрика" for p in pairs.get(rec["num"], [])] +
            [f"{p['abbr_en'] or p['term_ru']} — дополнение" for p in complements.get(rec["num"], [])]))

        row = {c["name"]: empty for c in schema["columns"]}
        row.update({
            "Наименование ru": rec["term_ru"] or empty,
            "id": rec["id"],
            "Аббревиатура en": rec["abbr_en"] or empty,
            "Аббревиатура ru": rec["abbr_ru"] or empty,
            "Наименование en": rec["term_en"] or empty,
            "Область (часть ключа)": rec["area"] or empty,
            "Тип сущности": rec["entity_type"],
            "Синонимы": ", ".join(rec["synonyms"]) or empty,
            std["source_column"]: f"п. {rec['num']} — {rec['definition']}" if rec["definition"] else empty,
            "Связанные термины": related or empty,
            "Статус": rec["status"],
        })
        if row[std["source_column"]] != empty:
            row["Ссылки для проверки"] = f"{std['designation']}: {std['url']}"
        row.update({
            "Ключ": rec["key"],
            "Пункт": rec["num"],
            "Раздел": rec["section"],
            "Страница": str(rec["page"]),
            "Примеры": "\n".join(f"{i}. {t}" for i, t in enumerate(rec["examples"], 1)) or empty,
            "Примечания": "\n".join(f"{i}. {t}" for i, t in enumerate(rec["notes"], 1)) or empty,
            "Исключённые": ", ".join(rec["excluded"]) or empty,
            "Флаги": ", ".join(rec["flags"]) or empty,
        })
        rows.append(row)

    for row in rows:  # «используется в определении»: записи стандарта, названные в его формулировке
        current = [] if row["Связанные термины"] == empty else row["Связанные термины"].split(". ")
        used = definition_links(row, rows, empty, [std["source_column"]], {i.split(" — ")[0] for i in current})
        if used:
            row["Связанные термины"] = ". ".join(current + used)
    return rows


def all_columns(schema):
    return [c["name"] for c in schema["columns"]] + schema["service_columns"]


def write_outputs(rows, schema, out_dir, columns=None):
    cols = columns or all_columns(schema)
    empty = schema["empty"]
    with open(out_dir / "registry.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(cols)
        for row in rows:
            w.writerow([row[c] for c in cols])

    nulled = [{c: (None if row[c] == empty else row[c]) for c in cols} for row in rows]
    (out_dir / "registry.json").write_text(
        json.dumps(nulled, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    db_path = out_dir / "registry.sqlite"
    if db_path.exists():
        db_path.unlink()
    con = sqlite3.connect(db_path)
    try:
        con.execute("CREATE TABLE terms (" + ", ".join(f'"{c}" TEXT' for c in cols) + ")")
        con.executemany(f"INSERT INTO terms VALUES ({', '.join('?' * len(cols))})",
                        [[r[c] for c in cols] for r in nulled])
        con.commit()
    finally:
        con.close()
