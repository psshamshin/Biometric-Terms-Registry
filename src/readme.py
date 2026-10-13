"""Разделы README, которые генерируются из конфигов и схемы при каждом полном прогоне:
подключённые стандарты (с размером эталона) и флаги. Текст между маркерами
<!-- AUTO:имя --> и <!-- /AUTO:имя --> заменяется целиком; остальной README не трогается.
"""
import re

import yaml

def _table(header, rows):
    esc = lambda v: str(v).replace("|", "\\|")
    out = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    out += ["| " + " | ".join(esc(c) for c in r) + " |" for r in rows]
    return "\n".join(out)


def _plural(n, one, few, many):
    if n % 10 == 1 and n % 100 != 11:
        return one
    return few if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14 else many


def _golden_size(path):
    """Эталон: статей и заполненных полей (сверяются посимвольно на каждом прогоне)."""
    if not path.exists():
        return 0, 0
    entries = yaml.safe_load(path.read_text(encoding="utf-8")) or []
    return len(entries), sum(v is not None for e in entries for k, v in e.items() if k != "пункт")


def standards_section(merge_cfg, results, std_id, load_yaml, root):
    rows = []
    for entry in merge_cfg["standards"]:
        sid = std_id(entry["config"])
        std = load_yaml(root / entry["config"])["standard"]
        res_rows = results[sid]["rows"]
        metrics = sum(r["Тип сущности"] == "метрика" for r in res_rows)
        g_arts, g_fields = _golden_size(root / entry["golden"])
        rows.append((std["designation"], len(res_rows), metrics,
                     f"{g_arts} {_plural(g_arts, 'статья', 'статьи', 'статей')} / "
                     f"{g_fields} {_plural(g_fields, 'поле', 'поля', 'полей')}",
                     str(entry.get("connected", "—"))))
    return _table(["Стандарт", "Статей", "Метрик", "Эталон по сканам", "Подключён"], rows)


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
        "flags": flags_section(schema),
    }
