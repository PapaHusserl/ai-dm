# /inv с сюжетными предметами (CUSTOM-ITEMS-PLAN, разд. 3 и 8, партия Б).
#   Квестовый предмет мира -- отдельная группа «Сюжетное», самая первая (выше «Оружия»);
#   обычный кастомный -- «Ценности и прочее». У предмета видно описание и, если заданы,
#   вес и цена в формате «0,1 фнт, 5 зм» (вес -- CustomItem.weight_centilb, цена -- cost_cp
#   записи стека). Описание и вес/цена -- в строке предмета или в следующей, более глубоко
#   отступленной строке под ним. Нет веса -- нет «фнт»; нет цены -- нет цены (хвоста нет).
from ai_dm.game.sheet_text import inv_lines
from ai_dm.rules.custom_items import world_registry
from ai_dm.rules.inventory import add_item
from ai_dm.state.creature import CreatureState
from ai_dm.state.hero import BackgroundSpec, CharacterSheet, ClassLevel, HeroState
from ai_dm.state.world import CustomItem


def make_hero():
    sheet = CharacterSheet(
        species_id="human",
        classes=[ClassLevel(class_id="fighter")], level_history=["fighter"] * 1,
        background=BackgroundSpec(
            name="Солдат",
            abilities=["str", "dex", "con"],
            skills=["athletics", "intimidation"],
            tool="dice_set",
            feat="savage_attacker",
        ),
        abilities={"str": 17, "dex": 13, "con": 15, "int": 8, "wis": 10, "cha": 12},
    )
    return HeroState(
        id="h1", ordinal=1, name="Арн", sheet=sheet,
        creature=CreatureState(hp_current=12, hp_max=12),
    )


class World:
    def __init__(self):
        self.custom_items = {}


def custom(item_id="custom_1", name="Ржавый ключ", **fields):
    data = {"description": "Ключ от ворот", "quest": True, "created_s": 0}
    data.update(fields)
    return CustomItem(id=item_id, name=name, **data)


def inventory(registry, items, cost_cp=0):
    # герой с предметами мира (по одному на запись) -> строки /inv
    hero = make_hero()
    world = World()
    for item in items:
        world.custom_items[item.id] = item
        add_item(hero, item.id, cost_cp=cost_cp)
    return hero, world_registry(registry, world)


def lines_of(registry, items, cost_cp=0, extra=None):
    hero, overlay = inventory(registry, items, cost_cp)
    if extra:
        extra(hero)
    return inv_lines(hero, overlay, "0 мм")


def item_block(lines, name):
    # строка предмета и, если за ней идёт более глубоко отступленная, строка под ним
    index = next(i for i, line in enumerate(lines) if name in line)
    block = lines[index]
    if index + 1 < len(lines):
        below = lines[index + 1]
        if len(below) - len(below.lstrip()) > len(lines[index]) - len(lines[index].lstrip()):
            block += "\n" + below
    return block


def titles(lines):
    return [line for line in lines if not line.startswith(" ")]


# группы

def test_quest_item_goes_to_the_story_group(registry):
    lines = lines_of(registry, [custom()])
    assert "Сюжетное:" in lines
    assert lines.index("Сюжетное:") < next(i for i, x in enumerate(lines) if "Ржавый ключ" in x)


def test_story_group_is_first(registry):
    lines = lines_of(registry, [custom()], extra=lambda h: add_item(h, "arrows", cost_cp=1))
    assert titles(lines)[0] == "Сюжетное:"
    assert "Снаряжение и инструменты:" in titles(lines)


def test_story_group_comes_before_weapons(registry):
    lines = lines_of(registry, [custom()], extra=lambda h: add_item(h, "dagger", cost_cp=200))
    assert titles(lines).index("Сюжетное:") < titles(lines).index("Оружие:")


def test_plain_custom_item_is_in_valuables(registry):
    lines = lines_of(registry, [custom(quest=False, name="Тряпичная кукла")])
    assert "Сюжетное:" not in lines
    start = lines.index("Ценности и прочее:")
    assert "Тряпичная кукла" in lines[start + 1]


def test_quest_item_is_not_in_valuables(registry):
    lines = lines_of(registry, [custom()])
    assert "Ценности и прочее:" not in lines


def test_story_group_lists_only_quest_items(registry):
    items = [custom(), custom("custom_2", "Тряпичная кукла", quest=False)]
    lines = lines_of(registry, items)
    story = lines.index("Сюжетное:")
    valuables = lines.index("Ценности и прочее:")
    assert any("Ржавый ключ" in x for x in lines[story:valuables])
    assert not any("Тряпичная кукла" in x for x in lines[story:valuables])


def test_no_story_group_without_quest_items(registry):
    lines = lines_of(registry, [], extra=lambda h: add_item(h, "dagger", cost_cp=200))
    assert "Сюжетное:" not in lines


# описание, вес, цена

def test_description_is_shown(registry):
    lines = lines_of(registry, [custom()])
    assert "Ключ от ворот" in item_block(lines, "Ржавый ключ")


def test_weight_and_cost_are_shown(registry):
    lines = lines_of(registry, [custom(weight_centilb=10)], cost_cp=500)
    block = item_block(lines, "Ржавый ключ")
    assert "0,1 фнт" in block
    assert "5 зм" in block


def test_whole_weight_has_no_fraction(registry):
    lines = lines_of(registry, [custom(weight_centilb=200)], cost_cp=500)
    block = item_block(lines, "Ржавый ключ")
    assert "2 фнт" in block
    assert "2,0" not in block


def test_weight_is_shown_without_cost(registry):
    lines = lines_of(registry, [custom(weight_centilb=150)], cost_cp=0)
    block = item_block(lines, "Ржавый ключ")
    assert "1,5 фнт" in block
    assert "0 мм" not in block


def test_item_without_weight_has_no_weight_tail(registry):
    lines = lines_of(registry, [custom(weight_centilb=None)], cost_cp=500)
    block = item_block(lines, "Ржавый ключ")
    assert "фнт" not in block
    assert "5 зм" in block


def test_item_without_weight_and_cost_has_no_tail(registry):
    lines = lines_of(registry, [custom(description="")], cost_cp=0)
    block = item_block(lines, "Ржавый ключ")
    assert "фнт" not in block
    assert "(" not in block
    assert "мм" not in block and "зм" not in block


def test_item_without_description_still_shows_weight(registry):
    lines = lines_of(registry, [custom(description="", weight_centilb=10)], cost_cp=500)
    block = item_block(lines, "Ржавый ключ")
    assert "0,1 фнт" in block


def test_srd_item_has_no_weight_or_description_tail(registry):
    lines = lines_of(registry, [], extra=lambda h: add_item(h, "dagger", cost_cp=200))
    block = item_block(lines, "Кинжал")
    assert "фнт" not in block


# цена экземпляра по стекам

def test_custom_stacks_with_different_cost_are_separate_lines(registry):
    def more(hero):
        add_item(hero, "custom_1", cost_cp=1500)

    lines = lines_of(registry, [custom()], cost_cp=500, extra=more)
    keys = [x for x in lines if "Ржавый ключ" in x]
    assert len(keys) == 2
    assert any("5 зм" in x for x in keys)
    assert any("15 зм" in x for x in keys)


def test_quantity_of_a_custom_stack_is_shown(registry):
    def more(hero):
        add_item(hero, "custom_1", 2, cost_cp=0)

    lines = lines_of(registry, [custom()], cost_cp=0, extra=more)
    line = [x for x in lines if "Ржавый ключ" in x][0]
    assert "x3" in line


def test_weight_and_cost_go_together_through_a_comma(registry):
    lines = lines_of(registry, [custom(weight_centilb=10)], cost_cp=500)
    assert "0,1 фнт, 5 зм" in item_block(lines, "Ржавый ключ")


def test_description_goes_before_weight_and_cost(registry):
    lines = lines_of(registry, [custom(weight_centilb=10)], cost_cp=500)
    block = item_block(lines, "Ржавый ключ")
    assert block.index("Ключ от ворот") < block.index("0,1 фнт")


def test_zero_weight_is_not_shown(registry):
    lines = lines_of(registry, [custom(weight_centilb=0)], cost_cp=500)
    block = item_block(lines, "Ржавый ключ")
    assert "фнт" not in block
    assert "5 зм" in block


def test_item_line_is_exact_with_tail(registry):
    lines = lines_of(registry, [custom(weight_centilb=10)], cost_cp=500)
    assert lines[1].strip().endswith("Ключ от ворот (0,1 фнт, 5 зм)")


def test_item_line_is_exact_without_tail(registry):
    lines = lines_of(registry, [custom()], cost_cp=0)
    assert lines[1].strip().endswith("Ржавый ключ — Ключ от ворот")
    assert lines[1].strip().split(" — ")[1] == "Ключ от ворот"
