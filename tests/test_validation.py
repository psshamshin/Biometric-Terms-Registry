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


LONG = ("Показывает что-то. " * 14) + "Пример: 100 условных попыток, 2 неудачи."


def test_direction_is_forbidden_for_metrics():
    ok = row(**{v.LONG: LONG, v.SHORT: "Как часто что-то случается", "Формула *": E, "Флаги": "formula_na"})
    assert not any(v.check_row(ok, [ok], SCHEMA).values())
    for long, short in ((LONG + " Чем ниже значение, тем лучше.", "Как часто"), (LONG, "Как часто. Ниже — лучше"),
                        (LONG, "Как часто. Выше — лучше")):
        r = row(**{v.LONG: long, v.SHORT: short, "Формула *": E, "Флаги": "formula_na"})
        assert v.check_row(r, [r], SCHEMA)["d"], (long, short)


def test_formula_text_in_long_is_format_finding():
    r = row(**{v.LONG: LONG + " Формулу через TP, FP, TN, FN записать нельзя.", v.SHORT: "Как часто",
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


def test_undecoded_abbreviations():
    f = v.undecoded_abbreviations
    assert f("Считается как FMR и ИАБП.", ()) == ["FMR", "ИАБП"]
    assert f("Парная метрика — вероятность ложного совпадения (FMR). Инструмент атаки (ИАБП) и снова ИАБП.", ()) == []
    assert f("FMR (вероятность ложного совпадения) считается иначе; потом FMR.", ()) == []
    assert f("Сначала FMR, потом FMR (вероятность ложного совпадения).", ()) == ["FMR"]  # расшифровка не при первом упоминании
    assert f("По ГОСТ Р и ISO/IEC 19795-1: XYZ = 2%.", {"XYZ"}) == []  # стандарты и собственная аббревиатура
    assert f("Обычные слова и Заглавные тоже не аббревиатуры.", ()) == []


def test_abbreviations_block():
    long = LONG + " Парная метрика — FMR."
    r = row(**{v.LONG: long, v.SHORT: "Как часто для ИАБП", "Формула *": E, "Флаги": "formula_na"})
    res = v.check_row(r, [r], SCHEMA)["g"]
    assert len(res) == 2 and "FMR" in res[0] and "ИАБП" in res[1]
    r = row(**{v.LONG: LONG + " Парная метрика — вероятность ложного совпадения (FMR). Своя XYZ.", v.SHORT: "Как часто",
               "Формула *": E, "Флаги": "formula_na"})
    assert v.check_row(r, [r], SCHEMA)["g"] == []


def test_mentions_and_related():
    other = row(id="fm", **{"Наименование ru": "Ложное совпадение", "Аббревиатура en": E})
    src = "Доля попыток, приведших к ложному совпадению."
    assert v.mentions(src, [other], "x", E) == ["fm"]
    assert v.mentions("Ничего общего.", [other], "x", E) == []
    assert v.related_labels(row(**{"Связанные термины": "FNIR — дополнение. FPIR — парная метрика"}), E) == {"FNIR", "FPIR"}


def test_mentioned_records_must_be_in_package():
    """Блок «ж»: запись реестра, названная в тексте (наименованием или аббревиатурой), но не входящая в пакет, — замечание."""
    fmr = row(id="fmr", **{"Наименование ru": "Вероятность ложного совпадения", "Аббревиатура en": "FMR"})
    fnmr = row(id="fnmr", **{"Наименование ru": "Вероятность ложного несовпадения", "Аббревиатура en": "FNMR"})
    far = row(id="far", **{"Наименование ru": "Вероятность ложного допуска", "Аббревиатура en": "FAR"})
    base = {v.SHORT: "Как часто", "Формула *": E, "Флаги": "formula_na", "Колонка источника": E}

    def check(long, **kw):
        r = row(id="me", **{v.LONG: LONG + long, **base, **kw})
        return v.check_row(r, [r, fmr, fnmr, far], SCHEMA)["h"]

    assert check(" Не путать с FMR.") and check(" Не путать с вероятностью ложного несовпадения.")  # аббревиатура и наименование
    assert check(" Парная метрика — FAR.", **{"Связанные термины": "FAR — парная метрика"}) == []  # запись в пакете
    assert check(" Просто текст.") == []
    # часть названия записи пакета («ложного допуска» входит в «Вероятность ложного допуска») отдельной записью не считается
    inner = row(id="inner", **{"Наименование ru": "Ложный допуск", "Аббревиатура en": E})
    r = row(id="me", **{v.LONG: LONG + " Парная метрика — вероятность ложный допуск.", **base, "Связанные термины": "FAR — парная метрика"})
    assert v.check_row(r, [r, far, inner], SCHEMA)["h"] == []


def test_definition_links_from_source_text():
    """Запись, названная в формулировке источника, получает «— используется в определении»; уже связанная — нет."""
    from src.links import definition_links

    cols = ["Колонка"]
    fm = row(id="fm", **{"Наименование ru": "Ложное совпадение", "Аббревиатура en": E, "Колонка": E})
    fnmr = row(id="fnmr", **{"Наименование ru": "Вероятность", "Аббревиатура en": "FNMR", "Колонка": E})
    me = row(id="me", **{"Колонка": "п. 1 — Доля попыток, приведших к ложному совпадению."})
    rows = [fm, fnmr, me]
    assert definition_links(me, rows, E, cols, set()) == ["Ложное совпадение — используется в определении"]
    assert definition_links(me, rows, E, cols, {"Ложное совпадение"}) == []
    assert definition_links(fm, rows, E, cols, set()) == []   # себя не связываем


def test_real_registry_has_no_findings_except_links():
    """Тексты реестра прошли проверку: замечания возможны только в блоке «д» (связи для упоминаний из источника)."""
    with open(ROOT / "data/out/registry.csv", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    records = v.validate(rows, SCHEMA, v.load_review())
    assert records
    for r in records:
        assert not any(r["findings"][k] for k in "fabcd"), (r["id"], r["findings"])
