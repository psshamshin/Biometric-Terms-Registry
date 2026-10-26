"""Проверка текстов (src/validation.py) и связь «дополнение» (schema.complements)."""
import csv
from pathlib import Path

from src import validation as v
from src.checks import load_schema
from src.classify import find_pairs

ROOT = Path(__file__).resolve().parent.parent
SCHEMA = load_schema()
E = SCHEMA["empty"]


def metric(num, name_en):
    return {"num": num, "term_en": name_en, "abbr_en": num.upper(), "term_ru": num}


def test_complement_fnir_tpir_only():
    ms = [metric("fnir", "false-negative identification rate"), metric("tpir", "true-positive identification rate"),
          metric("fpir", "false-positive identification rate")]
    comp = find_pairs(ms, SCHEMA["complements"])
    assert {k: [o["num"] for o in val] for k, val in comp.items()} == {"fnir": ["tpir"], "tpir": ["fnir"]}
    pairs = find_pairs(ms, SCHEMA["pairs"])
    assert [o["num"] for o in pairs["fnir"]] == ["fpir"] and "tpir" not in pairs  # парные связи не изменились


def row(**kw):
    base = {c["name"]: E for c in SCHEMA["columns"]}
    base.update({"id": "x", "Аббревиатура en": "XYZ", "Наименование ru": "Икс", "Синонимы": E, "Тип сущности": "метрика",
                 "Флаги": E, "Статус": "черновик", "Связанные термины": E})
    base.update(kw)
    return base


LONG = ("Показывает что-то. " * 14) + "Пример: 100 условных попыток, 2 неудачи. Чем ниже значение, тем лучше."


def test_direction_rule():
    assert v.expected_direction(row(**{"Формула *": "TPIR = TP / (TP + FN) = TPR"}), SCHEMA) == v.HIGHER
    assert v.expected_direction(row(**{"Формула *": "FMR = FP / (FP + TN) = FPR"}), SCHEMA) == v.LOWER
    assert v.expected_direction(row(**{"Формула *": E}), SCHEMA) == v.LOWER


def test_metric_direction_and_format_findings():
    r = row(**{v.LONG: LONG.replace("ниже", "выше"), v.SHORT: "Как часто. Ниже — лучше", "Формула *": E,
               "Флаги": "formula_na"})
    res = v.check_row(r, [r], SCHEMA)
    assert any("противоречит" in f for f in res["d"]) and not res["f"] and not res["c"]


def test_formula_text_in_long_is_format_finding():
    r = row(**{v.LONG: LONG + " Формулу через TP, FP, TN, FN записать нельзя.", v.SHORT: "Как часто. Ниже — лучше",
               "Формула *": E, "Флаги": "formula_na"})
    assert v.check_row(r, [r], SCHEMA)["f"]


def test_term_rules():
    ok = row(**{"Тип сущности": "термин", v.LONG: "Условие применения термина. " * 14, v.SHORT: "Краткое определение", "Формула *": E})
    res = v.check_row(ok, [ok], SCHEMA)
    assert not any(res[k] for k in "fcd")
    bad = row(**{"Тип сущности": "термин", v.LONG: LONG + " Чем ниже значение, тем лучше.", v.SHORT: "Как часто. Ниже — лучше", "Формула *": "X = FP / (FP + TN)",
                 "Статус": "отложено"})
    res = v.check_row(bad, [bad], SCHEMA)
    assert res["c"] and res["d"] and res["f"]


def test_mentions_and_related():
    other = row(id="fm", **{"Наименование ru": "Ложное совпадение", "Аббревиатура en": E})
    src = "Доля попыток, приведших к ложному совпадению."
    assert v.mentions(src, [other], "x", E) == ["fm"]
    assert v.mentions("Ничего общего.", [other], "x", E) == []
    assert v.related_labels(row(**{"Связанные термины": "FNIR — дополнение. FPIR — парная метрика"}), E) == {"FNIR", "FPIR"}


def test_real_registry_has_no_findings_except_links():
    """Тексты реестра прошли проверку: замечания возможны только в блоке «д» (связи для упоминаний из источника)."""
    with open(ROOT / "data/out/registry.csv", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    records = v.validate(rows, SCHEMA, v.load_review())
    assert records
    for r in records:
        assert not any(r["findings"][k] for k in "fabcd"), (r["id"], r["findings"])
