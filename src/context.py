"""Замкнутый контекст генерации текстов: пакет одной записи (задача #36).

Генерация (prompts/generate_fields.md) и проверка (prompts/validate_fields.md) используют только этот пакет.
Сгенерированные тексты других записей (колонки 13, 14, 16) в пакет не входят никогда.

Пакет метрики:
  - формулировки всех источников записи;
  - расшифровки аббревиатур: наименования записей реестра, чьи аббревиатуры (ru или en) стоят в этих формулировках;
  - «Примечания» и «Примеры» этой статьи ГОСТа (по каждому стандарту записи);
  - формулировки ГОСТа записей из «Связанных терминов»;
  - для формулы: справочник формул из схемы (formula) и формулы связанных метрик (парная метрика, дополнение).
Пакет термина:
  - формулировки всех источников записи;
  - «Примечания» и «Примеры» этой статьи ГОСТа;
  - формулировки ГОСТа записей «используется в определении».
  Формул и метрик (кроме названных в определении) в пакете термина нет.

Команда (только печатает, ничего не пишет):
    python -m src.context <id>
    python -m src.curated context <id>     # то же; разрешено в --allowedTools агента
"""
import json
import sys
from pathlib import Path

import yaml

from src.links import abbreviation_aliases, abbreviation_hits

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "data/out"

LONG, SHORT, FORMULA = "Переработанное длинное определение", "Короткое определение", "Формула *"
USED = "используется в определении"
FORMULA_LINKS = ("парная метрика", "дополнение")


def load_rows(out_dir=OUT_DIR):
    return json.loads((Path(out_dir) / "registry.json").read_text(encoding="utf-8"))


def load_std_rows(out_dir=OUT_DIR):
    """{std_id: {Ключ: строка стандарта}} для стандартов, чьи выходы есть в out_dir."""
    res = {}
    for p in sorted(Path(out_dir).glob("*/registry.json")):
        if p.parent.name.startswith("_"):
            continue
        res[p.parent.name] = {r["Ключ"]: r for r in json.loads(p.read_text(encoding="utf-8"))}
    return res


def source_columns(schema):
    return [c["name"] for c in schema["columns"] if c["filled_by"] == "source"]


def sources_of(row, schema):
    return {c: row[c] for c in source_columns(schema) if row.get(c)}


def label_of(row):
    return row.get("Аббревиатура en") or row["Наименование ru"]


def links_of(row, rows, sep=". "):
    """[(запись реестра, тип связи)] из «Связанных терминов» (запись находится по Аббревиатуре en или Наименованию ru)."""
    if not row.get("Связанные термины"):
        return []
    out = []
    for item in row["Связанные термины"].split(sep):
        name, kind = item.rsplit(" — ", 1)
        target = next((r for r in rows if name in (r.get("Аббревиатура en"), r["Наименование ru"])), None)
        if target is not None:
            out.append((target, kind))
    return out


def load_aliases(rows):
    """Сокращения из разделов «Сокращения» стандартов → {id записи: [сокращения]} (как при сборке объединения)."""
    from src.merge import load_abbreviations

    cfg = yaml.safe_load((ROOT / "config/merge.yaml").read_text(encoding="utf-8"))
    return abbreviation_aliases(rows, load_abbreviations(cfg, OUT_DIR), None)


def decoded_abbreviations(row, rows, schema, aliases=None):
    """Расшифровки: записи реестра, чьё сокращение (ru или en) стоит в формулировках источников этой записи."""
    text = "\n".join(sources_of(row, schema).values())
    return [{"аббревиатура": abbr, "наименование": r["Наименование ru"], "наименование_en": r.get("Наименование en")}
            for r, abbr in abbreviation_hits(text, rows, row["id"], None, aliases)]


def package(rid, rows, std_rows, schema, aliases=None):
    """Пакет записи rid: словарь, который печатается как YAML. Только данные источников и справочник формул."""
    row = next((r for r in rows if r["id"] == rid), None)
    if row is None:
        raise KeyError(rid)
    is_metric = row["Тип сущности"] == "метрика"
    flags = [f.rsplit(": ", 1)[-1] for f in (row.get("Флаги") or "").split(", ") if f]

    pkg = {
        "id": row["id"],
        "тип": row["Тип сущности"],
        "наименование": row["Наименование ru"],
        "аббревиатура": row.get("Аббревиатура en"),
        "область": row["Область (часть ключа)"],
        "флаги": sorted(set(flags)),
        "формулировки_источников": sources_of(row, schema),
        "расшифровки_аббревиатур": decoded_abbreviations(row, rows, schema, aliases),
        "примечания_и_примеры": [],
        "связанные": [],
    }
    for sid in (row.get("Источники") or "").split(", "):
        std = std_rows.get(sid, {}).get(row["Ключ"])
        if std and (std.get("Примечания") or std.get("Примеры")):
            pkg["примечания_и_примеры"].append(
                {"стандарт": sid, "пункт": std["Пункт"], "примечания": std.get("Примечания"), "примеры": std.get("Примеры")})

    links = links_of(row, rows)
    wanted = [(r, k) for r, k in links if is_metric or k == USED]
    for target, kind in wanted:
        pkg["связанные"].append({"запись": label_of(target), "наименование": target["Наименование ru"], "связь": kind,
                                 "формулировки_источников": sources_of(target, schema)})

    if is_metric:
        f = schema["formula"]
        peers = {label_of(r): r.get(FORMULA) for r, k in links if k in FORMULA_LINKS and r["Тип сущности"] == "метрика"}
        pkg["формулы"] = {
            "справочник": {"счётчики": f["counts"], "доли_матрицы_ошибок": f["aliases"], "прямые": f["direct"],
                           "check_values": f["check_values"]},
            "формулы_связанных_метрик": peers,
        }
    return pkg


def main(argv):
    from src.checks import load_schema

    if len(argv) != 1:
        sys.exit("использование: python -m src.context <id>")
    rows = load_rows()
    try:
        pkg = package(argv[0], rows, load_std_rows(), load_schema(), load_aliases(rows))
    except KeyError:
        sys.exit(f"нет строки с id «{argv[0]}» в data/out/registry.json; сначала: python run.py")
    print(yaml.safe_dump(pkg, allow_unicode=True, sort_keys=False, width=1000), end="")


if __name__ == "__main__":
    main(sys.argv[1:])
