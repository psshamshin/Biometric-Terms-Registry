"""Шаг 1: схема реестра совпадает со «Структурой реестра», примеры проходят свои ограничения."""
from pathlib import Path

import pytest
import yaml

from src.checks import check_rule, load_schema, validate_value

ROOT = Path(__file__).resolve().parent.parent
SCHEMA = load_schema()

# «Структура реестра» из задания — символ в символ. Колонки источников (между «Синонимы» и «Ссылки для проверки»)
# строятся из config/merge.yaml: по одной на подключённый стандарт, в его порядке (правило 3 prompts/add_gost.md).
MERGE = yaml.safe_load((ROOT / "config/merge.yaml").read_text(encoding="utf-8"))
SOURCE_COLUMNS = [
    yaml.safe_load((ROOT / e["config"]).read_text(encoding="utf-8"))["standard"]["source_column"]
    for e in MERGE["standards"]
]
EXPECTED_COLUMNS = [
    "Наименование ru",
    "id",
    "Аббревиатура en",
    "Аббревиатура ru",
    "Наименование en",
    "Область (часть ключа)",
    "Тип сущности",
    "Синонимы",
    *SOURCE_COLUMNS,
    "Ссылки для проверки",
    "Переработанное длинное определение",
    "Короткое определение",
    "Связанные термины",
    "Формула *",
    "Статус",
    "Есть в NIST",
    "Забираем в MRR",
]

EXPECTED_DICTIONARIES = {
    "entity_type": ["метрика", "термин", "понятие"],
    "status": ["черновик", "утвержден", "устарел", "отложено"],
    "area": [
        "биометрия · верификация",
        "биометрия · защита от атак",
        "биометрия · система целиком",
        "биометрия · общее",
        "биометрия · идентификация",
    ],
    "yes_no": ["Да", "Нет"],
}



def test_columns_names_and_order():
    assert [c["name"] for c in SCHEMA["columns"]] == EXPECTED_COLUMNS
    assert [c["n"] for c in SCHEMA["columns"]] == list(range(1, len(EXPECTED_COLUMNS) + 1))
    assert [c["name"] for c in SCHEMA["columns"] if c["filled_by"] == "source"] == SOURCE_COLUMNS


def test_dictionaries():
    assert SCHEMA["dictionaries"] == EXPECTED_DICTIONARIES
    for name in ("биометрия · верификация",):
        assert "·" in name  # разделитель области — U+00B7


def test_parser_allowed_is_subset():
    for dict_name, values in SCHEMA["parser_allowed"].items():
        assert set(values) <= set(SCHEMA["dictionaries"][dict_name])


def test_service_columns():
    assert SCHEMA["service_columns"] == [
        "Ключ", "Пункт", "Раздел", "Страница", "Примеры",
        "Примечания", "Синонимы (все)", "Исключённые", "Флаги",
    ]


def test_all_rules_known():
    # check_rule падает на неизвестном правиле — значит, каждое правило схемы интерпретируемо
    for col in SCHEMA["columns"]:
        for rule in col["rules"]:
            check_rule(SCHEMA, rule, str(col["example"]))


# Пример каждой колонки (не только заполняемых парсером) проходит своё правило.
@pytest.mark.parametrize("col", SCHEMA["columns"], ids=lambda c: f"{c['n']}-{c['name']}")
def test_example_passes(col):
    # Образец строки — метрика FNMR, поэтому проверяем как метрику
    errors = validate_value(SCHEMA, col, str(col["example"]), entity_type="метрика")
    assert errors == [], f"пример «{col['example']}» не проходит: {errors}"


# Валидатор не пропускает заведомо плохие значения.
@pytest.mark.parametrize("column,value,entity_type", [
    ("Наименование ru", "вероятность ложного несовпадения", "метрика"),   # строчная первая
    ("Наименование ru", "Вероятность (FNMR)", "метрика"),                 # скобки, латиница
    ("id", "FNMR", "метрика"),
    ("Аббревиатура en", "FNMRxx", "метрика"),
    ("Аббревиатура ru", "ВЛНС1", "метрика"),
    ("Наименование en", "biometric гесодпШоп", "термин"),                 # кириллица в латинском поле
    ("Область (часть ключа)", "биометрия - верификация", "метрика"),      # не тот разделитель
    ("Тип сущности", "метрики", "метрика"),
    ("Синонимы", "a, b, c, d, e, f", "термин"),
    ("ГОСТ ISO/IEC 2382-37-2016", "37.09.11 — Доля", "метрика"),
    ("Ссылки для проверки", "ГОСТ ISO/IEC 2382-37-2016 https://x", "метрика"),
    ("Связанные термины", "FMR — похожий термин", "метрика"),            # нет «парной метрики»
    ("Статус", "Черновик", "метрика"),
])
def test_bad_values_rejected(column, value, entity_type):
    col = next(c for c in SCHEMA["columns"] if c["name"] == column)
    assert validate_value(SCHEMA, col, value, entity_type) != []


def test_no_pair_flag_exempts_metric_link():
    col = next(c for c in SCHEMA["columns"] if c["name"] == "Связанные термины")
    assert validate_value(SCHEMA, col, "—", "метрика", flags={"no_pair"}) == []


def test_source_column_accepts_several_points():
    col = next(c for c in SCHEMA["columns"] if c["name"] == "ГОСТ Р 71414.1-2024 (ИСО/МЭК 19795-1)")
    assert validate_value(SCHEMA, col, "п. 3.23, 3.35 — Текст.", "метрика") == []
    assert validate_value(SCHEMA, col, "п. 3.23 — Текст.; п. 3.35 — Другой.", "метрика") == []
    assert validate_value(SCHEMA, col, "п. 3.23,3.35 — Текст.", "метрика") != []
