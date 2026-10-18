# Ж1 (docs/plan-zh1.md, п. 0.2): скрытое имя NPC движка.
#   name_hidden: origin="engine" и known_name не задан; NPC пака и ai -- имя публично;
#   shown_name: известное имя, иначе метка вида из боя (NPC.combat["label"]), иначе name.
from ai_dm.rules.npc_names import looks_like_kind, name_hidden, shown_name
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


# Ж2 (п. 0.11, BACKLOG 86): looks_like_kind(registry, npc, name) -- имя совпадает с видом:
# метка боя (с номером и без) или название монстра реестра; регистр и пробелы по краям не важны

def test_label_with_number_looks_like_kind(registry):
    assert looks_like_kind(registry, engine_npc(), "Воин-гоблин 1") is True


def test_label_without_number_looks_like_kind(registry):
    assert looks_like_kind(registry, engine_npc(), "Воин-гоблин") is True


def test_custom_label_without_number_looks_like_kind(registry):
    npc = engine_npc(combat={"monster_id": "x", "label": "Бродяга 1"})
    assert looks_like_kind(registry, npc, "Бродяга") is True


def test_kind_check_ignores_case_and_edge_spaces(registry):
    assert looks_like_kind(registry, engine_npc(), "  воин-ГОБЛИН 1 ") is True


def test_monster_name_of_registry_looks_like_kind_without_label(registry):
    assert looks_like_kind(registry, engine_npc(combat=None), "Кабан") is True


def test_monster_name_of_other_kind_looks_like_kind(registry):
    assert looks_like_kind(registry, engine_npc(), "Лютый волк") is True


def test_personal_name_does_not_look_like_kind(registry):
    assert looks_like_kind(registry, engine_npc(), "Мурк") is False


def test_name_containing_kind_among_other_words_is_allowed(registry):
    assert looks_like_kind(registry, engine_npc(), "Мурк Воин-гоблин") is False


def test_empty_name_does_not_look_like_kind_without_label(registry):
    assert looks_like_kind(registry, engine_npc(combat=None), "") is False


def test_empty_name_does_not_look_like_kind_with_empty_label(registry):
    npc = engine_npc(combat={"monster_id": "goblin_warrior", "label": ""})
    assert looks_like_kind(registry, npc, "  ") is False


def test_npc_without_combat_has_no_label_kind(registry):
    assert looks_like_kind(registry, engine_npc(combat=None), "Воин-гоблин 1") is False


def test_combat_without_label_key_has_no_label_kind(registry):
    npc = engine_npc(combat={"monster_id": "goblin_warrior"})
    assert looks_like_kind(registry, npc, "xxxx") is False


def test_engine_npc_combat_without_label_shows_name():
    assert shown_name(engine_npc(combat={"monster_id": "goblin_warrior"})) == "Гракх"
