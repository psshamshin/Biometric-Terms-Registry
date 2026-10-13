"""Слой data/curated/: подмешивание в общий реестр, llm_stale, curated_orphan, проверки схемы и статусов."""
import json
from pathlib import Path

import pytest
import yaml

from run import ROOT, run_all
from src import checks
from src.curated import CURATED_DIR, apply_curated, fingerprint
from src.merge import merge_registries

MERGE_CFG = yaml.safe_load((ROOT / "config/merge.yaml").read_text(encoding="utf-8"))
SCHEMA = checks.load_schema()

LONG = ("Показывает, как часто система не узнаёт человека, который на самом деле является собой. "
        "Считается по попыткам парного сравнения: сколько из них алгоритм посчитал несовпадающими. "
        "Пример: сотрудники 1000 раз прикладывались к турникету, 20 раз система их не узнала — FNMR = 2%. "
        "Чем ниже значение, тем меньше пользователь упирается в отказы. Значение зависит от порога: "
        "понизили порог — FNMR упал, но вырос FMR.")


@pytest.fixture(scope="module")
def out_dir(tmp_path_factory):
    out = tmp_path_factory.mktemp("out")
    run_all(out)
    return out


def merge(out_dir, curated_dir):
    return merge_registries(MERGE_CFG, checks.load_schema(), out_dir, curated_dir=curated_dir)


def row_by_id(res, rid):
    return next(r for r in res["rows"] if r["id"] == rid)


def write(curated_dir, rid, **fields):
    curated_dir.mkdir(exist_ok=True)
    (curated_dir / f"{rid}.yaml").write_text(
        yaml.safe_dump({"id": rid, **fields}, allow_unicode=True, sort_keys=False), encoding="utf-8")


def current_fp(out_dir, rid):
    res = merge(out_dir, None)
    return fingerprint(row_by_id(res, rid), SCHEMA)


def test_empty_curated_changes_nothing(out_dir, tmp_path):
    merge(out_dir, None)
    before = {f: (out_dir / f).read_bytes() for f in ("registry.csv", "registry.json")}
    (tmp_path / "curated").mkdir()
    merge(out_dir, tmp_path / "curated")
    assert before == {f: (out_dir / f).read_bytes() for f in ("registry.csv", "registry.json")}


def test_apply_texts_and_status(out_dir, tmp_path):
    cur = tmp_path / "curated"
    write(cur, "fnmr", **{"Переработанное длинное определение": LONG,
                          "Короткое определение": "Как часто система не узнаёт своего. Ниже — лучше",
                          "Формула *": "FNMR = FN / (FN + TP)", "Статус": "утвержден",
                          "отпечаток": current_fp(out_dir, "fnmr"), "флаги": []})
    res = merge(out_dir, cur)
    r = row_by_id(res, "fnmr")
    assert r["Формула *"] == "FNMR = FN / (FN + TP)" and r["Статус"] == "утвержден"
    assert "llm_stale" not in r["Флаги"]
    assert res["violations"] == [] and res["dict_errors"] == [] and res["curated"]["problems"] == []
    assert res["curated"]["applied"] == ["fnmr"]


def test_llm_stale_on_wrong_or_missing_fingerprint(out_dir, tmp_path):
    cur = tmp_path / "curated"
    write(cur, "fnmr", **{"Короткое определение": "Как часто система не узнаёт своего. Ниже — лучше",
                          "отпечаток": "0000000000000000"})
    write(cur, "fmr", **{"Короткое определение": "Как часто система принимает чужого. Ниже — лучше"})
    res = merge(out_dir, cur)
    assert "llm_stale" in row_by_id(res, "fnmr")["Флаги"] and "llm_stale" in row_by_id(res, "fmr")["Флаги"]
    assert sorted(i for i, _ in res["curated"]["stale"]) == ["fmr", "fnmr"]


def test_new_source_wording_makes_llm_stale(out_dir, tmp_path):
    """Отпечаток считается по заполненным колонкам: пустая колонка нового стандарта его не меняет,
    а появившаяся в ней формулировка для существующей метрики — меняет, и сборка ставит llm_stale."""
    empty = SCHEMA["empty"]
    source_cols = [c["name"] for c in SCHEMA["columns"] if c["filled_by"] == "source"]
    row = dict(row_by_id(merge(out_dir, None), "fnmr"))
    col = next(c for c in source_cols if row[c] not in (None, empty))  # колонка стандарта, где формулировка есть
    without = {**row, col: empty}
    assert fingerprint({**without, "__новая пустая колонка": empty}, SCHEMA) == fingerprint(without, SCHEMA)
    assert fingerprint(row, SCHEMA) != fingerprint(without, SCHEMA)

    cur = tmp_path / "curated"
    write(cur, "fnmr", **{"Короткое определение": "Как часто система не узнаёт своего. Ниже — лучше",
                          "отпечаток": fingerprint(without, SCHEMA)})
    stale_rows = [without, {**row_by_id(merge(out_dir, None), "fmr")}]
    assert apply_curated(stale_rows, SCHEMA, cur)["stale"] == []  # формулировки стандарта не менялись
    fresh_rows = [dict(row), {**row_by_id(merge(out_dir, None), "fmr")}]
    report = apply_curated(fresh_rows, SCHEMA, cur)  # новый стандарт добавил формулировку
    assert [i for i, _ in report["stale"]] == ["fnmr"] and "llm_stale" in fresh_rows[0]["Флаги"]


def test_curated_orphan(out_dir, tmp_path):
    cur = tmp_path / "curated"
    write(cur, "no-such-id", **{"Короткое определение": "Нечто. Ниже — лучше"})
    res = merge(out_dir, cur)
    assert res["curated"]["orphans"] == [("no-such-id.yaml", "no-such-id")]


def test_schema_violation_in_curated_value(out_dir, tmp_path):
    cur = tmp_path / "curated"
    write(cur, "fnmr", **{"Короткое определение": "Слишком длинное короткое определение из двенадцати слов для проверки "
                                                  "ограничения схемы Ниже — лучше",
                          "Формула *": "FNMR = FN / (FN + TP) * 100",
                          "отпечаток": current_fp(out_dir, "fnmr")})
    res = merge(out_dir, cur)
    cols = {v[1] for v in res["violations"] if v[0].startswith("FNMR |")}
    assert {"Короткое определение", "Формула *"} <= cols


def test_approved_requires_llm_fields(out_dir, tmp_path):
    cur = tmp_path / "curated"
    write(cur, "fnmr", **{"Статус": "утвержден"})
    res = merge(out_dir, cur)
    cols = {v[1] for v in res["violations"] if v[0].startswith("FNMR |")}
    assert {"Переработанное длинное определение", "Короткое определение", "Формула *"} <= cols


def test_status_only_from_curated(out_dir):
    res = merge(out_dir, None)
    row = dict(row_by_id(res, "fnmr"), Статус="утвержден")
    assert checks.check_dictionaries([row], SCHEMA, id_col="Ключ") != []
    assert checks.check_dictionaries([row], SCHEMA, id_col="Ключ", free_status_keys={row["Ключ"]}) == []


def test_formula_na_exempts_formula(out_dir, tmp_path):
    cur = tmp_path / "curated"
    texts = {"Переработанное длинное определение": LONG,
             "Короткое определение": "Как часто не удаётся получить данные. Ниже — лучше",
             "Статус": "утвержден", "отпечаток": current_fp(out_dir, "fta")}
    write(cur, "fta", **texts, флаги=["formula_na"])
    res = merge(out_dir, cur)
    assert not [v for v in res["violations"] if v[0].startswith("FTA |")]
    assert "formula_na" in row_by_id(res, "fta")["Флаги"]
    write(cur, "fta", **texts)  # без formula_na формула к «утвержден» обязательна
    res = merge(out_dir, cur)
    assert any(v[1] == "Формула *" for v in res["violations"] if v[0].startswith("FTA |"))


def test_bad_keys_and_flags_reported(out_dir, tmp_path):
    cur = tmp_path / "curated"
    write(cur, "fnmr", **{"Наименование ru": "Подмена", "флаги": ["no_pair"]})
    res = merge(out_dir, cur)
    problems = {(f, k) for f, k, _ in res["curated"]["problems"]}
    assert ("fnmr.yaml", "Наименование ru") in problems and ("fnmr.yaml", "флаги") in problems
    assert row_by_id(res, "fnmr")["Наименование ru"] == "Вероятность ложного несовпадения"   # не подменено


def test_fingerprint_from_json_matches_merged_row(out_dir):
    res = merge(out_dir, None)
    rows = json.loads((out_dir / "registry.json").read_text(encoding="utf-8"))
    for rid in ("fnmr", "fpir", "iapar"):
        assert fingerprint(next(r for r in rows if r["id"] == rid), SCHEMA) == fingerprint(row_by_id(res, rid), SCHEMA)


def test_parser_never_writes_to_curated(tmp_path):
    before = sorted(p.name for p in CURATED_DIR.iterdir()) if CURATED_DIR.exists() else []
    run_all(tmp_path / "out")
    after = sorted(p.name for p in CURATED_DIR.iterdir()) if CURATED_DIR.exists() else []
    assert before == after


def test_real_registry_is_clean(out_dir):
    res = merge(out_dir, CURATED_DIR)
    assert res["violations"] == [] and res["dict_errors"] == []
    assert res["curated"]["problems"] == [] and res["curated"]["orphans"] == []


# ---------- формула: цепочка равенств в пределах области

CHAINS = {   # целевые цепочки для всех метрик реестра — так их должен писать prompts/generate_fields.md
    "fnmr": "FNMR = FN / (FN + TP) = FNR = 1 − TPR",
    "fmr": "FMR = FP / (FP + TN) = FPR = 1 − TNR",
    "frr": "FRR = FN / (FN + TP) = FNR = 1 − TPR",
    "far": "FAR = FP / (FP + TN) = FPR = 1 − TNR",
    "fnir": "FNIR = FN / (FN + TP) = FNR = 1 − TPR = 1 − TPIR",
    "tpir": "TPIR = TP / (TP + FN) = TPR = 1 − FNR = 1 − FNIR",
    "fpir": "FPIR = FP / (FP + TN) = FPR = 1 − TNR",
    "iapar": "IAPAR = FP / (FP + TN) = FPR = 1 − TNR",
}


def _formula_violations(out_dir, tmp_path, formulas):
    cur = tmp_path / "curated"
    for rid, formula in formulas.items():
        write(cur, rid, **{"Формула *": formula, "отпечаток": current_fp(out_dir, rid)})
    res = merge(out_dir, cur)
    return [v for v in res["violations"] if v[1] == "Формула *"]


def test_target_chains_pass(out_dir, tmp_path):
    assert _formula_violations(out_dir, tmp_path, CHAINS) == []


@pytest.mark.parametrize("rid,formula,reason", [
    ("fmr", "FMR = FP / (FP + TN) = 1 − FRR", "вне"),          # FRR — другая область (система целиком)
    ("fnmr", "FNMR = FN / (FN + TP) = TPR", "не равны"),       # математически неверно
    ("fnmr", "FNMR = FN / (FN + TP) = XYZ", "вне"),            # неизвестный термин
    ("fnmr", "FMR = FN / (FN + TP)", "начинается"),            # не своя аббревиатура
    ("fnir", "FNIR = FN / (FN + TP) = 1 − TPR = 2 − TPR", None),  # «2» запрещена шаблоном
])
def test_bad_chains_rejected(out_dir, tmp_path, rid, formula, reason):
    v = _formula_violations(out_dir, tmp_path, {rid: formula})
    assert v, formula
    if reason:
        assert any(reason in x[2] for x in v), v
