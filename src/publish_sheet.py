"""Публикация общего реестра (data/out/registry.json) в Google Таблицу — только для чтения.

Листы «Реестр», «Метрики», «Сводка» каждый раз очищаются и записываются целиком.
Всё пишется через Sheets API v4 (spreadsheets.get + spreadsheets.batchUpdate), Drive API не нужен:
- на каждый лист — один batchUpdate: создать лист, размер, очистка, значения, оформление, защита;
- каждое значение — stringValue (или numberValue в «Сводке»): строки не разбираются как формулы;
- ссылка на коммит — формат текста (textFormat.link), не формула;
- чужие листы не трогаются; своя защита узнаётся по описанию PROTECTION_DESCRIPTION.

    python -m src.publish_sheet --dry-run    # без сети: листы, размеры, первые 3 строки
    python -m src.publish_sheet              # публикация; нужны GOOGLE_SERVICE_ACCOUNT_JSON и REGISTRY_SHEET_ID
"""
import json
import os
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
REGISTRY_JSON = ROOT / "data/out/registry.json"
MERGE_CONFIG = ROOT / "config/merge.yaml"

SHEET_REGISTRY, SHEET_METRICS, SHEET_SUMMARY = "Реестр", "Метрики", "Сводка"
PROTECTION_DESCRIPTION = "registry-publish: таблица перезаписывается автоматически"
WARNING = ("Таблица перезаписывается автоматически. Правки здесь пропадут. "
           "Тексты и статусы меняются через data/curated/ в репозитории")
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

WIDTH_LONG, WIDTH_MEDIUM, WIDTH_SHORT = 420, 220, 130
LONG_COLUMNS = {"Переработанное длинное определение"}           # + все колонки источников
MEDIUM_COLUMNS = {"Наименование ru", "Наименование en", "Синонимы", "Ссылки для проверки", "Короткое определение",
                  "Связанные термины", "Ключ", "Синонимы (все)", "Флаги", "Источники"}


# ---------------------------------------------------------------- данные листов (без сети)

def table_columns(schema, merge_cfg):
    """Колонки листов «Реестр» и «Метрики»: по схеме, затем служебные колонки общего реестра."""
    return [c["name"] for c in schema["columns"]] + list(merge_cfg["service_columns"])


def _cell(value, empty):
    return empty if value is None else str(value)


def build_sheets(rows, schema, merge_cfg, standards, sha, commit_url, updated_at):
    """Листы как {название: {"header": [...], "rows": [[...]], "widths": [...], "wrap": [...], "links": {}}}.
    rows — строки registry.json; standards — обозначения подключённых стандартов; updated_at — datetime UTC."""
    empty = schema["empty"]
    cols = table_columns(schema, merge_cfg)
    sources = {c["name"] for c in schema["columns"] if c["filled_by"] == "source"}

    def width(c):
        return WIDTH_LONG if c in LONG_COLUMNS | sources else WIDTH_MEDIUM if c in MEDIUM_COLUMNS else WIDTH_SHORT

    def table(selected):
        return {"header": cols, "rows": [[_cell(r.get(c), empty) for c in cols] for r in selected],
                "widths": [width(c) for c in cols], "wrap": [width(c) != WIDTH_SHORT for c in cols], "links": {}}

    metrics = [r for r in rows if r.get("Тип сущности") == "метрика"]
    statuses = Counter(r.get("Статус") for r in rows)
    flags = Counter(f.rsplit(": ", 1)[-1] for r in rows if r.get("Флаги") for f in r["Флаги"].split(", "))

    summary = [["Обновлено (UTC)", updated_at.strftime("%Y-%m-%d %H:%M UTC")],
               ["Коммит", sha[:7] if sha else empty],
               ["Предупреждение", WARNING],
               ["Подключённые стандарты", "\n".join(standards)],
               ["Строк в реестре", len(rows)],
               ["Метрик", len(metrics)]]
    summary += [[f"Статус «{s}»", statuses.get(s, 0)] for s in schema["dictionaries"]["status"]]
    summary += [[f"Флаг {f}", n] for f, n in sorted(flags.items())]
    links = {(1, 1): commit_url} if sha and commit_url else {}  # (строка данных, колонка)

    return {
        SHEET_REGISTRY: table(rows),
        SHEET_METRICS: table(metrics),
        SHEET_SUMMARY: {"header": ["Параметр", "Значение"], "rows": summary, "widths": [260, 700],
                        "wrap": [False, True], "links": links},
    }


# ---------------------------------------------------------------- запросы batchUpdate (без сети)

def _value(v):
    """ExtendedValue: числа — numberValue, всё остальное — stringValue (никогда не формула)."""
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return {"numberValue": v}
    return {"stringValue": str(v)}


def _row(values, bold=False, links=None):
    cells = []
    for c, v in enumerate(values):
        cell = {"userEnteredValue": _value(v)}
        fmt = {}
        if bold:
            fmt["bold"] = True
        if links and c in links:
            fmt["link"] = {"uri": links[c]}
        if fmt:
            cell["userEnteredFormat"] = {"textFormat": fmt}
        cells.append(cell)
    return {"values": cells}


def build_requests(sheet, sheet_id, title, exists, own_protection_ids):
    """Запросы одного batchUpdate для листа: создать (если нет), размер, очистка, значения, оформление, защита."""
    n_rows = len(sheet["rows"]) + 1
    n_cols = len(sheet["header"])
    grid = {"rowCount": max(n_rows, 2), "columnCount": n_cols, "frozenRowCount": 1}  # закрепить можно не все строки
    whole = {"sheetId": sheet_id}
    reqs = []
    if not exists:
        reqs.append({"addSheet": {"properties": {"sheetId": sheet_id, "title": title, "gridProperties": grid}}})
    else:
        reqs.append({"updateSheetProperties": {"properties": {"sheetId": sheet_id, "gridProperties": grid},
                                               "fields": "gridProperties(rowCount,columnCount,frozenRowCount)"}})
    reqs.append({"updateCells": {"range": whole, "fields": "userEnteredValue,userEnteredFormat"}})  # очистка
    links_by_row = {}
    for (r, c), uri in sheet["links"].items():
        links_by_row.setdefault(r, {})[c] = uri
    rows = [_row(sheet["header"], bold=True)] + [_row(v, links=links_by_row.get(i)) for i, v in enumerate(sheet["rows"])]
    reqs.append({"updateCells": {"start": {"sheetId": sheet_id, "rowIndex": 0, "columnIndex": 0},
                                 "rows": rows, "fields": "userEnteredValue,userEnteredFormat"}})
    for c, wrap in enumerate(sheet["wrap"]):
        if wrap and n_rows > 1:
            reqs.append({"repeatCell": {
                "range": {"sheetId": sheet_id, "startRowIndex": 1, "endRowIndex": n_rows,
                          "startColumnIndex": c, "endColumnIndex": c + 1},
                "cell": {"userEnteredFormat": {"wrapStrategy": "WRAP", "verticalAlignment": "TOP"}},
                "fields": "userEnteredFormat(wrapStrategy,verticalAlignment)"}})
    for c, px in enumerate(sheet["widths"]):
        reqs.append({"updateDimensionProperties": {
            "range": {"sheetId": sheet_id, "dimension": "COLUMNS", "startIndex": c, "endIndex": c + 1},
            "properties": {"pixelSize": px}, "fields": "pixelSize"}})
    reqs.append({"setBasicFilter": {"filter": {"range": {"sheetId": sheet_id, "startRowIndex": 0, "endRowIndex": n_rows,
                                                         "startColumnIndex": 0, "endColumnIndex": n_cols}}}})
    reqs += [{"deleteProtectedRange": {"protectedRangeId": pid}} for pid in sorted(own_protection_ids)]
    reqs.append({"addProtectedRange": {"protectedRange": {"range": whole, "description": PROTECTION_DESCRIPTION,
                                                          "warningOnly": True}}})
    return reqs


def plan_requests(sheets, metadata):
    """{название листа: запросы} по метаданным таблицы (ответ spreadsheets.get). Чужие листы не трогаются."""
    existing = {s["properties"]["title"]: s for s in metadata.get("sheets", [])}
    next_id = max([s["properties"]["sheetId"] for s in metadata.get("sheets", [])] + [0]) + 1
    plan = {}
    for title, sheet in sheets.items():
        if title in existing:
            props = existing[title]
            sheet_id = props["properties"]["sheetId"]
            own = {p["protectedRangeId"] for p in props.get("protectedRanges", [])
                   if p.get("description") == PROTECTION_DESCRIPTION}
            plan[title] = build_requests(sheet, sheet_id, title, True, own)
        else:
            plan[title] = build_requests(sheet, next_id, title, False, set())
            next_id += 1
    return plan


# ---------------------------------------------------------------- сеть

def publish(service, spreadsheet_id, sheets):
    """Один spreadsheets.get и по одному spreadsheets.batchUpdate на лист."""
    metadata = service.spreadsheets().get(
        spreadsheetId=spreadsheet_id,
        fields="sheets(properties(sheetId,title),protectedRanges(protectedRangeId,description))").execute()
    for title, requests in plan_requests(sheets, metadata).items():
        service.spreadsheets().batchUpdate(spreadsheetId=spreadsheet_id, body={"requests": requests}).execute()
        print(f"лист «{title}»: записано строк {len(sheets[title]['rows'])}")


def _service(info):
    from google.oauth2 import service_account
    from googleapiclient.discovery import build

    creds = service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
    return build("sheets", "v4", credentials=creds, cache_discovery=False)


# ---------------------------------------------------------------- запуск

def load_sheets(updated_at=None, sha=None, commit_url=None):
    from src.checks import load_schema

    merge_cfg = yaml.safe_load(MERGE_CONFIG.read_text(encoding="utf-8"))
    standards = [yaml.safe_load((ROOT / e["config"]).read_text(encoding="utf-8"))["standard"]["designation"]
                 for e in merge_cfg["standards"]]
    rows = json.loads(REGISTRY_JSON.read_text(encoding="utf-8"))
    return build_sheets(rows, load_schema(), merge_cfg, standards, sha, commit_url,
                        updated_at or datetime.now(timezone.utc))


def _commit():
    sha = os.environ.get("GITHUB_SHA", "")
    server, repo = os.environ.get("GITHUB_SERVER_URL", "https://github.com"), os.environ.get("GITHUB_REPOSITORY", "")
    return sha, (f"{server}/{repo}/commit/{sha}" if sha and repo else None)


def main(argv):
    sha, url = _commit()
    if "--dry-run" in argv:
        for title, sheet in load_sheets(sha=sha, commit_url=url).items():
            print(f"== {title}: строк {len(sheet['rows'])}, колонок {len(sheet['header'])}")
            for row in [sheet["header"]] + sheet["rows"][:3]:
                print("   ", " | ".join(str(v).replace("\n", " ⏎ ")[:40] for v in row))
        return 0

    key, sheet_id = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", ""), os.environ.get("REGISTRY_SHEET_ID", "")
    if not key.strip() or not sheet_id.strip():
        print("публикация пропущена: нет секретов GOOGLE_SERVICE_ACCOUNT_JSON и REGISTRY_SHEET_ID")
        return 0
    try:
        info = json.loads(key)
    except json.JSONDecodeError:
        print("ошибка: секрет GOOGLE_SERVICE_ACCOUNT_JSON — не JSON ключа сервисного аккаунта", file=sys.stderr)
        return 1

    from google.auth.exceptions import GoogleAuthError
    from googleapiclient.errors import HttpError

    try:
        publish(_service(info), sheet_id.strip(), load_sheets(sha=sha, commit_url=url))
    except (GoogleAuthError, ValueError) as e:  # ключ не того формата; текст ключа не печатается
        print(f"ошибка ключа сервисного аккаунта: {type(e).__name__}. Проверьте секрет GOOGLE_SERVICE_ACCOUNT_JSON "
              f"(весь JSON-файл ключа целиком).", file=sys.stderr)
        return 1
    except HttpError as e:
        print(f"ошибка Google Sheets API {e.status_code}: {e.reason}. Проверьте, что Sheets API включён, "
              f"таблице дан доступ «Редактор» для client_email сервисного аккаунта и REGISTRY_SHEET_ID верный.",
              file=sys.stderr)
        return 1
    print("публикация завершена")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
