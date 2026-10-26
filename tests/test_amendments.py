"""Ключ конфига amendments: правка статьи по «Изменению № …» стандарта, флаг amended."""
import json
from pathlib import Path

import pytest

from src.clean import CleaningLog, apply_amendments

ROOT = Path(__file__).resolve().parent.parent
FIX = {"пункт": "3.5", "изменение": "Изменение № 1", "было": "attack): Биометрическое предъявление",
       "стало": "attack): Предъявление инструмента атаки на биометрическое предъявление", "основание": "скан стр. 17"}


def article():
    return {"num": "3.5", "lines": [
        (6, "3.5 атака на биометрическое предъявление (presentation attack): Биометрическое предъявление"),
        (6, "подсистеме сбора биометрических данных с целью вмешательства в работу биометрической системы.")]}


def test_amendment_replaces_text_and_marks_article():
    art, log = article(), CleaningLog()
    apply_amendments([art], {"amendments": [FIX]}, log)
    assert art["lines"][0][1].endswith("attack): Предъявление инструмента атаки на биометрическое предъявление")
    assert art["amendments"] == [FIX]
    assert any("изменение к стандарту" in r[3] for r in log.rows)


def test_amendment_must_match_exactly_once():
    with pytest.raises(ValueError):
        apply_amendments([article()], {"amendments": [{**FIX, "было": "нет такого текста"}]}, CleaningLog())


def test_no_amendments_changes_nothing():
    art = article()
    apply_amendments([art], {}, CleaningLog())
    assert art == article()


def test_58624_1_item_3_5_amended_by_change_1():
    """Реальный выход: п. 3.5 в редакции Изменения № 1 (скан PDF стр. 17), примечания прежние, п. 3.3 из 58624.3 не затронут."""
    rows = json.loads((ROOT / "data/out/gost_r_58624_1_2019/registry.json").read_text(encoding="utf-8"))
    r = next(x for x in rows if x["Пункт"] == "3.5")
    assert r["ГОСТ Р 58624.1-2019 (ИСО/МЭК 30107-1)"].startswith(
        "п. 3.5 — Предъявление инструмента атаки на биометрическое предъявление подсистеме сбора")
    assert r["Флаги"] == "amended"
    assert r["Примечания"].startswith("1. Атака на биометрическое предъявление может быть реализована")
    assert all(x["Флаги"] is None for x in rows if x["Пункт"] != "3.5")
