"""Регрессия: выход каждого подключённого стандарта побайтно совпадает с его базовой копией
data/out/_baseline/<std_id>/.

Правило: после подключения стандарта заводится его базовая копия; регрессия проверяет все стандарты
из config/merge.yaml. Стандарт без базовой копии — ошибка.
registry.sqlite не входит ни в git, ни в базовые копии: его байты зависят от версии SQLite в Python.
Его содержимое проверяет test_sqlite_matches_json (строки совпадают с registry.json).

История базовых копий (2026-10-13):
  - gost_2382_37: обновлена при подключении 58624.4 (новая колонка; путь к журналу очистки в report.md)
    и при подключении 71414.1 (колонка «ГОСТ Р ИСО/МЭК 19795-1-2007» переименована);
  - gost_r_58624_4_2025: заведена до подключения 71414.1, обновлена после переименования колонки;
  - gost_r_71414_1_2024: заведена при подключении;
  - все три: обновлены при переносе в GitHub — колонки источников строятся из merge.yaml (порядок как в merge.yaml),
    колонка «ГОСТ Р 58624.3-2019 (ИСО/МЭК 30107-3)» убрана; registry.sqlite убран из базовых копий.
  - gost_r_58624_1_2019: заведена при подключении; у остальных трёх добавлена колонка
    «ГОСТ Р 58624.1-2019 (ИСО/МЭК 30107-1)» (везде «—»), базовые копии обновлены.
  - gost_r_58624_3_2019: заведена при подключении (2026-10-16); у остальных четырёх добавлена колонка
    «ГОСТ Р 58624.3-2019 (ИСО/МЭК 30107-3)» (везде «—»); ограничения формата полей схемы расширены,
    выход старых стандартов не менялся (сверка с --ignore-column).
  - все пять (2026-10-26, задача #29): связь «используется в определении» в «Связанных терминах» (сверка с
    --ignore-column "Связанные термины": остальное совпало); gost_r_58624_1_2019 — ещё п. 3.5 по Изменению № 1
    (колонка источника и флаг amended, только эта статья).
  - все пять (2026-10-26, задача #34): словоформы и сокращения в «используется в определении», правило pairs
    attack presentation ↔ bona fide presentation (сверка без колонок «Связанные термины», «Формула *», «Флаги»,
    «Короткое определение», «Переработанное длинное определение», «Синонимы»: остальное совпало).
  - все пять (2026-10-27, задача #36): термины получают статус «черновик» вместо «отложено» (сверка без колонки
    «Статус»: остальное совпало; в report.md — строка воронки «Терминов (черновик)» и «Ждёт LLM» теперь считает и термины).
  Каждое обновление — после сверки: кроме изменённой колонки (в ней везде «—») отличий нет.
"""
import json
import sqlite3
from pathlib import Path

import pytest
import yaml

from run import build_registry, std_id

ROOT = Path(__file__).resolve().parent.parent
MERGE = yaml.safe_load((ROOT / "config/merge.yaml").read_text(encoding="utf-8"))
STANDARDS = [std_id(e["config"]) for e in MERGE["standards"]]
NOT_COMPARED = {"registry.sqlite"}  # собирается при прогоне, проверяется по содержимому


@pytest.fixture(scope="module")
def outputs(tmp_path_factory):
    out = {}
    for entry in MERGE["standards"]:
        sid = std_id(entry["config"])
        out[sid] = tmp_path_factory.mktemp(sid)
        build_registry(ROOT / entry["config"], out[sid])
    return out


@pytest.mark.parametrize("sid", STANDARDS)
def test_baseline_exists(sid):
    assert (ROOT / "data/out/_baseline" / sid / "registry.csv").exists(), f"нет базовой копии {sid}"


@pytest.mark.parametrize("sid", STANDARDS)
def test_matches_baseline(outputs, sid):
    baseline = ROOT / "data/out/_baseline" / sid
    produced = sorted(p.name for p in outputs[sid].iterdir() if p.is_file() and p.name not in NOT_COMPARED)
    assert produced == sorted(p.name for p in baseline.iterdir() if p.is_file()), "состав файлов отличается"
    for name in produced:
        assert (outputs[sid] / name).read_bytes() == (baseline / name).read_bytes(), f"{sid}/{name} отличается"


def sqlite_rows(path):
    con = sqlite3.connect(path)
    try:
        cur = con.execute("SELECT * FROM terms")
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, r)) for r in cur.fetchall()]
    finally:
        con.close()


@pytest.mark.parametrize("sid", STANDARDS)
def test_sqlite_matches_json(outputs, sid):
    rows = json.loads((outputs[sid] / "registry.json").read_text(encoding="utf-8"))
    assert sqlite_rows(outputs[sid] / "registry.sqlite") == rows
