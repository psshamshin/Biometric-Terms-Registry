"""Генератор черновика конфига (src.new_standard): на каждом подключённом стандарте находит те же ключи
и тот же шаблон нумерации, что в его конфиге. Сравниваются наборы ключей, не байты; конфиги не меняются."""
from pathlib import Path

import pytest
import yaml

from src import new_standard

ROOT = Path(__file__).resolve().parent.parent
CONFIGS = [e["config"] for e in yaml.safe_load((ROOT / "config/merge.yaml").read_text(encoding="utf-8"))["standards"]]


@pytest.fixture(scope="module")
def results(tmp_path_factory):
    work = tmp_path_factory.mktemp("new_standard")
    out = {}
    for path in CONFIGS:
        cfg = yaml.safe_load((ROOT / path).read_text(encoding="utf-8"))
        out[path] = (cfg, new_standard.analyze(ROOT / cfg["standard"]["pdf"], work / Path(path).stem))
    return out


@pytest.mark.parametrize("path", CONFIGS)
def test_same_keys(results, path):
    cfg, result = results[path]
    expected = new_standard.config_features(cfg)
    assert result["features"] == expected, (
        f"не нашёл: {sorted(expected - result['features'])}; лишнее: {sorted(result['features'] - expected)}")


@pytest.mark.parametrize("path", CONFIGS)
def test_same_numbering(results, path):
    cfg, result = results[path]
    assert result["cfg"]["numbering"] == cfg["numbering"]


@pytest.mark.parametrize("path", CONFIGS)
def test_same_designation_and_pattern_values(results, path):
    cfg, result = results[path]
    assert result["cfg"]["standard"]["source_column"] == cfg["standard"]["source_column"]
    for key in ("short_forms",):
        assert result["cfg"]["markers"].get(key) == cfg["markers"].get(key)
    assert result["cfg"]["bounds"]["terms"] == cfg["bounds"]["terms"]


@pytest.mark.parametrize("path", CONFIGS)
def test_unparsed_only_where_config_has_corrections(results, path):
    """Генератор не видит скан: статьи с ошибками распознавания остаются header_unparsed — ровно те,
    для которых в конфиге есть corrections."""
    cfg, result = results[path]
    fixed = {str(c["пункт"]) for c in cfg["corrections"]} | {str(n) for n in cfg["header_overrides"]}
    assert {n for n, _, _ in result["unparsed"]} <= fixed
    assert result["problems"] == []


def test_existing_config_is_not_overwritten(tmp_path, monkeypatch):
    out = tmp_path / "x.yaml"
    out.write_text("x", encoding="utf-8")
    with pytest.raises(SystemExit):
        new_standard.main([str(ROOT / "data/raw/85866.pdf"), "--out", str(out)])
    assert out.read_text(encoding="utf-8") == "x"


@pytest.mark.parametrize("path", CONFIGS)
def test_summary_and_draft_yaml(results, path):
    _, result = results[path]
    merge_cfg = yaml.safe_load((ROOT / "config/merge.yaml").read_text(encoding="utf-8"))
    text = new_standard.summary(result, merge_cfg)
    assert "Найденные ключи" in text and "header_unparsed" in text
    draft = yaml.safe_load(new_standard.draft_yaml(result))
    assert draft["numbering"] == result["cfg"]["numbering"]
    assert draft["standard"]["pdf"].startswith("data/raw/")
