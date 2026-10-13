"""Слой data/curated/: тексты LLM (колонки 13, 14, 16) и статусы, которые ставит человек.

Парсер в data/curated/ никогда не пишет. Сборка подмешивает файлы только в общий реестр.
Формат файла data/curated/{id}.yaml — ключи из раздела curated схемы:

    id: fnmr
    Переработанное длинное определение: "..."
    Короткое определение: "... Ниже — лучше"
    Формула *: "FNMR = FN / (FN + TP)"
    Статус: утвержден          # необязательно, ставит только человек
    отпечаток: 3f2a9c0d41b7e865 # отпечаток формулировок источников, по которым написаны тексты
    флаги: [formula_na]        # необязательно

Команды для генерации текстов (только печатают, ничего не пишут):
    python -m src.curated fingerprint <id>   # текущий отпечаток строки общего реестра
    python -m src.curated template <id>      # заготовка curated-файла с текущим отпечатком
"""
import hashlib
import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
CURATED_DIR = ROOT / "data/curated"
REGISTRY_JSON = ROOT / "data/out/registry.json"


def fingerprint(row, schema):
    """sha256 колонок источников строки (в порядке схемы), первые 16 знаков."""
    empty = schema["empty"]
    sources = [c["name"] for c in schema["columns"] if c["filled_by"] == "source"]
    payload = "".join(f"{c}\t{empty if row.get(c) is None else row[c]}\n" for c in sources)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def load_files(curated_dir):
    if not curated_dir or not Path(curated_dir).exists():
        return []
    return [(p, yaml.safe_load(p.read_text(encoding="utf-8")) or {}) for p in sorted(Path(curated_dir).glob("*.yaml"))]


def _add_flags(row, flags, empty):
    current = [] if row["Флаги"] == empty else row["Флаги"].split(", ")
    row["Флаги"] = ", ".join(dict.fromkeys(current + flags)) or empty


def apply_curated(rows, schema, curated_dir):
    """Подмешивает curated-файлы в строки общего реестра (по id). Возвращает отчёт:
    files, applied [id], stale [(id, причина)], orphans [(файл, id)], problems [(файл, поле, проблема)],
    status_keys — ключи строк, статус которых пришёл из curated-файла."""
    c = schema["curated"]
    empty = schema["empty"]
    text_cols = [col for col in c["columns"] if col != "Статус"]
    allowed_keys = {"id", c["fingerprint_key"], c["flags_key"], *c["columns"]}
    by_id = {r["id"]: r for r in rows}
    report = {"files": 0, "applied": [], "stale": [], "orphans": [], "problems": [], "status_keys": set()}

    for path, data in load_files(curated_dir):
        report["files"] += 1
        cid = str(data.get("id") or path.stem)
        if cid != path.stem:
            report["problems"].append((path.name, "id", f"id «{cid}» не совпадает с именем файла"))
        for key in sorted(set(data) - allowed_keys):
            report["problems"].append((path.name, key, "неизвестное поле"))
        file_flags = [str(f) for f in (data.get(c["flags_key"]) or [])]
        for f in file_flags:
            if f not in c["flags"]:
                report["problems"].append((path.name, c["flags_key"], f"флаг «{f}» не из списка curated.flags"))
        row = by_id.get(cid)
        if row is None:
            report["orphans"].append((path.name, cid))
            continue

        actual = fingerprint(row, schema)  # по формулировкам источников до подмешивания
        for col in c["columns"]:
            if data.get(col) is not None:
                row[col] = str(data[col])
                if col == "Статус":
                    report["status_keys"].add(row["Ключ"])
        flags = [f for f in file_flags if f in c["flags"]]
        has_texts = any(data.get(col) not in (None, empty) for col in text_cols)
        saved = data.get(c["fingerprint_key"])
        if has_texts and str(saved) != actual:
            flags.append("llm_stale")
            reason = "отпечатка нет" if saved is None else f"отпечаток {saved} ≠ текущий {actual}"
            report["stale"].append((cid, reason))
        _add_flags(row, flags, empty)
        report["applied"].append(cid)
    return report


def _registry_row(rid):
    rows = json.loads(REGISTRY_JSON.read_text(encoding="utf-8"))
    row = next((r for r in rows if r["id"] == rid), None)
    if row is None:
        sys.exit(f"нет строки с id «{rid}» в {REGISTRY_JSON.relative_to(ROOT)}; сначала: python run.py")
    return row


def main(argv):
    from src.checks import load_schema

    if len(argv) != 2 or argv[0] not in ("fingerprint", "template"):
        sys.exit("использование: python -m src.curated fingerprint|template <id>")
    schema = load_schema()
    c = schema["curated"]
    row = _registry_row(argv[1])
    fp = fingerprint(row, schema)
    if argv[0] == "fingerprint":
        print(fp)
        return
    template = {"id": row["id"]}
    for col in c["columns"]:
        if col != "Статус":
            template[col] = row[col] if row[col] is not None else schema["empty"]
    template[c["fingerprint_key"]] = fp
    template[c["flags_key"]] = []
    print(yaml.safe_dump(template, allow_unicode=True, sort_keys=False), end="")


if __name__ == "__main__":
    main(sys.argv[1:])
