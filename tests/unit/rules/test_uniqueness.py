# Ожидаемый API: ai_dm.rules.uniqueness (этап 2, партия 1; ТЗ 5.3 «Уникальность сущностей»)
#   check_npc(world: WorldState, npc: NPC, heroes: list[HeroState]) -> list[str]
#   check_location(world: WorldState, location: Location, heroes: list[HeroState]) -> list[str]
#       Возвращают список текстов конфликтов (пустой список -- можно добавлять). Ничего не
#       мутируют и не добавляют в world. Тексты на русском, содержат конфликтующий id / имя.
#       Правила:
#         * id уникален среди NPC, фракций, богов, локаций и героев (строгая уникальность)
#         * имя именованного NPC (named=True) уникально среди именованных NPC, героев, богов
#           (world.pantheon) и фракций (world.factions) -- одно общее пространство имён;
#           безымянные NPC (named=False) могут повторять имена («Стражник»)
#         * имя локации уникально в пределах parent_id (None -- верхний уровень);
#           в разных родителях одинаковое имя можно
#         * имена сравниваются без учёта регистра и пробелов по краям
#         * несколько нарушений -- несколько строк (id и имя -- по строке на каждое)
from types import SimpleNamespace

from ai_dm.core.rng import Rng
from ai_dm.rules.uniqueness import check_location, check_npc
from ai_dm.state.world import NPC, Faction, God, Location, WorldState

HEROES = [SimpleNamespace(id="hero", name="Арн")]


def make_npc(npc_id="aldric", name="Олдрик", named=True):
    return NPC(id=npc_id, name=name, named=named, means=["связи"])


def make_location(loc_id, name, parent_id=None):
    return Location(id=loc_id, name=name, parent_id=parent_id)


def make_world():
    world = WorldState(world_id="w1", rng=Rng(1).state)
    world.npcs["aldric"] = make_npc()
    world.npcs["guard_1"] = make_npc("guard_1", "Стражник", named=False)
    world.factions["thieves"] = Faction(id="thieves", name="Гильдия воров")
    world.pantheon["morrah"] = God(id="morrah", name="Моррах")
    world.locations["vale"] = make_location("vale", "Вейл")
    world.locations["capital"] = make_location("capital", "Столица")
    world.locations["vale_tavern"] = make_location("vale_tavern", "Таверна", "vale")
    return world


# NPC

def test_new_npc_has_no_conflicts():
    assert check_npc(make_world(), make_npc("brana", "Бранка"), HEROES) == []


def test_duplicate_npc_id_is_conflict():
    conflicts = check_npc(make_world(), make_npc("aldric", "Другое Имя"), HEROES)
    assert len(conflicts) == 1
    assert "aldric" in conflicts[0]


def test_duplicate_named_npc_name_is_conflict():
    conflicts = check_npc(make_world(), make_npc("aldric_2", "Олдрик"), HEROES)
    assert len(conflicts) == 1
    assert "Олдрик" in conflicts[0]


def test_name_comparison_ignores_case_and_edge_spaces():
    assert len(check_npc(make_world(), make_npc("a2", "  олдрик "), HEROES)) == 1


def test_named_npc_cannot_take_god_name():
    conflicts = check_npc(make_world(), make_npc("m", "Моррах"), HEROES)
    assert len(conflicts) == 1
    assert "Моррах" in conflicts[0]


def test_named_npc_cannot_take_faction_name():
    conflicts = check_npc(make_world(), make_npc("t", "Гильдия воров"), HEROES)
    assert len(conflicts) == 1


def test_unnamed_npc_may_repeat_name():
    assert check_npc(make_world(), make_npc("guard_2", "Стражник", named=False), HEROES) == []


def test_same_id_and_same_name_give_two_conflicts():
    conflicts = check_npc(make_world(), make_npc("aldric", "Олдрик"), HEROES)
    assert len(conflicts) == 2


def test_unnamed_npc_with_duplicate_id_is_still_conflict():
    assert len(check_npc(make_world(), make_npc("guard_1", "Стражник", named=False), HEROES)) == 1


def test_npc_check_does_not_change_world():
    world = make_world()
    before = world.model_dump_json()
    check_npc(world, make_npc("aldric", "Олдрик"), HEROES)
    assert world.model_dump_json() == before


def test_npc_check_on_empty_world_is_clean():
    world = WorldState(world_id="w1", rng=Rng(1).state)
    assert check_npc(world, make_npc(), HEROES) == []


# локации

def test_new_location_has_no_conflicts():
    assert check_location(make_world(), make_location("port", "Порт"), HEROES) == []


def test_duplicate_location_id_is_conflict():
    conflicts = check_location(make_world(), make_location("vale", "Другая долина"), HEROES)
    assert len(conflicts) == 1
    assert "vale" in conflicts[0]


def test_same_name_in_same_parent_is_conflict():
    tavern = make_location("vale_tavern_2", "Таверна", "vale")
    conflicts = check_location(make_world(), tavern, HEROES)
    assert len(conflicts) == 1
    assert "Таверна" in conflicts[0]


def test_same_name_in_other_parent_is_allowed():
    tavern = make_location("cap_tavern", "Таверна", "capital")
    assert check_location(make_world(), tavern, HEROES) == []


def test_same_name_at_top_level_is_conflict():
    conflicts = check_location(make_world(), make_location("vale_2", "Вейл"), HEROES)
    assert len(conflicts) == 1


def test_same_name_top_level_vs_nested_is_allowed():
    assert check_location(make_world(), make_location("tavern_top", "Таверна"), HEROES) == []


def test_location_name_comparison_ignores_case():
    assert len(check_location(make_world(), make_location("t2", "ТАВЕРНА", "vale"), HEROES)) == 1


def test_location_name_may_equal_npc_or_god_name():
    assert check_location(make_world(), make_location("morrah_temple", "Моррах"), HEROES) == []


def test_location_check_does_not_change_world():
    world = make_world()
    before = world.model_dump_json()
    check_location(world, make_location("vale", "Вейл"), HEROES)
    assert world.model_dump_json() == before


# строгая уникальность: герои, id между видами сущностей

def test_npc_id_equal_to_faction_id_is_conflict():
    conflicts = check_npc(make_world(), make_npc("thieves", "Вор"), HEROES)
    assert len(conflicts) == 1
    assert "thieves" in conflicts[0]


def test_npc_id_equal_to_god_id_is_conflict():
    conflicts = check_npc(make_world(), make_npc("morrah", "Жрец"), HEROES)
    assert len(conflicts) == 1
    assert "morrah" in conflicts[0]


def test_npc_id_equal_to_location_id_is_conflict():
    conflicts = check_npc(make_world(), make_npc("vale", "Житель"), HEROES)
    assert len(conflicts) == 1
    assert "vale" in conflicts[0]


def test_npc_id_equal_to_hero_id_is_conflict():
    conflicts = check_npc(make_world(), make_npc("hero", "Другой"), HEROES)
    assert len(conflicts) == 1
    assert "hero" in conflicts[0]


def test_unnamed_npc_id_equal_to_hero_id_is_conflict():
    assert len(check_npc(make_world(), make_npc("hero", "Стражник", named=False), HEROES)) == 1


def test_named_npc_name_equal_to_hero_name_is_conflict():
    conflicts = check_npc(make_world(), make_npc("arn_2", "Арн"), HEROES)
    assert len(conflicts) == 1
    assert "Арн" in conflicts[0]


def test_hero_name_comparison_ignores_case_and_edge_spaces():
    assert len(check_npc(make_world(), make_npc("arn_2", "  арн "), HEROES)) == 1


def test_unnamed_npc_may_take_hero_name():
    assert check_npc(make_world(), make_npc("arn_2", "Арн", named=False), HEROES) == []


def test_npc_check_without_heroes_ignores_hero_names():
    assert check_npc(make_world(), make_npc("hero", "Арн"), []) == []


def test_location_id_equal_to_npc_id_is_conflict():
    conflicts = check_location(make_world(), make_location("aldric", "Кузня"), HEROES)
    assert len(conflicts) == 1
    assert "aldric" in conflicts[0]


def test_location_id_equal_to_faction_id_is_conflict():
    assert len(check_location(make_world(), make_location("thieves", "Притон"), HEROES)) == 1


def test_location_id_equal_to_god_id_is_conflict():
    assert len(check_location(make_world(), make_location("morrah", "Храм"), HEROES)) == 1


def test_location_id_equal_to_hero_id_is_conflict():
    conflicts = check_location(make_world(), make_location("hero", "Дом"), HEROES)
    assert len(conflicts) == 1
    assert "hero" in conflicts[0]


def test_location_name_may_equal_hero_name():
    assert check_location(make_world(), make_location("arn_hill", "Арн"), HEROES) == []


# Б1а (B1-PLAN A1): name_taken(name, taken) -> bool -- общее сравнение имён героя

def test_name_taken_finds_equal_name():
    from ai_dm.rules.uniqueness import name_taken

    assert name_taken("Олдрик", ["Бранка", "Олдрик"]) is True


def test_name_taken_ignores_case():
    from ai_dm.rules.uniqueness import name_taken

    assert name_taken("олдрик", ["ОЛДРИК"]) is True


def test_name_taken_ignores_edge_spaces_on_both_sides():
    from ai_dm.rules.uniqueness import name_taken

    assert name_taken("  Олдрик ", [" олдрик"]) is True


def test_name_taken_is_false_for_other_name():
    from ai_dm.rules.uniqueness import name_taken

    assert name_taken("Бранка", ["Олдрик", "Стражник"]) is False


def test_name_taken_is_false_for_empty_list():
    from ai_dm.rules.uniqueness import name_taken

    assert name_taken("Олдрик", []) is False


def test_name_taken_does_not_match_part_of_name():
    from ai_dm.rules.uniqueness import name_taken

    assert name_taken("Олд", ["Олдрик"]) is False


def test_name_taken_accepts_any_iterable():
    from ai_dm.rules.uniqueness import name_taken

    assert name_taken("Олдрик", (n for n in ["Олдрик"])) is True
