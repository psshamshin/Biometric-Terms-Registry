"""README: разделы 3, 6 и 9 совпадают с конфигами и схемой; общий реестр в sqlite совпадает с registry.json."""
import json

import pytest

from run import README, readme_sections, run_all
from src import readme
from tests.test_regression import sqlite_rows


@pytest.fixture(scope="module")
def full_run(tmp_path_factory):
    out = tmp_path_factory.mktemp("out")
    results, _ = run_all(out)
    return out, results


def test_readme_generated_sections_up_to_date(full_run):
    _, results = full_run
    text = README.read_text(encoding="utf-8")
    assert readme.render(text, readme_sections(results)) == text, "README устарел: запустите python run.py"


def test_every_flag_has_action():
    from src.checks import load_schema
    schema = load_schema()
    assert set(schema["flags"]) == set(schema["flag_actions"])


def test_merged_sqlite_matches_json(full_run):
    out, _ = full_run
    assert sqlite_rows(out / "registry.sqlite") == json.loads((out / "registry.json").read_text(encoding="utf-8"))
