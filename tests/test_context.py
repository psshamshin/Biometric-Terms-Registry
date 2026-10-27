"""Состав пакета записи (src/context.py) и список src/pending.py — задача #36."""
import json
from pathlib import Path

import yaml

from src.checks import load_schema
from src.context import FORMULA, LONG, SHORT, load_rows, load_std_rows, package
from src.pending import pending, reasons

ROOT = Path(__file__).resolve().parent.parent
SCHEMA = load_schema()
SRC = next(c["name"] for c in SCHEMA["columns"] if c["filled_by"] == "source")


def rec(rid, name, etype, abbr=None, source="", links=None, long=None, short=None, formula=None, flags=None):
    r = {c["name"]: None for c in SCHEMA["columns"]}
    r.update({s: None for s in SCHEMA["service_columns"]})
    r.update({"id": rid, "Наименование ru": name, "Тип сущности": etype, "Аббревиатура en": abbr,
              "Область (часть ключа)": "биометрия · верификация", SRC: source or None, "Связанные термины": links,
              LONG: long, SHORT: short, FORMULA: formula, "Флаги": flags, "Источники": "std",
              "Ключ": f"{abbr or name} | v", "Статус": "черновик"})
    return r


ROWS = [
    rec("fnmr", "Ложное несовпадение метрика", "метрика", "FNMR", "п. 1 — Доля попыток, приведших к ложному несовпадению.",
        "FMR — парная метрика. Ложное несовпадение — используется в определении. Попытка — связь без типа формулы",
        long="ДЛИННЫЙ-FNMR", short="КОРОТКИЙ-FNMR", formula="FNMR = FN / (FN + TP)"),
    rec("fmr", "Ложное совпадение метрика", "метрика", "FMR", "п. 2 — Доля попыток, приведших к ложному совпадению.",
        "FNMR — парная метрика", long="ДЛИННЫЙ-FMR", short="КОРОТКИЙ-FMR", formula="FMR = FP / (FP + TN)"),
    rec("false-nm", "Ложное несовпадение", "термин", None, "п. 3 — Несовпадение как решение о сравнении.",
        "Другой термин — используется в определении. Ещё термин — прочая связь",
        long="ДЛИННЫЙ-ТЕРМИНА", short="КОРОТКИЙ-ТЕРМИНА"),
    rec("other", "Другой термин", "термин", None, "п. 4 — Другое определение.", long="ДЛИННЫЙ-ДРУГОГО", short="КОРОТКИЙ-ДРУГОГО"),
    rec("more", "Ещё термин", "термин", None, "п. 5 — Ещё определение.", long="ДЛИННЫЙ-ЕЩЁ", short="КОРОТКИЙ-ЕЩЁ"),
]
ROWS[0]["Связанные термины"] = "FMR — парная метрика. Ложное несовпадение — используется в определении"
STD = {"std": {r["Ключ"]: dict(r, Пункт="1", Примечания="ПРИМЕЧАНИЕ-" + r["id"], Примеры="ПРИМЕР-" + r["id"]) for r in ROWS}}


def dump(pkg):
    return yaml.safe_dump(pkg, allow_unicode=True)


def test_metric_package():
    pkg = package("fnmr", ROWS, STD, SCHEMA)
    text = dump(pkg)
    assert pkg["формулировки_источников"] == {SRC: ROWS[0][SRC]}
    assert pkg["примечания_и_примеры"][0]["примечания"] == "ПРИМЕЧАНИЕ-fnmr"
    assert pkg["примечания_и_примеры"][0]["примеры"] == "ПРИМЕР-fnmr"
    assert {(x["запись"], x["связь"]) for x in pkg["связанные"]} == {
        ("FMR", "парная метрика"), ("Ложное несовпадение", "используется в определении")}
    assert pkg["связанные"][0]["формулировки_источников"] == {SRC: ROWS[1][SRC]}
    assert pkg["формулы"]["справочник"]["прямые"] == SCHEMA["formula"]["direct"]
    assert pkg["формулы"]["формулы_связанных_метрик"] == {"FMR": "FMR = FP / (FP + TN)"}
    assert "ПРИМЕЧАНИЕ-fmr" not in text  # примечания связанных записей в пакет не входят


def test_term_package():
    pkg = package("false-nm", ROWS, STD, SCHEMA)
    text = dump(pkg)
    assert "формулы" not in pkg and "FN / (FN + TP)" not in text
    assert [(x["запись"], x["связь"]) for x in pkg["связанные"]] == [("Другой термин", "используется в определении")]
    assert pkg["связанные"][0]["формулировки_источников"] == {SRC: ROWS[3][SRC]}
    assert pkg["примечания_и_примеры"][0]["примечания"] == "ПРИМЕЧАНИЕ-false-nm"
    assert "Ещё определение" not in text  # связь другого типа в пакет термина не входит
    assert "FNMR" not in text and "метрик" not in pkg["тип"]


def test_other_records_texts_never_in_package():
    for rid in ("fnmr", "fmr", "false-nm"):
        text = dump(package(rid, ROWS, STD, SCHEMA))
        for other in ROWS:
            assert "ДЛИННЫЙ-" + other["id"].upper() not in text
        assert "ДЛИННЫЙ-" not in text and "КОРОТКИЙ-" not in text  # и своих текстов тоже нет


def test_real_registry_packages():
    rows, std = load_rows(), load_std_rows()
    texts = [t for r in rows for t in (r[LONG], r[SHORT]) if t]
    for r in rows:
        pkg = package(r["id"], rows, std, SCHEMA)
        text = dump(pkg)
        assert not [t for t in texts if t in text], r["id"]
        if r["Тип сущности"] == "термин":
            assert "формулы" not in pkg
            assert {x["связь"] for x in pkg["связанные"]} <= {"используется в определении"}
        else:
            assert "формулы" in pkg


def test_pending_rules():
    def row(**kw):
        return rec("x", "Х", kw.pop("etype", "метрика"), "ABC", "п. 1 — Х.", **kw)

    full = dict(long="д", short="к", formula="ABC = FP / (FP + TN)")
    assert reasons(row(**full)) == []
    assert reasons(row(**dict(full, long=None))) == ["пусто 13"]
    assert reasons(row(**dict(full, short=None))) == ["пусто 14"]
    assert reasons(row(**dict(full, formula=None))) == ["пусто 16"]
    assert reasons(row(**dict(full, formula=None, flags="formula_na"))) == []
    assert reasons(row(**dict(full, flags="std: llm_stale"))) == ["llm_stale"]
    # у термина формула пуста всегда — это не причина
    assert reasons(row(etype="термин", long="д", short="к")) == []
    assert reasons(row(etype="термин", long="д", short=None)) == ["пусто 14"]


def test_pending_filter_by_standard():
    rows = [rec("a", "А", "термин"), rec("b", "Б", "термин")]
    rows[1]["Источники"] = "other_std"
    assert [r["id"] for r, _ in pending(rows)] == ["a", "b"]
    assert [r["id"] for r, _ in pending(rows, "other_std")] == ["b"]


def test_real_registry_pending_matches_registry():
    rows = json.loads((ROOT / "data/out/registry.json").read_text(encoding="utf-8"))
    ids = {r["id"] for r, _ in pending(rows)}
    expected = {r["id"] for r in rows if r[LONG] is None or r[SHORT] is None}
    assert expected <= ids
