"""docs/RULES.md и AGENTS.md не расходятся с кодом: команды существуют и разрешены агенту, флаги и ключи — настоящие."""
import re
from pathlib import Path

import pytest

from src.checks import load_schema

ROOT = Path(__file__).resolve().parent.parent
RULES = (ROOT / "docs/RULES.md").read_text(encoding="utf-8")
AGENTS = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
MODULES = sorted(set(re.findall(r"python -m src\.(\w+)", RULES + AGENTS)))
AGENT_CONFIG = ROOT / ".github/workflows/claude.yml"


def read_allowed_commands() -> list[str]:
    """Разрешения агента из его конфига, в виде `Bash(...)`. Единственное место, привязанное к конкретному агенту:
    при смене агента переписывается только эта функция."""
    text = AGENT_CONFIG.read_text(encoding="utf-8")
    match = re.search(r'--allowedTools\s+"([^"]*)"', text)
    assert match, f"в {AGENT_CONFIG.name} нет --allowedTools"
    return [p.strip() for p in match.group(1).split(",") if p.strip()]


def rules_commands() -> list[str]:
    """Команды из таблицы раздела 1 RULES.md (первая колонка) с подставленными образцами вместо `<...>`,
    обрезанные на необязательных и альтернативных аргументах."""
    section = RULES.split("## 1. Инструменты", 1)[1].split("\n## ", 1)[0]
    commands = []
    for row in re.findall(r"^\| `([^`]+)` \|", section, flags=re.M):
        tokens = []
        for token in row.split():
            if token.startswith("[") or token == "…":
                break
            token = re.split(r"\\?\|", token)[0]
            tokens.append(re.sub(r"<[^>]*>", "x", token))
        commands.append(" ".join(tokens))
    return commands


def is_allowed(command: str, permission: str) -> bool:
    m = re.fullmatch(r"Bash\((.*?)(:\*)?\)", permission)
    if not m:
        return False
    prefix, any_args = m.groups()
    return command == prefix or (bool(any_args) and command.startswith(prefix + " "))


def test_rules_commands_are_parsed():
    assert "python run.py" in rules_commands() and "python -m pytest -q" in rules_commands()


@pytest.mark.parametrize("command", rules_commands())
def test_rules_command_allowed_for_agent(command):
    allowed = read_allowed_commands()
    assert any(is_allowed(command, p) for p in allowed), f"«{command}» из RULES.md не разрешена в конфиге агента"


@pytest.mark.parametrize("permission", read_allowed_commands())
def test_agent_permission_is_listed_in_rules(permission):
    assert any(is_allowed(c, permission) for c in rules_commands()), f"{permission} разрешено агенту, но нет в RULES.md"


@pytest.mark.parametrize("module", MODULES)
def test_documented_command_exists_and_allowed(module):
    assert (ROOT / "src" / f"{module}.py").exists(), f"нет src/{module}.py"
    command = f"python -m src.{module}"
    assert any(is_allowed(command + " x", p) for p in read_allowed_commands()), f"src.{module} не разрешён агенту"


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
