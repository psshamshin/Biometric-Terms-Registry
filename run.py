"""Парсер ГОСТ → реестр терминов по биометрии.

    python run.py                          # все стандарты из config/merge.yaml + объединение
    python run.py config/<стандарт>.yaml   # один стандарт → data/out/<std_id>/
"""
import csv
import json
import re
import sys
from collections import Counter
from pathlib import Path

import yaml

from src import checks, validation
from src.build import build_rows, write_outputs
from src.clean import CleaningLog, apply_corrections, clean
from src.curated import CURATED_DIR
from src.extract import extract_pages
from src.parse import apply_abbreviations, parse_abbreviations, parse_article
from src.split import split_articles

ROOT = Path(__file__).resolve().parent
INTERIM = ROOT / "data/interim"
OUT = ROOT / "data/out"
MERGE_CONFIG = ROOT / "config/merge.yaml"
README = ROOT / "README.md"


def load_yaml(path):
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def write_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def std_id(config_path):
    return Path(config_path).stem


def standard_entry(config_path):
    """Запись стандарта из merge.yaml (пути к эталону и Miro). Нет в списке — эталон по умолчанию, без Miro."""
    sid = std_id(config_path)
    for entry in load_yaml(MERGE_CONFIG)["standards"]:
        if std_id(entry["config"]) == sid:
            return entry
    return {"config": str(config_path), "golden": f"tests/golden_{sid}.yaml", "miro": None}


def parse_standard(config_path, interim_dir):
    """Шаги 2–4: извлечение, очистка, разбиение, разбор. Пишет промежуточные файлы в interim_dir."""
    cfg = load_yaml(config_path)
    interim_dir.mkdir(parents=True, exist_ok=True)
    log = CleaningLog()
    pages = extract_pages(ROOT / cfg["standard"]["pdf"], interim_dir / "pages")
    parts, furniture = clean(pages, cfg, log)
    for name in sorted(parts):
        if name.startswith("index_") or name == "abbreviations":
            (interim_dir / f"{name}.txt").write_text(
                "".join(f"{line}\n" for _, line in parts[name]), encoding="utf-8")

    articles = split_articles(parts["terms"], cfg)
    apply_corrections(articles, cfg, log)
    parsed = [parse_article(a, cfg, log) for a in articles]

    log.write(interim_dir / "cleaning_log.csv")
    write_json(interim_dir / "parsed.json", parsed)
    return cfg, parsed, parts, furniture, log


def write_abbreviations(path, abbreviations):
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["аббр. ru", "аббр. en", "расшифровка ru", "расшифровка en"])
        for a in abbreviations:
            w.writerow([a["abbr_ru"], a["abbr_en"] or "—", a["text_ru"], a["text_en"] or "—"])


def build_registry(config_path, out_dir=None):
    """Шаги 2–10 для одного стандарта: разбор, реестр, выходные файлы, проверки и отчёт."""
    sid = std_id(config_path)
    out_dir = Path(out_dir) if out_dir else OUT / sid
    interim_dir = INTERIM / sid
    entry = standard_entry(config_path)
    schema = checks.load_schema(extra_source=load_yaml(config_path)["standard"]["source_column"])
    cfg, parsed, parts, furniture, log = parse_standard(config_path, interim_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    abbr = None
    if "abbreviations" in parts:
        abbreviations = parse_abbreviations(parts["abbreviations"], cfg)
        actions, unmatched = apply_abbreviations(parsed, abbreviations)  # до классификации: аббревиатура — признак А
        write_abbreviations(out_dir / "abbreviations.csv", abbreviations)
        abbr = (actions, unmatched, len(abbreviations))

    rows = build_rows(parsed, cfg, schema)
    write_outputs(rows, schema, out_dir)

    violations, waiting = checks.check_schema(rows, schema)
    indexes = {name.split("_", 1)[1]: lines for name, lines in parts.items() if name.startswith("index_")}
    index, index_unparsed = checks.check_index(parsed, indexes, cfg) if indexes else (None, [])
    golden_path = ROOT / entry["golden"]
    golden = load_yaml(golden_path) if golden_path.exists() else None
    ctx = {
        "schema": schema, "cfg": cfg, "rows": rows, "parsed": parsed,
        "violations": violations, "waiting": waiting,
        "dict_errors": checks.check_dictionaries(rows, schema),
        "index": index, "index_unparsed": index_unparsed,
        "numbering": checks.check_numbering(parsed),
        "integrity": checks.check_integrity(parsed, cfg, schema, furniture),
        "miro": checks.check_miro(parsed, load_yaml(ROOT / entry["miro"])) if entry["miro"] else None,
        "golden": checks.check_golden(rows, golden),
        "golden_path": entry["golden"],
        "abbreviations": abbr,
        "cleaning_counts": dict(sorted(Counter(re.sub(r" \(.*\)$", "", r[3]) for r in log.rows).items())),
        "cleaning_log_path": (interim_dir / "cleaning_log.csv").relative_to(ROOT).as_posix(),
    }
    checks.write_report(out_dir / "report.md", ctx)
    return ctx


def readme_sections(results):
    """Генерируемые разделы README: подключённые стандарты, колонки реестра, флаги."""
    from src import readme

    return readme.sections(load_yaml(MERGE_CONFIG), checks.load_schema(), results, std_id, load_yaml, ROOT)


def run_all(out_dir=OUT, readme_path=None):
    """Все стандарты из merge.yaml, затем объединение в data/out/registry.* и merge_report.md.
    readme_path — README, в котором обновляются генерируемые разделы (только для полного прогона)."""
    from src import readme
    from src.merge import merge_registries

    merge_cfg = load_yaml(MERGE_CONFIG)
    results = {}
    for entry in merge_cfg["standards"]:
        sid = std_id(entry["config"])
        results[sid] = build_registry(ROOT / entry["config"], Path(out_dir) / sid)
    schema = checks.load_schema()
    merged = merge_registries(merge_cfg, schema, Path(out_dir), curated_dir=CURATED_DIR)
    validation.write_report(Path(out_dir) / "validation_report.md", merged["rows"], schema, validation.load_review())
    if readme_path:
        text = Path(readme_path).read_text(encoding="utf-8")
        Path(readme_path).write_text(readme.render(text, readme_sections(results)), encoding="utf-8")
    return results, merged


def _summary(sid, ctx):
    rows = ctx["rows"]
    metrics = [r["Пункт"] for r in rows if r["Тип сущности"] == "метрика"]
    return (f"{sid}: статей {len(rows)}; метрик {len(metrics)} ({', '.join(metrics)}); "
            f"нарушений схемы {len(ctx['violations'])}")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        config = Path(sys.argv[1])
        print(_summary(std_id(config), build_registry(config)))
        print(f"отчёт: {OUT / std_id(config) / 'report.md'}")
    else:
        results, merged = run_all(readme_path=README)
        for sid, ctx in results.items():
            print(_summary(sid, ctx))
        print(f"общий реестр: строк {len(merged['rows'])}; нарушений схемы {len(merged['violations'])}")
        print(f"отчёт объединения: {OUT / 'merge_report.md'}")
