"""Публикация в Google Таблицу — без сети: данные листов, запросы batchUpdate, пропуск без секретов."""
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
import yaml

from src import publish_sheet as ps
from src.checks import load_schema

ROOT = Path(__file__).resolve().parent.parent
SCHEMA = load_schema()
MERGE_CFG = yaml.safe_load((ROOT / "config/merge.yaml").read_text(encoding="utf-8"))
COLS = ps.table_columns(SCHEMA, MERGE_CFG)
T = datetime(2026, 10, 13, 12, 0, tzinfo=timezone.utc)


def row(**kw):
    r = {c: None for c in COLS}
    r.update({"Наименование ru": "Термин", "id": "t", "Тип сущности": "термин", "Статус": "отложено"})
    r.update(kw)
    return r


def sheets(rows, sha="abcdef1234567", url="https://github.com/o/r/commit/abcdef1234567"):
    return ps.build_sheets(rows, SCHEMA, MERGE_CFG, ["ГОСТ A", "ГОСТ B"], sha, url, T)


def all_values(requests):
    for req in requests:
        for r in req.get("updateCells", {}).get("rows", []):
            for cell in r["values"]:
                yield cell["userEnteredValue"]


def test_columns_follow_schema_and_service_columns():
    expected = [c["name"] for c in SCHEMA["columns"]] + MERGE_CFG["service_columns"]
    assert COLS == expected and "Синонимы" in COLS
    real = json.loads((ROOT / "data/out/registry.json").read_text(encoding="utf-8"))
    assert list(real[0]) == COLS                      # совпадает с колонками общего реестра
    s = sheets(real)
    assert s[ps.SHEET_REGISTRY]["header"] == COLS == s[ps.SHEET_METRICS]["header"]
    assert len(s[ps.SHEET_REGISTRY]["rows"]) == len(real)


def test_metrics_sheet_has_only_metrics():
    rows = [row(id="a", **{"Тип сущности": "метрика"}), row(id="b"), row(id="c", **{"Тип сущности": "метрика"})]
    metrics = sheets(rows)[ps.SHEET_METRICS]["rows"]
    t = COLS.index("Тип сущности")
    assert [r[COLS.index("id")] for r in metrics] == ["a", "c"] and all(r[t] == "метрика" for r in metrics)


@pytest.mark.parametrize("value", ["=SUM(A1:A2)", "+7 999", "-1", "=IMPORTXML(\"x\")", "—"])
def test_formula_like_values_stay_text(value):
    s = sheets([row(**{"Синонимы": value})])
    reqs = ps.build_requests(s[ps.SHEET_REGISTRY], 5, ps.SHEET_REGISTRY, True, set())
    values = list(all_values(reqs))
    assert {"stringValue": value} in values
    assert all("formulaValue" not in v for v in values)


def test_none_becomes_dash():
    s = sheets([row()])
    assert s[ps.SHEET_REGISTRY]["rows"][0][COLS.index("Синонимы")] == "—"


def test_empty_registry():
    s = sheets([])
    assert s[ps.SHEET_REGISTRY]["rows"] == [] and s[ps.SHEET_METRICS]["rows"] == []
    reqs = ps.build_requests(s[ps.SHEET_REGISTRY], 1, ps.SHEET_REGISTRY, False, set())
    grid = reqs[0]["addSheet"]["properties"]["gridProperties"]
    assert grid["rowCount"] >= 2 and grid["frozenRowCount"] == 1   # закрепить можно не все строки


def test_one_row_and_multiline():
    text = "строка 1\nстрока 2\n=не формула"
    s = sheets([row(**{"Переработанное длинное определение": text})])
    reqs = ps.build_requests(s[ps.SHEET_REGISTRY], 1, ps.SHEET_REGISTRY, True, set())
    assert {"stringValue": text} in list(all_values(reqs))
    grid = reqs[0]["updateSheetProperties"]["properties"]["gridProperties"]
    assert (grid["rowCount"], grid["columnCount"]) == (2, len(COLS))


def test_request_structure_one_batch_per_sheet():
    s = sheets([row()])
    metadata = {"sheets": [
        {"properties": {"sheetId": 0, "title": "Чужой лист"}},
        {"properties": {"sheetId": 7, "title": ps.SHEET_REGISTRY},
         "protectedRanges": [{"protectedRangeId": 11, "description": ps.PROTECTION_DESCRIPTION},
                             {"protectedRangeId": 12, "description": "чужая защита"}]}]}
    plan = ps.plan_requests(s, metadata)
    assert list(plan) == [ps.SHEET_REGISTRY, ps.SHEET_METRICS, ps.SHEET_SUMMARY]
    reg = plan[ps.SHEET_REGISTRY]
    kinds = [next(iter(r)) for r in reg]
    assert kinds[0] == "updateSheetProperties" and "addSheet" not in kinds
    assert {"deleteProtectedRange": {"protectedRangeId": 11}} in reg            # своя защита пересоздаётся
    assert {"deleteProtectedRange": {"protectedRangeId": 12}} not in reg        # чужая не трогается
    prot = [r["addProtectedRange"]["protectedRange"] for r in reg if "addProtectedRange" in r]
    assert prot == [{"range": {"sheetId": 7}, "description": ps.PROTECTION_DESCRIPTION, "warningOnly": True}]
    assert "setBasicFilter" in kinds and "repeatCell" in kinds and "updateDimensionProperties" in kinds
    header = next(r for r in reg if "updateCells" in r and "rows" in r["updateCells"])["updateCells"]["rows"][0]
    assert header["values"][0]["userEnteredFormat"]["textFormat"]["bold"] is True
    new_ids = {plan[t][0]["addSheet"]["properties"]["sheetId"] for t in (ps.SHEET_METRICS, ps.SHEET_SUMMARY)}
    assert new_ids == {8, 9}                                                     # не пересекаются с существующими
    assert 0 not in set(_sheet_ids(plan))                                         # чужой лист (id 0) не упоминается


def _sheet_ids(obj):
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == "sheetId":
                yield v
            else:
                yield from _sheet_ids(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _sheet_ids(v)


def test_summary_counts_and_commit_link():
    rows = [row(id="a", **{"Тип сущности": "метрика", "Статус": "черновик", "Флаги": "no_pair, std: ocr_fixed"}),
            row(id="b", **{"Флаги": "std: ocr_fixed"})]
    summ = dict((k, v) for k, v in sheets(rows)[ps.SHEET_SUMMARY]["rows"])
    assert summ["Строк в реестре"] == 2 and summ["Метрик"] == 1
    assert summ["Статус «черновик»"] == 1 and summ["Статус «отложено»"] == 1 and summ["Статус «утвержден»"] == 0
    assert summ["Флаг ocr_fixed"] == 2 and summ["Флаг no_pair"] == 1
    assert summ["Коммит"] == "abcdef1" and summ["Предупреждение"] == ps.WARNING
    reqs = ps.build_requests(sheets(rows)[ps.SHEET_SUMMARY], 3, ps.SHEET_SUMMARY, True, set())
    data = next(r for r in reqs if "updateCells" in r and "rows" in r["updateCells"])["updateCells"]["rows"]
    assert data[2]["values"][1]["userEnteredFormat"]["textFormat"]["link"]["uri"].endswith("abcdef1234567")


def test_same_registry_same_requests_except_time():
    real = json.loads((ROOT / "data/out/registry.json").read_text(encoding="utf-8"))
    a = ps.build_sheets(real, SCHEMA, MERGE_CFG, ["x"], "s", "u", T)
    b = ps.build_sheets(real, SCHEMA, MERGE_CFG, ["x"], "s", "u", datetime(2027, 1, 1, tzinfo=timezone.utc))
    assert a[ps.SHEET_REGISTRY] == b[ps.SHEET_REGISTRY] and a[ps.SHEET_METRICS] == b[ps.SHEET_METRICS]
    assert a[ps.SHEET_SUMMARY]["rows"][1:] == b[ps.SHEET_SUMMARY]["rows"][1:]


def test_no_secrets_skips(monkeypatch, capsys):
    monkeypatch.delenv("GOOGLE_SERVICE_ACCOUNT_JSON", raising=False)
    monkeypatch.setenv("REGISTRY_SHEET_ID", "")
    assert ps.main([]) == 0
    assert "публикация пропущена: нет секретов" in capsys.readouterr().out


def test_bad_key_fails_without_printing_it(monkeypatch, capsys):
    monkeypatch.setenv("GOOGLE_SERVICE_ACCOUNT_JSON", '{"type": "service_account", "private_key": "SECRET-VALUE"}')
    monkeypatch.setenv("REGISTRY_SHEET_ID", "abc")
    assert ps.main([]) == 1
    out = capsys.readouterr()
    assert "SECRET-VALUE" not in out.out + out.err and "ошибка ключа" in out.err


def test_publish_with_fake_service(monkeypatch):
    calls = []

    class Call:
        def __init__(self, result): self.result = result
        def execute(self): return self.result

    class Sheets:
        def get(self, **kw):
            calls.append(("get", kw)); return Call({"sheets": [{"properties": {"sheetId": 0, "title": "Лист1"}}]})
        def batchUpdate(self, **kw):
            calls.append(("batchUpdate", kw)); return Call({})

    class Service:
        def spreadsheets(self): return Sheets()

    ps.publish(Service(), "ID", sheets([row()]))
    assert [c[0] for c in calls] == ["get", "batchUpdate", "batchUpdate", "batchUpdate"]   # по одному на лист
    assert all(c[1]["spreadsheetId"] == "ID" for c in calls)


def test_dry_run(capsys):
    assert ps.main(["--dry-run"]) == 0
    out = capsys.readouterr().out
    assert "== Реестр: строк" in out and "== Метрики" in out and "== Сводка" in out
