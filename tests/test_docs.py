"""docs/RULES.md и AGENTS.md не расходятся с кодом: команды существуют и разрешены агенту, флаги и ключи — настоящие."""
import re
from pathlib import Path

import pytest

from src.checks import load_schema

ROOT = Path(__file__).resolve().parent.parent
RULES = (ROOT / "docs/RULES.md").read_text(encoding="utf-8")
AGENTS = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
WORKFLOW = (ROOT / ".github/workflows/claude.yml").read_text(encoding="utf-8")
MODULES = sorted(set(re.findall(r"python -m src\.(\w+)", RULES + AGENTS)))


@pytest.mark.parametrize("module", MODULES)
def test_documented_command_exists_and_allowed(module):
    assert (ROOT / "src" / f"{module}.py").exists(), f"нет src/{module}.py"
    assert f"Bash(python -m src.{module}:*)" in WORKFLOW, f"src.{module} не разрешён агенту в claude.yml"


def test_documented_identifiers_are_real():
    """Каждое `слово_слово` в RULES.md — флаг схемы или реально встречается в конфигах или коде (не выдумано)."""
    flags = set(load_schema()["flags"])
    sources = "".join(p.read_text(encoding="utf-8") for p in list((ROOT / "config").glob("*.yaml")) +
                      list((ROOT / "src").glob("*.py")) + [ROOT / "run.py"])
    words = set(re.findall(r"`([a-z]+(?:_[a-z]+)+)`", RULES))
    unknown = sorted(w for w in words if w not in flags and w not in sources)
    assert not unknown, f"в RULES.md нет в схеме/конфигах/коде: {unknown}"


def test_documented_config_keys_are_used():
    keys = set(re.findall(r"`(?:markers|standard|numbering|cleaning|areas|bounds|abbreviations)\.(\w+)", RULES))
    sources = "".join(p.read_text(encoding="utf-8") for p in list((ROOT / "config").glob("*.yaml")) +
                      list((ROOT / "src").glob("*.py")))
    assert keys and all(k in sources for k in keys), sorted(k for k in keys if k not in sources)
