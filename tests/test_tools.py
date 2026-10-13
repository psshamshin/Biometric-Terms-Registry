"""Инструменты агента: src.baseline (сверка с базовыми копиями) и src.recon (разведка PDF)."""
import csv
import json
import shutil
from pathlib import Path

from src import baseline, recon

ROOT = Path(__file__).resolve().parent.parent
SID = "gost_r_58624_4_2025"


def _copy_with_extra_column(tmp_path, value):
    out = tmp_path / SID
    shutil.copytree(ROOT / "data/out/_baseline" / SID, out)
    rows = list(csv.DictReader(open(out / "registry.csv", encoding="utf-8-sig")))
    with open(out / "registry.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]) + ["Новая колонка"])
        w.writeheader()
        for r in rows:
            w.writerow(dict(r, **{"Новая колонка": value}))
    data = json.loads((out / "registry.json").read_text(encoding="utf-8"))
    (out / "registry.json").write_text(json.dumps([dict(r, **{"Новая колонка": None}) for r in data],
                                                  ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with open(out / "report.md", "a", encoding="utf-8") as f:
        f.write("| Новая колонка | — |\n")
    return out


def test_baseline_compare_ignores_only_given_column(tmp_path, capsys):
    out = _copy_with_extra_column(tmp_path, "—")
    assert baseline.compare_std(SID, out, {"Новая колонка"}) is True
    assert "везде пусто" in capsys.readouterr().out
    assert baseline.compare_std(SID, out, set()) is False             # без игнорирования — расхождение


def test_baseline_compare_catches_other_changes(tmp_path):
    out = _copy_with_extra_column(tmp_path, "—")
    data = json.loads((out / "registry.json").read_text(encoding="utf-8"))
    data[0]["Наименование ru"] = "Подмена"
    (out / "registry.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    assert baseline.compare_std(SID, out, {"Новая колонка"}) is False


def test_recon_pages_and_mixed(capsys):
    assert recon._pages(["3", "6-8"]) == [3, 6, 7, 8]
    recon.cmd_mixed(str(ROOT / "data/raw/85866.pdf"), 7, 7)
    assert "'РА'" in capsys.readouterr().out                          # известная ошибка 58624.4: «ПА (РА)»
