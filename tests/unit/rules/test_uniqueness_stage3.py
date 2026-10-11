# Ожидаемый API: ai_dm.rules.uniqueness (этап 3, партия 1; STAGE3-PLAN A2, ТЗ 5.3)
#   check_faction(world, faction, heroes) -> list[str]
#   check_god(world, god, heroes) -> list[str]
#   check_hero(world, hero, heroes) -> list[str]   -- heroes: уже существующие ДРУГИЕ герои
#       Как check_npc / check_location: список текстов конфликтов (пусто -- можно добавлять),
#       ничего не мутируют; тексты содержат конфликтующий id / имя.
#       * id уникален среди NPC, фракций, богов, локаций и героев;
#       * имя фракции, бога и героя -- в общем пространстве имён с именованными NPC, героями,
#         богами и фракциями (регистр и пробелы по краям не важны);
#       * безымянный NPC (named=False) имя занять не мешает.
from types import SimpleNamespace

from ai_dm.core.rng import Rng
from ai_dm.rules.uniqueness import check_faction, check_god, check_hero
from ai_dm.state.world import NPC, Faction, God, Location, WorldState

HEROES = [SimpleNamespace(id="hero", name="Арн")]


def make_world():
    world = WorldState(world_id="w1", rng=Rng(1).state)
    world.npcs["aldric"] = NPC(id="aldric", name="Олдрик", named=True, means=["связи"])
    world.npcs["guard_1"] = NPC(id="guard_1", name="Стражник", named=False, means=["меч"])
    world.factions["thieves"] = Faction(id="thieves", name="Гильдия воров")
    world.pantheon["morrah"] = God(id="morrah", name="Моррах")
    world.locations["vale"] = Location(id="vale", name="Вейл")
    return world


def make_hero(hero_id="h2", name="Бранка"):
    return SimpleNamespace(id=hero_id, name=name)


# фракции

def test_new_faction_has_no_conflicts():
    assert check_faction(make_world(), Faction(id="guards", name="Стража"), HEROES) == []


def test_faction_id_equal_to_location_id_is_conflict():
    conflicts = check_faction(make_world(), Faction(id="vale", name="Стража"), HEROES)
    assert len(conflicts) == 1
    assert "vale" in conflicts[0]


def test_faction_id_equal_to_npc_id_is_conflict():
    conflicts = check_faction(make_world(), Faction(id="aldric", name="Орден"), HEROES)
    assert len(conflicts) == 1


def test_faction_name_equal_to_faction_name_is_conflict():
    conflicts = check_faction(make_world(), Faction(id="t2", name="  гильдия ВОРОВ "), HEROES)
    assert len(conflicts) == 1
    assert "воров" in conflicts[0].casefold()


def test_faction_name_equal_to_god_is_conflict():
    assert len(check_faction(make_world(), Faction(id="m", name="Моррах"), HEROES)) == 1


def test_faction_name_equal_to_named_npc_is_conflict():
    assert len(check_faction(make_world(), Faction(id="a", name="Олдрик"), HEROES)) == 1


def test_faction_name_equal_to_hero_is_conflict():
    assert len(check_faction(make_world(), Faction(id="a", name="Арн"), HEROES)) == 1


def test_faction_name_equal_to_unnamed_npc_is_ok():
    assert check_faction(make_world(), Faction(id="s", name="Стражник"), HEROES) == []


def test_faction_id_and_name_both_taken_give_two_lines():
    conflicts = check_faction(make_world(), Faction(id="thieves", name="Гильдия воров"), HEROES)
    assert len(conflicts) == 2


# боги

def test_new_god_has_no_conflicts():
    assert check_god(make_world(), God(id="selune", name="Селунэ"), HEROES) == []


def test_god_id_equal_to_faction_id_is_conflict():
    conflicts = check_god(make_world(), God(id="thieves", name="Бог воров"), HEROES)
    assert len(conflicts) == 1
    assert "thieves" in conflicts[0]


def test_god_id_equal_to_god_id_is_conflict():
    assert len(check_god(make_world(), God(id="morrah", name="Другое имя"), HEROES)) == 1


def test_god_name_equal_to_god_name_is_conflict():
    conflicts = check_god(make_world(), God(id="morrah_2", name="моррах"), HEROES)
    assert len(conflicts) == 1


def test_god_name_equal_to_faction_name_is_conflict():
    assert len(check_god(make_world(), God(id="g", name="Гильдия воров"), HEROES)) == 1


def test_god_name_equal_to_named_npc_is_conflict():
    assert len(check_god(make_world(), God(id="g", name="Олдрик"), HEROES)) == 1


def test_god_name_equal_to_hero_is_conflict():
    assert len(check_god(make_world(), God(id="g", name="Арн"), HEROES)) == 1


# герои

def test_new_hero_has_no_conflicts():
    assert check_hero(make_world(), make_hero(), HEROES) == []


def test_hero_id_equal_to_npc_id_is_conflict():
    conflicts = check_hero(make_world(), make_hero("aldric", "Бранка"), HEROES)
    assert len(conflicts) == 1
    assert "aldric" in conflicts[0]


def test_hero_id_equal_to_other_hero_id_is_conflict():
    assert len(check_hero(make_world(), make_hero("hero", "Бранка"), HEROES)) == 1


def test_hero_id_equal_to_location_id_is_conflict():
    assert len(check_hero(make_world(), make_hero("vale", "Бранка"), HEROES)) == 1


def test_hero_name_equal_to_named_npc_is_conflict():
    conflicts = check_hero(make_world(), make_hero("h2", "Олдрик"), HEROES)
    assert len(conflicts) == 1
    assert "Олдрик" in conflicts[0]


def test_hero_name_equal_to_god_is_conflict():
    assert len(check_hero(make_world(), make_hero("h2", "Моррах"), HEROES)) == 1


def test_hero_name_equal_to_faction_is_conflict():
    assert len(check_hero(make_world(), make_hero("h2", "Гильдия воров"), HEROES)) == 1


def test_hero_name_equal_to_other_hero_is_conflict():
    assert len(check_hero(make_world(), make_hero("h2", " арн "), HEROES)) == 1


def test_hero_name_equal_to_unnamed_npc_is_ok():
    assert check_hero(make_world(), make_hero("h2", "Стражник"), HEROES) == []


def test_checks_do_not_mutate_world():
    world = make_world()
    before = world.model_dump()
    check_faction(world, Faction(id="x", name="Икс"), HEROES)
    check_god(world, God(id="y", name="Игрек"), HEROES)
    check_hero(world, make_hero(), HEROES)
    assert world.model_dump() == before


# Б1а: check_hero после выноса name_taken -- прежние тексты

def test_hero_name_conflict_text_is_unchanged():
    conflicts = check_hero(make_world(), make_hero("h2", "Олдрик"), HEROES)
    assert conflicts == ["имя 'Олдрик' уже занято (NPC, бог, фракция или герой)"]


def test_hero_id_conflict_text_is_unchanged():
    conflicts = check_hero(make_world(), make_hero("aldric", "Бранка"), HEROES)
    assert conflicts == ["id 'aldric' уже занят (NPC, фракция, бог, локация или герой)"]


def test_hero_name_ignores_case_and_spaces():
    assert len(check_hero(make_world(), make_hero("h2", "  олдрик "), HEROES)) == 1


def test_hero_name_equal_to_unnamed_npc_is_not_conflict():
    assert check_hero(make_world(), make_hero("h2", "Стражник"), HEROES) == []


def test_hero_with_both_conflicts_gives_two_lines_id_first():
    conflicts = check_hero(make_world(), make_hero("aldric", "Олдрик"), HEROES)
    assert len(conflicts) == 2
    assert conflicts[0].startswith("id ")
    assert conflicts[1].startswith("имя ")
