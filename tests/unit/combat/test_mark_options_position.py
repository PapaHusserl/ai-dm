# Позиция из живого прогона Дракона (docs/plan-stage3.md, раздел T):
# герой Грей на gallery_stairs (высота 1), цепочка gallery_stairs - platform - lower_arch,
# два воина-гоблина в lower_arch (два шага по зонам, до них 90 фт по правилу Метки).
# Ожидаемый API: Метка охотника предлагается на каждого видимого врага в пределах 90 фт
#   бонусным действием (cost "bonus"); пока есть ячейка -- пункт со ячейкой, пока есть
#   Избранный враг -- отдельный пункт с «без ячейки» в подписи; без обоих -- пунктов нет.
from combat_kit import make_engine, mon, option_ids
from test_ranger_combat import make_ranger, pool

from ai_dm.state.combat import Zone, ZoneFeature


def dragon_zones():
    return [
        Zone(id="gallery_stairs", name="Верхние скобы и карниз", adjacent=["platform"],
             exit=True, elevation=1, pos=[0, 0]),
        Zone(id="platform", name="Решётчатая платформа", adjacent=["gallery_stairs", "lower_arch"],
             pos=[1, 0]),
        Zone(id="lower_arch", name="Каменный уступ у арки", adjacent=["platform"], exit=True,
             features=[ZoneFeature(kind="cover_half")], pos=[2, 0]),
    ]


def dragon_engine(registry, cfg):
    return make_engine(
        registry, cfg, heroes=[make_ranger(registry)], zones=dragon_zones(),
        monsters=[mon("goblin_1", "goblin_warrior", "lower_arch", group="cultists"),
                  mon("goblin_2", "goblin_warrior", "lower_arch", group="cultists")],
        hero_zone="gallery_stairs",
    )


def mark_options(engine):
    return [o for o in engine.available_actions("hero") if o.params.get("spell") == "hunters_mark"]


def free_ones(options):
    return [o for o in options if "без ячейки" in o.label]


def slot_ones(options):
    return [o for o in options if "без ячейки" not in o.label]


def test_mark_is_offered_on_both_goblins_through_a_zone(registry, cfg):
    engine = dragon_engine(registry, cfg)
    targets = {o.params["target"] for o in mark_options(engine)}
    assert targets == {"goblin_1", "goblin_2"}


def test_slot_mark_is_offered_on_each_goblin(registry, cfg):
    engine = dragon_engine(registry, cfg)
    assert "cast:hunters_mark:1:goblin_1" in option_ids(engine, "hero")
    assert "cast:hunters_mark:1:goblin_2" in option_ids(engine, "hero")


def test_mark_options_are_bonus_actions(registry, cfg):
    engine = dragon_engine(registry, cfg)
    options = mark_options(engine)
    assert options
    assert {o.cost for o in options} == {"bonus"}


def test_mark_has_a_separate_free_option_per_goblin_with_favored_enemy(registry, cfg):
    engine = dragon_engine(registry, cfg)
    assert pool(engine, "favored_enemy").current == 2
    options = mark_options(engine)
    assert {o.params["target"] for o in free_ones(options)} == {"goblin_1", "goblin_2"}
    assert {o.params["target"] for o in slot_ones(options)} == {"goblin_1", "goblin_2"}
    assert len({o.id for o in options}) == 4


def test_free_option_label_shows_remaining_uses(registry, cfg):
    engine = dragon_engine(registry, cfg)
    assert all("2/2" in o.label for o in free_ones(mark_options(engine)))


def test_without_slots_only_free_options_stay(registry, cfg):
    engine = dragon_engine(registry, cfg)
    pool(engine, "spell_slot:1").current = 0
    options = mark_options(engine)
    assert {o.params["target"] for o in free_ones(options)} == {"goblin_1", "goblin_2"}
    assert slot_ones(options) == []


def test_without_favored_enemy_only_slot_options_stay(registry, cfg):
    engine = dragon_engine(registry, cfg)
    pool(engine, "favored_enemy").current = 0
    options = mark_options(engine)
    assert free_ones(options) == []
    assert {o.params["target"] for o in slot_ones(options)} == {"goblin_1", "goblin_2"}


def test_without_slots_and_favored_enemy_there_is_no_mark(registry, cfg):
    engine = dragon_engine(registry, cfg)
    pool(engine, "spell_slot:1").current = 0
    pool(engine, "favored_enemy").current = 0
    assert mark_options(engine) == []


def test_free_option_spends_favored_enemy_and_keeps_the_slot(registry, cfg):
    engine = dragon_engine(registry, cfg)
    option = free_ones(mark_options(engine))[0]
    engine.perform("hero", option.id)
    assert pool(engine, "favored_enemy").current == 1
    assert pool(engine, "spell_slot:1").current == 2


def test_slot_option_spends_the_slot_and_keeps_favored_enemy(registry, cfg):
    engine = dragon_engine(registry, cfg)
    option = slot_ones(mark_options(engine))[0]
    engine.perform("hero", option.id)
    assert pool(engine, "favored_enemy").current == 2
    assert pool(engine, "spell_slot:1").current == 1


def test_mark_is_not_offered_when_bonus_action_is_spent(registry, cfg):
    engine = dragon_engine(registry, cfg)
    engine.part("hero").turn.bonus = False
    assert mark_options(engine) == []
