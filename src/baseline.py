"""Сверка выхода стандартов с базовыми копиями data/out/_baseline/<std_id>/ и их обновление
(правило 2 prompts/add_gost.md: «сверяй всё, кроме изменённого места; проверь само изменение; потом обнови копии»).

    python -m src.baseline compare [--std <std_id>] [--ignore-column "<колонка>" ...]
        Собирает стандарты во временную папку и сравнивает с базовыми копиями:
        - без --ignore-column — побайтно (как tests/test_regression.py);
        - с --ignore-column — CSV и JSON по строкам без этих колонок и без учёта порядка колонок,
          report.md — по набору строк; печатает, пусты ли («—» / null) игнорируемые колонки там, где они есть.
        Код выхода 0 — расхождений нет (кроме игнорируемого), 1 — есть.
    python -m src.baseline update [--std <std_id>]
        Копирует data/out/<std_id>/ (кроме registry.sqlite) в базовую копию. Сначала: python run.py.
"""
import argparse
import collections
import csv
import json
import shutil
import sys
import tempfile
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
BASELINE = ROOT / "data/out/_baseline"
NOT_COMPARED = {"registry.sqlite"}


def standards():
    merge = yaml.safe_load((ROOT / "config/merge.yaml").read_text(encoding="utf-8"))
    return [Path(e["config"]).stem for e in merge["standards"]]


def _csv(path):
    return list(csv.DictReader(open(path, encoding="utf-8-sig")))


def _drop(rows, ignore):
    return [{k: v for k, v in r.items() if k not in ignore} for r in rows]


def compare_std(sid, out, ignore):
    base = BASELINE / sid
    ok = True
    files = sorted({p.name for p in out.iterdir() if p.is_file()} | {p.name for p in base.iterdir() if p.is_file()})
    for name in (f for f in files if f not in NOT_COMPARED):
        new, old = out / name, base / name
        if not new.exists() or not old.exists():
            print(f"  {name}: есть только в {'выходе' if new.exists() else 'базовой копии'}")
            ok = False
            continue
        if new.read_bytes() == old.read_bytes():
            print(f"  {name}: совпадает побайтно")
            continue
        if not ignore:
            print(f"  {name}: ОТЛИЧАЕТСЯ")
            ok = False
        elif name == "registry.csv" or name == "registry.json":
            load = _csv if name.endswith(".csv") else (lambda p: json.loads(p.read_text(encoding="utf-8")))
            a, b = load(old), load(new)
            for col in ignore:
                for label, rows in (("в базовой копии", a), ("в выходе", b)):
                    if rows and col in rows[0]:
                        values = {r[col] for r in rows}
                        print(f"  {name}: «{col}» {label}: " + ("везде пусто" if values <= {"—", None}
                                                                 else f"есть значения: {sorted(map(str, values))[:5]}"))
            same = _drop(a, ignore) == _drop(b, ignore)
            print(f"  {name}: без {', '.join(ignore)} — {'совпадает' if same else 'ОТЛИЧАЕТСЯ'}")
            ok &= same
        elif name == "report.md":
            la = collections.Counter(old.read_text(encoding="utf-8").splitlines())
            lb = collections.Counter(new.read_text(encoding="utf-8").splitlines())
            gone, added = list((la - lb).elements()), list((lb - la).elements())
            print(f"  {name}: строки только в базовой копии: {gone or 'нет'}; только в выходе: {added or 'нет'}")
            ok &= all(any(c in line for c in ignore) for line in gone + added)
        else:
            print(f"  {name}: ОТЛИЧАЕТСЯ")
            ok = False
    return ok


def main(argv):
    p = argparse.ArgumentParser(prog="python -m src.baseline")
    p.add_argument("action", choices=["compare", "update"])
    p.add_argument("--std", action="append", help="std_id; по умолчанию — все из merge.yaml")
    p.add_argument("--ignore-column", action="append", default=[])
    a = p.parse_args(argv)
    sids = a.std or standards()
    if a.action == "update":
        for sid in sids:
            src, dst = ROOT / "data/out" / sid, BASELINE / sid
            dst.mkdir(parents=True, exist_ok=True)
            for f in src.iterdir():
                if f.is_file() and f.name not in NOT_COMPARED:
                    shutil.copy2(f, dst / f.name)
            print(f"{sid}: базовая копия обновлена из data/out/{sid}/")
        return 0

    from run import build_registry

    ok = True
    with tempfile.TemporaryDirectory() as tmp:
        for sid in sids:
            print(f"{sid}:")
            out = Path(tmp) / sid
            build_registry(ROOT / "config" / f"{sid}.yaml", out)
            ok &= compare_std(sid, out, set(a.ignore_column))
    print("ИТОГ: " + ("расхождений нет" + (" (кроме игнорируемых колонок)" if a.ignore_column else "")
                      if ok else "ЕСТЬ РАСХОЖДЕНИЯ"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
