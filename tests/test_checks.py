"""Шаг 9: проверки ловят то, что должны; шаг 10: повторный запуск даёт те же файлы."""
import hashlib
from pathlib import Path

import pytest
import yaml

from run import build_registry
from src import checks
from src.build import mark_synonym_clashes
from src.classify import classify, find_pairs

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "config/gost_2382_37.yaml"
SCHEMA = checks.load_schema()
CFG = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
OUT_FILES = ["registry.csv", "registry.json", "registry.sqlite", "report.md"]


@pytest.fixture(scope="module")
def result(tmp_path_factory):
    return build_registry(CONFIG, tmp_path_factory.mktemp("out"))


def _rec(**kw):
    base = {"num": "37.99.01", "section": "37.99", "term_ru": "Т", "term_en": None, "abbr_en": None,
            "definition": "", "synonyms": [], "flags": [], "flag_reasons": {}}
    base.update(kw)
    return base


# ---------- на реальных данных

def test_registry_columns_match_schema(result):
    cols = [c["name"] for c in SCHEMA["columns"]] + SCHEMA["service_columns"]
    assert all(list(r) == cols for r in result["rows"])


def test_no_schema_violations(result):
    assert result["violations"] == []


def test_dictionaries_only(result):
    assert result["dict_errors"] == []


def test_numbering_and_integrity(result):
    counts, problems = result["numbering"]
    assert problems == [] and sum(counts.values()) == 120
    assert result["integrity"] == []


def test_all_37_09_metrics_complete(result):
    metrics = {r["Пункт"]: r for r in result["rows"] if r["Тип сущности"] == "метрика"}
    assert set(metrics) == {"37.09.04", "37.09.07", "37.09.09", "37.09.11"}
    for r in metrics.values():
        for col in ("Наименование ru", "Наименование en", "Аббревиатура en", "Область (часть ключа)", "id",
                    "ГОСТ ISO/IEC 2382-37-2016", "Ссылки для проверки"):
            assert r[col] != "—", (r["Пункт"], col)
        assert r["Статус"] == "черновик"
    assert metrics["37.09.09"]["Связанные термины"].startswith("FNMR — парная метрика")
    assert metrics["37.09.11"]["Связанные термины"].startswith("FMR — парная метрика")


def test_every_flag_explained(result):
    for p in result["parsed"]:
        for f in p["flags"]:
            assert f in SCHEMA["flags"] and p["flag_reasons"].get(f), (p["num"], f)


# ---------- проверки ловят ошибки

def test_schema_check_catches_bad_values(result):
    row = dict(result["rows"][0])
    row.update({"id": "Bad ID", "Наименование ru": "—", "Ссылки для проверки": "—"})
    violations, _ = checks.check_schema([row], SCHEMA)
    rules = {(v[1], v[2].split(" ")[0]) for v in violations}
    assert ("id", "не") in rules                       # шаблон
    assert ("Наименование ru", "обязательно") in rules
    assert any(v[1] == "Ссылки для проверки" for v in violations)


def test_metric_without_pair_needs_no_pair_flag(result):
    row = dict(next(r for r in result["rows"] if r["Пункт"] == "37.09.04"))
    row["Флаги"] = "—"
    violations, _ = checks.check_schema([row], SCHEMA)
    # «используется в определении» не заменяет пару: нет «парной метрики» — нарушение без флага no_pair
    assert any(v[1] == "Связанные термины" and ("обязательно" in v[2] or "парная метрика" in v[2]) for v in violations)


def test_links_must_exist(result):
    row = dict(next(r for r in result["rows"] if r["Пункт"] == "37.09.09"))
    row["Связанные термины"] = "XYZR — парная метрика"
    assert any(v[2] == "запись есть в реестре" for v in checks.check_table_rules([row], SCHEMA))


def test_dictionary_check():
    row = {"Пункт": "x", "Тип сущности": "понятие", "Статус": "утвержден", "Область (часть ключа)": "биометрия"}
    assert len(checks.check_dictionaries([row], SCHEMA)) == 3   # «понятие» и «утвержден» парсер не ставит


def test_numbering_gap_and_dupe():
    parsed = [{"num": n, "section": "37.01"} for n in ("37.01.01", "37.01.03", "37.01.03")]
    _, problems = checks.check_numbering(parsed)
    text = " ".join(p[1] for p in problems)
    assert "37.01.02" in text and "дубли" in text


def test_integrity_catches_glued_article():
    p = {"num": "37.01.01", "definition": "Имеющий отношение к биометрии. 37.01.02 биометрическая", "raw": ""}
    assert any("чужой номер" in x[1] for x in checks.check_integrity([p], CFG, SCHEMA, set()))
    p = {"num": "37.01.01", "definition": "Обрыв определения на запятой,", "raw": "x\n14"}
    found = {x[1].split(" ")[0] for x in checks.check_integrity([p], CFG, SCHEMA, set())}
    assert {"определение", "строка"} <= found


def test_index_word_order_free():
    parsed = [_rec(num="37.03.07", term_ru="Биометрическая база данных", term_en="biometric database",
                   synonyms_ru=[], synonyms_en=[], abbr_ru=None)]
    lines = {"ru": [(1, "база данных биометрическая 37.03..07")], "en": [(1, "biometric database 37.03.07")]}
    found, unparsed = checks.check_index(parsed, lines, CFG)
    assert found == [] and unparsed == []


def test_miro_ignores_spaces_and_final_dot():
    parsed = [{"num": "37.03.36", "definition": "Численное  значение."}]
    assert checks.check_miro(parsed, [{"пункт": "37.03.36", "текст": "Численное значение"}]) == []
    assert checks.check_miro(parsed, [{"пункт": "37.03.36", "текст": "Числовое значение"}]) != []


# ---------- тип, пары, синонимы

def test_classify_sign_a_by_rate():
    rec = _rec(abbr_en="FTA", term_en="failure-to-acquire rate", definition="Доля чего-то")
    assert classify(rec, SCHEMA) == ("метрика", "черновик")
    rec = _rec(abbr_en=None, term_en="something", definition="Доля чего-то")
    assert classify(rec, SCHEMA) == ("термин", "черновик") and "type_conflict" in rec["flags"]


def test_pairs():
    ms = [_rec(num=n, term_en=t) for n, t in [("1", "false match rate"), ("2", "false non-match rate"),
                                              ("3", "false accept rate"), ("4", "false reject rate"),
                                              ("5", "failure-to-enrol rate"),
                                              ("6", "false-negative identification rate"),
                                              ("7", "false-positive identification rate"),
                                              ("8", "true-positive identification rate")]]
    pairs = find_pairs(ms, SCHEMA["pairs"])
    assert [p["num"] for p in pairs["1"]] == ["2"] and [p["num"] for p in pairs["4"]] == ["3"]
    assert "5" not in pairs
    assert [p["num"] for p in pairs["6"]] == ["7"] and [p["num"] for p in pairs["7"]] == ["6"]
    assert "8" not in pairs                               # TPIR — без пары


def test_pairs_attack_vs_bona_fide():
    ms = [_rec(num=n, term_en=t) for n, t in [
        ("1", "attack presentation classification error rate"), ("2", "bona fide presentation classification error rate"),
        ("3", "attack presentation non-response rate"), ("4", "bona fide presentation non-response rate"),
        ("5", "attack presentation acquisition rate"), ("6", "impostor attack presentation match rate"),
        ("7", "concealer attack presentation non-match rate")]]
    pairs = find_pairs(ms, SCHEMA["pairs"])
    assert [p["num"] for p in pairs["1"]] == ["2"] and [p["num"] for p in pairs["2"]] == ["1"]
    assert [p["num"] for p in pairs["3"]] == ["4"] and [p["num"] for p in pairs["4"]] == ["3"]
    assert not {"5", "6", "7"} & set(pairs)           # метрики без «подлинной» пары пар не получают


def test_synonym_clash():
    recs = [_rec(num="a", term_ru="Порог", term_en="threshold"),
            _rec(num="b", term_ru="Фильтровать", term_en="filter", synonyms=["threshold"])]
    mark_synonym_clashes(recs)
    assert "synonym_clash" in recs[1]["flags"] and "threshold" in recs[1]["synonyms"]
    assert recs[0]["flags"] == []


# ---------- шаг 10: повторный запуск

def test_rerun_is_byte_identical(tmp_path):
    digests = []
    for run_dir in ("a", "b"):
        out = tmp_path / run_dir
        build_registry(CONFIG, out)
        digests.append({f: hashlib.sha256((out / f).read_bytes()).hexdigest() for f in OUT_FILES})
    assert digests[0] == digests[1]


# ---------- перенос дефисом в конце строки

@pytest.mark.parametrize("tail,head,corpus,keep,why", [
    ("(full-", "system", "the full-system test", True, "в тексте с дефисом"),
    ("био-", "метрия", "это биометрия", False, "в тексте слитно"),
    ("(full-", "system", "", True, "hyphen_guess"),        # латиница — дефис сохранить
    ("несакционирован-", "ную", "", False, "hyphen_guess"),  # кириллица — склеить
    ("пользователь-", "нарушитель", "Пользователь-нарушитель и пользовательнарушитель", True, "в тексте с дефисом"),
])
def test_hyphen_decision(tail, head, corpus, keep, why):
    from src.clean import hyphen_decision
    got_keep, got_why = hyphen_decision(tail, head, corpus)
    assert got_keep == keep and got_why.startswith(why)


def test_hyphen_join_logged():
    from src.clean import CleaningLog, join_hyphenated
    log = CleaningLog()
    out = join_hyphenated([(1, "ДОПБС (full-"), (1, "system processing)")], CFG, log, corpus="")
    assert out == [(1, "ДОПБС (full-system processing)")]
    assert "hyphen_guess" in log.rows[0][3]


@pytest.mark.parametrize("lines,flagged", [
    (["37.99.01 термин (test term): Определение с пере-", "носом слова."], True),          # в определении
    (["37.99.01 термин (test term): Определение.", "Пример — Текст с пере-", "носом."], False),  # в примере
])
def test_hyphen_guess_flag_only_in_registry_fields(lines, flagged):
    from src.clean import CleaningLog, join_hyphenated
    from src.parse import parse_article
    log = CleaningLog()
    joined = join_hyphenated([(1, l) for l in lines], CFG, log, corpus="")
    art = {"num": "37.99.01", "section": "37.99", "page": 1, "lines": joined}
    rec = parse_article(art, CFG, log)
    assert ("hyphen_guess" in rec["flags"]) == flagged
    if flagged:
        assert "переносом" in rec["flag_reasons"]["hyphen_guess"]


# ---------- ключи разбора ГОСТ Р 71414.1: квадратные скобки, обозначения с параметрами, «Примечания» с пунктами

CFG_71414 = yaml.safe_load((ROOT / "config/gost_r_71414_1_2024.yaml").read_text(encoding="utf-8"))


def _parse(lines, cfg):
    from src.clean import CleaningLog
    from src.parse import parse_article
    art = {"num": "3.99", "section": "3", "page": 1, "lines": [(1, l) for l in lines]}
    return parse_article(art, cfg, CleaningLog())


def test_square_brackets_and_parameters():
    rec = _parse(["3.99 вероятность ложноотрицательной идентификации; ВЛОИ; ВЛОИ (N, R, T) "
                  "[false-negative identification rate; FNIR; FNIR (N, R, T)]: Доля транзакций."], CFG_71414)
    assert (rec["term_ru"], rec["abbr_ru"], rec["term_en"], rec["abbr_en"]) == (
        "Вероятность ложноотрицательной идентификации", "ВЛОИ", "false-negative identification rate", "FNIR")
    assert rec["synonyms"] == [] and rec["definition"] == "Доля транзакций."
    assert rec["notes"] == ["Обозначение с параметрами: ВЛОИ (N, R, T); FNIR (N, R, T)"]


def test_abbreviation_from_parameter_form():
    rec = _parse(["3.99 селективность; СЕЛ (N, R, T) [selectivity; SEL (N, T)]: Среднее количество."], CFG_71414)
    assert (rec["abbr_ru"], rec["abbr_en"]) == ("СЕЛ", "SEL")


def test_note_list_items():
    rec = _parse(["3.99 термин (term): Определение.", "П р и м е ч а н и я", "1 Первое", "продолжение.", "2 Второе."],
                 CFG_71414)
    assert rec["notes"] == ["Первое продолжение.", "Второе."]


def test_without_new_keys_brackets_stay_text():
    # у 2382-37 ключей groups/parameters нет: квадратная скобка — часть текста, как раньше
    rec = _parse(["3.99 термин [x] (term): Определение."], CFG)
    assert rec["term_ru"] == "Термин [x]"


# ---------- ключи разбора ГОСТ Р 58624.1: «Примеры» с пунктами, служебный хвост строки

CFG_58624_1 = yaml.safe_load((ROOT / "config/gost_r_58624_1_2019.yaml").read_text(encoding="utf-8"))


def test_example_list_items():
    rec = _parse(["3.99 термин (term): Определение.", "Примеры", "1 Первый", "продолжение.", "2 Второй."], CFG_58624_1)
    assert rec["examples"] == ["Первый продолжение.", "Второй."]


def test_service_fragments_keep_article_number():
    from src.clean import CleaningLog, drop_service_lines
    log = CleaningLog()
    out = drop_service_lines([(1, "3.2 _______"), (1, "термин (term): Определение.")], CFG_58624_1, log)
    assert [l for _, l in out] == ["3.2", "термин (term): Определение."]


def test_without_service_fragments_line_stays():
    from src.clean import CleaningLog, drop_service_lines
    out = drop_service_lines([(1, "3.2 _______")], CFG, CleaningLog())
    assert [l for _, l in out] == ["3.2 _______"]
