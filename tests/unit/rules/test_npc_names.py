# Ж1 (docs/plan-zh1.md, п. 0.2): скрытое имя NPC движка.
#   name_hidden: origin="engine" и known_name не задан; NPC пака и ai -- имя публично;
#   shown_name: известное имя, иначе метка вида из боя (NPC.combat["label"]), иначе name.
from ai_dm.rules.npc_names import name_hidden, shown_name
from ai_dm.state.world import NPC


def engine_npc(**kwargs):
    base = {
        "id": "goblin_warrior_1", "name": "Гракх", "origin": "engine", "means": ["бой"],
        "combat": {"monster_id": "goblin_warrior", "label": "Воин-гоблин 1"},
    }
    return NPC(**{**base, **kwargs})


def test_engine_npc_without_known_name_is_hidden():
    assert name_hidden(engine_npc()) is True


def test_engine_npc_with_known_name_is_not_hidden():
    assert name_hidden(engine_npc(known_name="Гракх")) is False


def test_pack_npc_is_not_hidden():
    assert name_hidden(NPC(id="a", name="Олдрик", means=["бой"])) is False


def test_ai_npc_is_not_hidden():
    assert name_hidden(NPC(id="a", name="Олдрик", means=["бой"], origin="ai")) is False


def test_hidden_engine_npc_shows_label():
    assert shown_name(engine_npc()) == "Воин-гоблин 1"


def test_engine_npc_with_known_name_shows_it():
    assert shown_name(engine_npc(known_name="Гракх")) == "Гракх"


def test_pack_npc_shows_real_name_even_with_combat_label():
    npc = NPC(id="a", name="Олдрик", means=["бой"], combat={"label": "Воин"})
    assert shown_name(npc) == "Олдрик"


def test_ai_npc_shows_real_name():
    assert shown_name(NPC(id="a", name="Олдрик", means=["бой"], origin="ai")) == "Олдрик"


def test_engine_npc_without_combat_shows_name():
    assert shown_name(engine_npc(combat=None)) == "Гракх"


def test_engine_npc_combat_without_label_shows_name():
    assert shown_name(engine_npc(combat={"monster_id": "goblin_warrior"})) == "Гракх"
