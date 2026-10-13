"""Шаг 9.9: разобранные поля совпадают с эталоном, заполненным вручную по изображениям страниц, посимвольно.
Эталоны всех подключённых стандартов — из config/merge.yaml."""
from pathlib import Path

import pytest
import yaml

from run import build_registry, std_id

ROOT = Path(__file__).resolve().parent.parent
MERGE = yaml.safe_load((ROOT / "config/merge.yaml").read_text(encoding="utf-8"))
STANDARDS = {std_id(e["config"]): e for e in MERGE["standards"]}

# (std_id, пункт, колонка, эталон) — заполненные поля; ~ — ещё не заполнено.
CASES = [
    (sid, entry["пункт"], field, expected)
    for sid, std in STANDARDS.items()
    if (ROOT / std["golden"]).exists()
    for entry in yaml.safe_load((ROOT / std["golden"]).read_text(encoding="utf-8")) or []
    for field, expected in entry.items()
    if field != "пункт" and expected is not None
]


@pytest.fixture(scope="module")
def rows(tmp_path_factory):
    out = {}
    for sid, std in STANDARDS.items():
        result = build_registry(ROOT / std["config"], tmp_path_factory.mktemp(sid))
        out[sid] = {row["Пункт"]: row for row in result["rows"]}
    return out


def test_every_standard_has_golden():
    for sid, std in STANDARDS.items():
        assert any(c[0] == sid for c in CASES), f"эталон {std['golden']} не заполнен"


@pytest.mark.parametrize("sid,num,field,expected", CASES, ids=[f"{s}-{n}-{f}" for s, n, f, _ in CASES])
def test_golden(rows, sid, num, field, expected):
    assert num in rows[sid], f"статьи {num} нет в реестре {sid}"
    assert rows[sid][num][field] == str(expected)
