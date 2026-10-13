"""Разделы README, которые генерируются из конфигов и схемы при каждом полном прогоне:
подключённые стандарты, колонки реестра, флаги. Текст между маркерами
<!-- AUTO:имя --> и <!-- /AUTO:имя --> заменяется целиком; остальной README не трогается.
"""
import re

FILLED_BY = {
    "parser": "парсер",
    "source": "парсер, дословно из стандарта",
    "llm": "LLM, через data/curated/",
    "consumer": "потребитель реестра",
}


def _table(header, rows):
    esc = lambda v: str(v).replace("|", "\\|")
    out = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    out += ["| " + " | ".join(esc(c) for c in r) + " |" for r in rows]
    return "\n".join(out)


def standards_section(merge_cfg, results, std_id, load_yaml, root):
    rows = []
    for entry in merge_cfg["standards"]:
        sid = std_id(entry["config"])
        std = load_yaml(root / entry["config"])["standard"]
        res_rows = results[sid]["rows"]
        metrics = sum(r["Тип сущности"] == "метрика" for r in res_rows)
        rows.append((std["designation"], f"`{sid}`", std["source_column"], len(res_rows), metrics,
                     str(entry.get("connected", "—"))))
    return _table(["Обозначение", "std_id", "Колонка", "Статей", "Метрик", "Подключён"], rows)


def columns_section(schema, merge_cfg):
    rows = [(c["n"], c["name"], c["type"], c["constraint"], FILLED_BY.get(c["filled_by"], c["filled_by"]))
            for c in schema["columns"]]
    text = _table(["№", "Колонка", "Тип", "Что в ней (ограничение)", "Кто заполняет"], rows)
    return (text + "\n\nСлужебные колонки реестра стандарта: " + ", ".join(schema["service_columns"]) +
            ".\nСлужебные колонки общего реестра: " + ", ".join(merge_cfg["service_columns"]) + ".")


def flags_section(schema):
    rows = [(f"`{f}`", when, schema["flag_actions"][f]) for f, when in schema["flags"].items()]
    return _table(["Флаг", "Когда ставится", "Что с ним делать"], rows)


def render(text, sections):
    for name, body in sections.items():
        pattern = re.compile(rf"(<!-- AUTO:{name} -->\n)(?:.*?\n)?(<!-- /AUTO:{name} -->)", re.S)
        if not pattern.search(text):
            raise ValueError(f"в README нет маркеров раздела {name}")
        text = pattern.sub(lambda m: m.group(1) + body + "\n" + m.group(2), text)
    return text


def sections(merge_cfg, schema, results, std_id, load_yaml, root):
    return {
        "standards": standards_section(merge_cfg, results, std_id, load_yaml, root),
        "columns": columns_section(schema, merge_cfg),
        "flags": flags_section(schema),
    }
