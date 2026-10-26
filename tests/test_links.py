"""Связь «используется в определении» (src/links.py): словоформы, сокращения, синонимы; лишних связей нет."""
from src.links import abbreviation_aliases, mentions

E = "—"


def r(rid, name_ru, abbr_en=E, abbr_ru=E, synonyms=E):
    return {"id": rid, "Наименование ru": name_ru, "Аббревиатура en": abbr_en, "Аббревиатура ru": abbr_ru, "Синонимы": synonyms}


ROWS = [
    r("pai-species", "Вид инструментов атаки на биометрическое предъявление"),
    r("pai", "Инструмент атаки на биометрическое предъявление", "PAI", "ИАБП"),
    r("pad", "Обнаружение атаки на биометрическое предъявление", "PAD", "ОАБП"),
    r("artefact", "Артефакт"),
    r("biometric-claim", "Биометрическое заявление"),
    r("identification-transaction", "Транзакция идентификации"),
    r("transaction", "Транзакция биометрической регистрации"),
    r("biometric-acquisition-process", "Процесс получения биометрических данных"),
    r("cmc", "График характеристики совокупного совпадения", synonyms="график ХСС, CMC plot"),
    r("identity-concealer", "Укрыватель личности"),
    r("rank", "Ранг идентификации"),
    r("attack", "Атака на биометрическое предъявление"),
]


def found(text, aliases=None):
    return set(mentions(text, ROWS, "self", E, aliases))


def test_case_and_number_forms():
    assert "pai-species" in found("Доля предъявлений при атаке одного вида инструментов атаки на биометрическое предъявление")
    assert "pai-species" in found("при атаке одним видом инструментов атаки на биометрическое предъявление")
    assert "pai-species" in found("одного вида инструмента атаки на биометрическое предъявление")
    assert "artefact" in found("Доля предъявлений артефакта, которые")
    assert "biometric-claim" in found("транзакций с ложными биометрическими заявлениями")
    assert "biometric-acquisition-process" in found("набора процессов получения биометрических данных")


def test_adjective_inside_name():
    assert "identification-transaction" in found("Доля транзакций биометрической идентификации незарегистрированных")
    assert "identification-transaction" not in found("Доля транзакций с ложными биометрическими заявлениями")


def test_abbreviations_of_the_record():
    assert "pad" in found("отсутствие ответа со стороны подсистемы ОАБП")
    assert "pad" in found("PAD subsystem")
    assert "pad" not in found("слово пада и оабп в нижнем регистре")        # сокращение — с тем же регистром


def test_abbreviations_from_standard_section():
    aliases = abbreviation_aliases(ROWS, [{"abbr_ru": "ВИАБП", "abbr_en": "PAIS",
                                           "text_ru": "вид инструмента атаки на биометрическое предъявление"}], E)
    assert aliases == {"pai-species": ["ВИАБП", "PAIS"]}
    assert "pai-species" in found("одного ВИАБП", aliases)
    assert "pai-species" not in found("одного ВИАБП")                        # без раздела «Сокращения» связи нет


def test_synonyms_of_the_record():
    assert "cmc" in found("см. график ХСС в приложении")
    assert "cmc" in found("CMC plot")


def test_no_extra_links():
    assert found("доля атак") == set()                                       # «атака» без «на биометрическое предъявление»
    assert "identity-concealer" not in found("при атаке укрывателя")         # только целое название, без угадывания по корню
    assert "rank" not in found("в ранге R или выше")
    assert found("вид спорта") == set()
    assert "pai" not in found("одного вида инструментов атаки на биометрическое предъявление")  # вложено в более длинное
