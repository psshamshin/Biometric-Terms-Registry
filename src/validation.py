"""Проверка текстов колонок 13, 14, 16 (prompts/validate_fields.md) → data/out/validation_report.md.

Автоматически: формат (f), формулы (c), отсутствие направления «лучше» (d), записи реестра из источника без связи (e).
Вручную (по prompts/validate_fields.md): утверждения без опоры (a), противоречия между определениями (b),
подстановка чисел в пример (c). Результат ручной проверки — data/review/validation_review.yaml;
запись привязана к хэшу текстов и источников: изменились тексты — проверку нужно повторить («ревью устарело»).
Запускается из run.py после объединения; сама ничего, кроме отчёта, не пишет.
"""
import hashlib
import re
from pathlib import Path

import yaml

from src.checks import length_bounds
from src.links import mentions

ROOT = Path(__file__).resolve().parent.parent
REVIEW_PATH = ROOT / "data/review/validation_review.yaml"
LONG, SHORT, FORMULA = "Переработанное длинное определение", "Короткое определение", "Формула *"
LOWER, HIGHER = "Ниже — лучше", "Выше — лучше"
BLOCKS = [
    ("f", "Формат: объём, слова, формулы и условный пример"),
    ("a", "а) Утверждения опираются на источники"),
    ("b", "б) Короткое определение не противоречит длинному и источникам"),
    ("c", "в) Формула сходится с определением"),
    ("d", "г) Нет направления «Ниже/Выше — лучше»"),
    ("e", "д) Записи из источника есть в «Связанных терминах»"),
]


def load_review(path=REVIEW_PATH):
    if not Path(path).exists():
        return {"history": [], "records": {}}
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    return {"history": data.get("history") or [], "records": data.get("records") or {}}


def source_text(row, schema):
    empty = schema["empty"]
    cols = [c["name"] for c in schema["columns"] if c["filled_by"] == "source"]
    return "\n".join(row[c] for c in cols if row.get(c) not in (None, empty))


def review_hash(row, schema):
    payload = "\n".join([row[LONG], row[SHORT], row[FORMULA], source_text(row, schema)])
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]


def related_labels(row, empty):
    if row["Связанные термины"] == empty:
        return set()
    return {item.split(" — ")[0] for item in row["Связанные термины"].split(". ")}


def check_row(row, rows, schema, aliases=None):
    """Автоматические проверки одной записи с текстами → {блок: [замечание]}."""
    empty = schema["empty"]
    is_metric = row["Тип сущности"] == "метрика"
    flags = {f.rsplit(": ", 1)[-1] for f in row["Флаги"].split(", ")} if row["Флаги"] != empty else set()
    res = {k: [] for k, _ in BLOCKS}
    long, short, formula = row[LONG], row[SHORT], row[FORMULA]

    lo, hi = length_bounds(schema, LONG, row["Тип сущности"])
    if not lo <= len(long) <= hi:
        res["f"].append(f"длинное: {len(long)} символов, нужно {lo}–{hi}")
    words = [w for w in short.split() if w != empty]
    if len(words) > 10:
        res["f"].append(f"короткое: {len(words)} слов, нужно ≤ 10")
    if re.search(r"\b(TP|FP|TN|FN)\b", long):
        res["f"].append("длинное: счётчики формулы TP/FP/TN/FN в тексте (формул и пояснений к ним в тексте нет)")
    if is_metric and "условн" not in long.lower():
        res["f"].append("длинное: пример не помечен словом «условный»")

    if LOWER in short or HIGHER in short or LOWER in long or HIGHER in long:
        res["d"].append("в тексте есть «Ниже/Выше — лучше»: направление не указывается")
    if re.search(r"[Чч]ем (ниже|выше)", long):
        res["d"].append("в длинном определении есть «как читать значение» («Чем ниже / выше значение…»)")

    if not is_metric:
        if formula != empty or "formula_na" in flags:
            res["c"].append("у термина формула должна быть «—» без флага formula_na")
        if row["Статус"] != "черновик":
            res["f"].append(f"статус термина с текстами «{row['Статус']}», нужен «черновик»")
    else:
        abbr = row["Аббревиатура en"]
        if formula == empty:
            if "formula_na" not in flags:
                res["c"].append("формулы нет, флага formula_na нет")
        else:
            parts = [p.strip() for p in formula.split("=")]
            expect = next((e for e, abbrs in schema["formula"]["direct"].items() if abbr in abbrs), None)
            if parts[0] != abbr:
                res["c"].append(f"формула начинается с «{parts[0]}», а не с «{abbr}»")
            if expect and parts[1] != expect:
                res["c"].append(f"прямая формула «{parts[1]}», по справочнику «{expect}»")
            if "formula_na" in flags:
                res["c"].append("есть и формула, и флаг formula_na")

    src = source_text(row, schema)
    labels = related_labels(row, empty)
    missing = []
    for rid in mentions(src, rows, row["id"], empty, aliases):
        other = next(r for r in rows if r["id"] == rid)
        if not ({other["Аббревиатура en"], other["Наименование ru"]} & labels):
            missing.append(other["Аббревиатура en"] if other["Аббревиатура en"] != empty else other["Наименование ru"])
    if missing:
        res["e"].append("в источнике упомянуты, но не связаны: " + "; ".join(missing))
    return res


def validate(rows, schema, review, aliases=None):
    empty = schema["empty"]
    records = []
    for row in rows:
        if row[LONG] == empty and row[SHORT] == empty and row[FORMULA] == empty:
            continue
        auto = check_row(row, rows, schema, aliases)
        entry = review["records"].get(row["id"])
        h = review_hash(row, schema)
        manual = {"a": [], "b": [], "c": []}
        state = "проверено"
        if entry is None:
            state = f"ревью нет (хэш {h})"
        elif entry.get("hash") != h:
            state = f"ревью устарело (хэш {h})"
        else:
            for k in manual:
                manual[k] = list(entry.get(k) or [])
        if state != "проверено":
            for k in manual:
                manual[k] = [state]
        findings = {k: auto[k] + manual.get(k, []) for k in auto}
        records.append({"id": row["id"], "abbr": row["Аббревиатура en"] if row["Аббревиатура en"] != empty else row["id"],
                        "type": row["Тип сущности"], "findings": findings, "state": state, "hash": h})
    return records


def _table(head, rows):
    esc = lambda x: str(x).replace("|", "\\|").replace("\n", " ")
    out = ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
    out += ["| " + " | ".join(esc(c) for c in r) + " |" for r in rows]
    return "\n".join(out) + "\n"


def percent(records, key):
    if not records:
        return "—"
    ok = sum(1 for r in records if not r["findings"][key])
    return f"{100 * ok // len(records)}% ({ok} из {len(records)})"


def write_report(path, rows, schema, review, aliases=None):
    empty = schema["empty"]
    records = validate(rows, schema, review, aliases)
    metrics = [r for r in records if r["type"] == "метрика"]
    terms = [r for r in records if r["type"] != "метрика"]
    all_metrics = [r for r in rows if r["Тип сущности"] == "метрика"]
    all_terms = [r for r in rows if r["Тип сущности"] != "метрика"]
    s = ["# Проверка текстов (колонки 13, 14, 16)\n",
         "Правила — `prompts/validate_fields.md`. Автоматические блоки считает `src/validation.py` при `python run.py`; "
         "блоки а, б и подстановку чисел в пример проверяет человек или агент и записывает в "
         "`data/review/validation_review.yaml`.\n"]

    s.append("\n## Охват\n")
    s.append(_table(["Тип", "Записей", "С текстами", "Без текстов"], [
        ("метрика", len(all_metrics), len(metrics), len(all_metrics) - len(metrics)),
        ("термин", len(all_terms), len(terms), len(all_terms) - len(terms))]))

    s.append("\n## Итог по блокам (доля записей без замечаний)\n")
    s.append(_table(["Блок", "Метрики", "Термины"], [
        (title, percent(metrics, k), percent(terms, k)) for k, title in BLOCKS]))
    total = [r for r in records if any(r["findings"].values())]
    s.append(f"\nЗаписей с замечаниями: {len(total)} из {len(records)}; замечаний всего: "
             f"{sum(len(v) for r in records for v in r['findings'].values())}.\n")

    s.append("\n## Список правок\n")
    fixes = [(r["abbr"], k, f) for r in records for k, _ in BLOCKS for f in r["findings"][k]]
    s.append(_table(["Запись", "Блок", "Замечание"], fixes) if fixes else "Замечаний нет.\n")

    s.append("\n## По записям\n")
    s.append(_table(["Запись", "Тип", "Ревью"] + [k for k, _ in BLOCKS],
                    [[r["abbr"], r["type"], r["state"]] + ["+" if not r["findings"][k] else "−" for k, _ in BLOCKS]
                     for r in records]))

    if review["history"]:
        s.append("\n## История проверки\n")
        s.append("\n".join(f"- {h}" for h in review["history"]) + "\n")
    Path(path).write_text("\n".join(s), encoding="utf-8")
    return records
