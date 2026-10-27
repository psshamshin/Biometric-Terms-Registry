"""Список записей, которым нужны тексты (задача #36). prompts/generate_fields.md работает строго по нему.

Запись попадает в список, если выполнено хотя бы одно:
  - пуста колонка 13 или 14 (метрика и термин);
  - у метрики пуста колонка 16 и нет флага formula_na;
  - стоит флаг llm_stale.
У термина колонка 16 пустой и должна быть — её наличие не причина.

    python -m src.pending [std_id]
    python -m src.curated pending [std_id]     # то же; разрешено в --allowedTools агента
"""
import sys
from pathlib import Path

from src.context import FORMULA, LONG, SHORT, load_rows

ROOT = Path(__file__).resolve().parent.parent


def reasons(row):
    flags = {f.rsplit(": ", 1)[-1] for f in (row.get("Флаги") or "").split(", ") if f}
    out = []
    if not row.get(LONG):
        out.append("пусто 13")
    if not row.get(SHORT):
        out.append("пусто 14")
    if row["Тип сущности"] == "метрика" and not row.get(FORMULA) and "formula_na" not in flags:
        out.append("пусто 16")
    if "llm_stale" in flags:
        out.append("llm_stale")
    return out


def pending(rows, std=None):
    """[(строка, [причины])] в порядке реестра; std — только записи, у которых этот стандарт среди источников."""
    res = []
    for r in rows:
        if std and std not in (r.get("Источники") or "").split(", "):
            continue
        why = reasons(r)
        if why:
            res.append((r, why))
    return res


def main(argv):
    if len(argv) > 1:
        sys.exit("использование: python -m src.pending [std_id]")
    items = pending(load_rows(), argv[0] if argv else None)
    if not items:
        print("Записей для генерации нет.")
        return
    metrics = sum(r["Тип сущности"] == "метрика" for r, _ in items)
    print(f"Записей: {len(items)} (метрик {metrics}, терминов {len(items) - metrics})")
    print("id\tтип\tисточники\tпричины")
    for r, why in items:
        print(f"{r['id']}\t{r['Тип сущности']}\t{r['Источники']}\t{', '.join(why)}")


if __name__ == "__main__":
    main(sys.argv[1:])
