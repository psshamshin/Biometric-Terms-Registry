"""Шаг 5: правила объединения на синтетических реестрах двух стандартов; повторный запуск всего прогона."""
import hashlib
import json
from pathlib import Path

import pytest
import yaml

from run import run_all
from src import checks
from src.build import all_columns
from src.merge import merge_registries

ROOT = Path(__file__).resolve().parent.parent
SCHEMA = checks.load_schema()
MERGE_CFG = yaml.safe_load((ROOT / "config/merge.yaml").read_text(encoding="utf-8"))
CFG = dict(MERGE_CFG, priority=["a", "b"])
SRC = {"a": "ГОСТ ISO/IEC 2382-37-2016", "b": "ГОСТ Р 58624.4-2025 (ИСО/МЭК 30107-4)"}
AREA_V, AREA_A = "биометрия · верификация", "биометрия · защита от атак"


def row(sid, num, ru, en, abbr=None, area=AREA_V, etype="термин", rid=None, synonyms=(), related=None, flags=()):
    r = {c: None for c in all_columns(SCHEMA)}
    r.update({
        "Наименование ru": ru, "Наименование en": en, "Аббревиатура en": abbr,
        "id": rid or (abbr or en.replace(" ", "-")).lower(), "Область (часть ключа)": area,
        "Тип сущности": etype, "Статус": "черновик",
        "Синонимы": ", ".join(synonyms) or None,
        SRC[sid]: f"п. {num} — Определение {sid}.", "Ссылки для проверки": f"{SRC[sid]}: https://{sid}.example",
        "Связанные термины": related, "Ключ": f"{abbr or en} | {area}", "Пункт": num, "Флаги": ", ".join(flags) or None,
    })
    return r


def merge(tmp_path, a_rows, b_rows):
    for sid, rows in (("a", a_rows), ("b", b_rows)):
        (tmp_path / sid).mkdir()
        (tmp_path / sid / "registry.json").write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
    res = merge_registries(CFG, SCHEMA, tmp_path)
    return res, {r["Ключ"]: r for r in res["rows"]}


def flags(r):
    return [] if r["Флаги"] == "—" else r["Флаги"].split(", ")


def test_same_abbr_and_area_one_row(tmp_path):
    res, by_key = merge(tmp_path,
                        [row("a", "1.1", "Вероятность ложного допуска", "false accept rate", "FAR", etype="метрика",
                             flags=["no_pair"])],
                        [row("b", "3.1", "Вероятность ложного допуска", "false accept rate", "FAR", etype="метрика")])
    assert len(res["rows"]) == 1
    r = by_key["FAR | " + AREA_V]
    assert r["Источники"] == "a, b"
    assert r[SRC["a"]] == "п. 1.1 — Определение a." and r[SRC["b"]] == "п. 3.1 — Определение b."
    assert r["Ссылки для проверки"] == f"{SRC['a']}: https://a.example; {SRC['b']}: https://b.example"
    assert r["Флаги"] == "a: no_pair"                      # флаги стандартов — с префиксом std_id
    assert res["violations"] == []                         # no_pair с префиксом снимает требование пары


def test_no_abbr_same_name_and_area_one_row(tmp_path):
    res, _ = merge(tmp_path, [row("a", "1", "Порог", "Threshold-value")], [row("b", "2", "Порог", "threshold value")])
    assert len(res["rows"]) == 1 and res["rows"][0]["Источники"] == "a, b"


def test_same_abbr_other_area_not_merged(tmp_path):
    res, by_key = merge(tmp_path, [row("a", "1", "Доля X", "x rate", "XR", area=AREA_V)],
                        [row("b", "2", "Доля X", "x rate", "XR", area=AREA_A)])
    assert len(res["rows"]) == 2
    assert all("area_conflict" in flags(r) for r in res["rows"])
    assert [c["flag"] for c in res["conflicts"]] == ["area_conflict"]


def test_same_name_other_abbr_merge_candidate(tmp_path):
    res, _ = merge(tmp_path, [row("a", "1", "Доля Y", "y rate", "YR")], [row("b", "2", "Доля Y", "y rate", "YRR")])
    assert len(res["rows"]) == 2
    assert all("merge_candidate" in flags(r) for r in res["rows"])


def test_name_conflict_goes_to_synonyms(tmp_path):
    res, _ = merge(tmp_path, [row("a", "1", "Вероятность ложного допуска", "false accept rate", "FAR")],
                   [row("b", "2", "Частота ложного допуска", "false accept rate", "FAR", synonyms=["ЧЛД"])])
    r = res["rows"][0]
    assert r["Наименование ru"] == "Вероятность ложного допуска"   # первый по priority
    assert r["Синонимы"] == "ЧЛД, частота ложного допуска"   # первая буква — как в тексте ГОСТа, не заглавная
    assert "name_conflict" in flags(r)


def test_name_conflict_synonym_keeps_gost_case(tmp_path):
    """Синоним из наименования другого ГОСТа: строчная первая буква; аббревиатура в начале не трогается."""
    from src.merge import as_in_text

    assert as_in_text("Отказ сбора данных") == "отказ сбора данных"
    assert as_in_text("ДОПО системы") == "ДОПО системы"
    res, _ = merge(tmp_path, [row("a", "1", "Отказ получения данных", "failure to acquire")],
                   [row("b", "2", "Отказ сбора данных", "failure to acquire")])
    assert res["rows"][0]["Синонимы"] == "отказ сбора данных"


def test_real_registry_name_conflict_synonym_lowercase():
    rows = json.loads((Path(__file__).resolve().parent.parent / "data/out/registry.json").read_text(encoding="utf-8"))
    r = next(x for x in rows if x["id"] == "failure-to-acquire")
    assert r["Синонимы"] == "отказ сбора данных"


def test_type_conflict(tmp_path):
    res, _ = merge(tmp_path, [row("a", "1", "Доля Z", "z rate", "ZR", etype="метрика")],
                   [row("b", "2", "Доля Z", "z rate", "ZR", etype="термин")])
    r = res["rows"][0]
    assert (r["Тип сущности"], r["Статус"]) == ("термин", "черновик") and "type_conflict" in flags(r)


def test_id_collision(tmp_path):
    res, _ = merge(tmp_path, [row("a", "1", "Альфа", "alpha", rid="same")], [row("b", "2", "Бета", "beta", rid="same")])
    ids = sorted(r["id"] for r in res["rows"])
    assert ids == ["same", "same-2"]
    assert sum("id_collision" in flags(r) for r in res["rows"]) == 1


def test_all_synonyms_kept(tmp_path):
    res, _ = merge(tmp_path, [row("a", "1", "Ка", "k", synonyms=["s1", "s2", "s3"])],
                   [row("b", "2", "Ка", "k", synonyms=["s4", "s5", "s6"])])
    r = res["rows"][0]
    assert r["Синонимы"] == "s1, s2, s3, s4, s5, s6"            # ограничения на число синонимов нет
    assert "Синонимы (все)" not in r


def test_related_union_and_must_exist(tmp_path):
    res, _ = merge(tmp_path,
                   [row("a", "1", "Доля А", "a match rate", "AMR", etype="метрика", related="ANMR — парная метрика")],
                   [row("b", "2", "Доля А", "a match rate", "AMR", etype="метрика", related="ANMR — парная метрика")])
    r = res["rows"][0]
    assert r["Связанные термины"] == "ANMR — парная метрика"
    assert any(v[2] == "запись есть в реестре" for v in res["violations"])   # пары ANMR в общем реестре нет


def test_rows_sorted_by_key_and_columns(tmp_path):
    res, _ = merge(tmp_path, [row("a", "1", "Бэ", "b term"), row("a", "2", "Аа", "a term")], [])
    assert [r["Ключ"] for r in res["rows"]] == sorted(r["Ключ"] for r in res["rows"])
    assert list(res["rows"][0]) == [c["name"] for c in SCHEMA["columns"]] + MERGE_CFG["service_columns"]


def test_full_run_is_byte_identical(tmp_path):
    digests = []
    for d in ("a", "b"):
        run_all(tmp_path / d)
        digests.append({p.relative_to(tmp_path / d).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                        for p in sorted((tmp_path / d).rglob("*")) if p.is_file()})
    assert digests[0] == digests[1] and len(digests[0]) >= 13


def test_same_standard_duplicate_merged_same_text(tmp_path):
    a1 = row("a", "3.23", "Вероятность Х", "x positive rate", "XPR", etype="метрика", rid="xpr", flags=["key_duplicate"])
    a2 = row("a", "3.35", "Вероятность Х", "x positive rate", "XPR", etype="метрика", rid="xpr-2",
             flags=["key_duplicate", "id_collision"])
    res, _ = merge(tmp_path, [a1, a2], [])
    assert len(res["rows"]) == 1
    r = res["rows"][0]
    assert r[SRC["a"]] == "п. 3.23, 3.35 — Определение a." and r["id"] == "xpr" and r["Источники"] == "a"
    assert all(v[1] != SRC["a"] for v in res["violations"])   # форма «п. 3.23, 3.35 — …» проходит схему
    assert r["Флаги"] == "a: key_duplicate, a: id_collision"    # без повторов


def test_same_standard_duplicate_different_texts(tmp_path):
    a1, a2 = row("a", "1.1", "Вероятность Х", "x rate", "XR"), row("a", "1.2", "Вероятность Х", "x rate", "XR")
    a2[SRC["a"]] = "п. 1.2 — Другой текст."
    res, _ = merge(tmp_path, [a1, a2], [])
    assert res["rows"][0][SRC["a"]] == "п. 1.1 — Определение a.; п. 1.2 — Другой текст."
