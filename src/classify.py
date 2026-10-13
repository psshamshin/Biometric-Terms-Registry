"""Шаги 5–7: тип сущности и статус, область, парные метрики.

Правила типа — в registry_schema.yaml (classification), область — в конфиге стандарта (areas).
"""
import re


def _flag(rec, flag, reason):
    if flag not in rec["flags"]:
        rec["flags"].append(flag)
    rec["flag_reasons"][flag] = reason


def classify(rec, schema):
    """Шаг 5. Возвращает (тип сущности, статус); флаг type_conflict — на записи."""
    c = schema["classification"]
    a_cfg, b_cfg = c["sign_a"], c["sign_b"]
    abbr = rec["abbr_en"] or ""
    sign_a = bool(re.fullmatch(a_cfg["abbr_en_pattern"], abbr)) and any(
        re.search(cond["pattern"], rec[cond["field"]] or "") for cond in a_cfg["any_of"])
    words = "|".join(map(re.escape, b_cfg["definition_starts_with"]))
    sign_b = bool(re.match(rf"(?:{words})\b", rec["definition"] or "", re.IGNORECASE))

    if sign_a and sign_b:
        decision = c["decision"]["both"]
    elif sign_a or sign_b:
        decision = c["decision"]["one"]
        _flag(rec, decision["flag"], "выполнен только признак " + ("А" if sign_a else "Б"))
    else:
        decision = c["decision"]["neither"]
    return decision["entity_type"], decision["status"]


def area(rec, cfg, schema):
    """Шаг 6. Исключение по номеру пункта, иначе по разделу. Вне справочника — нельзя."""
    areas = cfg["areas"]
    value = (areas.get("exceptions") or {}).get(rec["num"]) or areas["sections"].get(rec["section"])
    if value is None:
        _flag(rec, "area_missing", f"раздел {rec['section']} не сопоставлен с областью")
        return None
    if value not in schema["dictionaries"]["area"]:
        raise ValueError(f"область вне справочника в конфиге: {value!r}")
    return value


def _pair_key(name, rules):
    """Название → (общий вид, «сторона» пары) по правилам schema.pairs:
    prefix — приставка (non-) убирается; swap — пара слов (accept/reject) сводится к общему виду."""
    base, side = name, []
    for rule in rules:
        if "prefix" in rule:
            pattern = r"\b" + re.escape(rule["prefix"])
            if re.search(pattern, base):
                side.append(rule["prefix"])
            base = re.sub(pattern, "", base)
        else:
            a, b = rule["swap"]
            if re.search(r"\b" + re.escape(b), base):
                side.append(b)
            base = re.sub(r"\b(%s|%s)" % (re.escape(a), re.escape(b)), f"{a}|{b}", base)
    return base, tuple(side)


def find_pairs(metrics, rules):
    """Шаг 7. Пара — метрика, чьё Наименование en отличается только по одному из правил schema.pairs."""
    pairs = {}
    for m in metrics:
        base, side = _pair_key(m["term_en"] or "", rules)
        for other in metrics:
            if other is m:
                continue
            obase, oside = _pair_key(other["term_en"] or "", rules)
            if obase == base and oside != side:
                pairs.setdefault(m["num"], []).append(other)
    return pairs
