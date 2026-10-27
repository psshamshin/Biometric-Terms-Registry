"""Ограничения по типу записи (метрика / термин) из config/registry_schema.yaml — задача #36.

Каждое правило из таблицы задачи: тест падает, если схема перестала его ловить."""
import copy
import json
from pathlib import Path

from src import checks
from src.checks import check_dictionaries, check_schema, length_bounds, load_schema

ROOT = Path(__file__).resolve().parent.parent
SCHEMA = load_schema()
E = SCHEMA["empty"]
LONG, SHORT, FORMULA = "Переработанное длинное определение", "Короткое определение", "Формула *"
SRC = next(c["name"] for c in SCHEMA["columns"] if c["filled_by"] == "source")


def row(etype, **kw):
    r = {c["name"]: E for c in SCHEMA["columns"]}
    r.update({s: E for s in SCHEMA["service_columns"]})
    r.update({"Наименование ru": "Запись", "id": "x", "Область (часть ключа)": "биометрия · верификация",
              "Тип сущности": etype, "Статус": "черновик", "Пункт": "1.1", "Ключ": "x | v",
              SRC: "п. 1.1 — Определение.", "Ссылки для проверки": "Стандарт: https://example.org/a.pdf",
              "Связанные термины": "FMR — парная метрика" if etype == "метрика" else E})
    r["Ссылки для проверки"] = SRC + ": https://example.org/a.pdf"
    if etype == "метрика":
        r["Аббревиатура en"] = "FNMR"
    r.update(kw)
    return r


def violations(r):
    return {(v[1], v[2]) for v in check_schema([r], SCHEMA)[0]}


def cols(r):
    return {c for c, _ in violations(r)}


METRIC_LONG = "м" * 300
TERM_LONG = "т" * 100


def test_bounds_by_type():
    assert length_bounds(SCHEMA, LONG, "метрика") == (300, 1000)
    assert length_bounds(SCHEMA, LONG, "термин") == (100, 700)


def test_long_length_metric():
    ok = row("метрика", **{LONG: METRIC_LONG, FORMULA: "FNMR = FN / (FN + TP)"})
    assert LONG not in cols(ok)
    assert LONG in cols(dict(ok, **{LONG: "м" * 299}))
    assert LONG in cols(dict(ok, **{LONG: "м" * 1001}))
    assert LONG in cols(dict(ok, **{LONG: "м" * 700 + "м" * 301}))


def test_long_length_term():
    ok = row("термин", **{LONG: TERM_LONG})
    assert LONG not in cols(ok)
    assert LONG not in cols(dict(ok, **{LONG: "т" * 700}))
    assert LONG in cols(dict(ok, **{LONG: "т" * 99}))
    assert LONG in cols(dict(ok, **{LONG: "т" * 701}))


def test_short_words_both_types():
    for etype in ("метрика", "термин"):
        ok = row(etype, **{SHORT: "один два три четыре пять шесть семь восемь девять десять"})
        assert SHORT not in cols(ok)
        assert SHORT in cols(dict(ok, **{SHORT: ok[SHORT] + " одиннадцать"}))


def test_term_formula_is_violation():
    assert FORMULA not in cols(row("термин"))
    assert FORMULA in cols(row("термин", **{FORMULA: "FNMR = FN / (FN + TP)"}))


def test_metric_needs_formula_or_flag_when_texts_present():
    texts = {LONG: METRIC_LONG, SHORT: "Как часто система ошибается"}
    assert FORMULA in cols(row("метрика", **texts))
    assert FORMULA not in cols(row("метрика", **texts, **{FORMULA: "FNMR = FN / (FN + TP)"}))
    assert FORMULA not in cols(row("метрика", **texts, **{"Флаги": "formula_na"}))


def test_approved_requires_columns():
    m = row("метрика", Статус="утвержден")
    assert {LONG, SHORT, FORMULA} <= cols(m)
    assert FORMULA not in cols(dict(m, **{"Флаги": "formula_na"}))
    t = row("термин", Статус="утвержден")
    assert {LONG, SHORT} <= cols(t) and FORMULA not in cols(t)
    full = dict(t, **{LONG: TERM_LONG, SHORT: "Кратко"})
    assert not cols(full) & {LONG, SHORT, FORMULA}


def test_parser_sets_only_draft():
    assert SCHEMA["parser_allowed"]["status"] == ["черновик"]
    assert "отложено" in SCHEMA["dictionaries"]["status"]
    bad = row("термин", Статус="отложено")
    assert check_dictionaries([bad], SCHEMA)
    assert not check_dictionaries([row("термин")], SCHEMA)
    for decision in SCHEMA["classification"]["decision"].values():
        assert decision["status"] == "черновик"


def test_real_registry_parser_statuses():
    rows = json.loads((ROOT / "data/out/registry.json").read_text(encoding="utf-8"))
    assert {r["Статус"] for r in rows} <= {"черновик", "утвержден", "устарел"}
    assert not [r["id"] for r in rows if r["Тип сущности"] == "термин" and r[FORMULA] is not None]
