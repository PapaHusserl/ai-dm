# Ж3 (docs/plan-zh3.md, п. 0.7, шаг 8а): журнал знаний в состоянии хода рассказчика.
#   state_data["knowledge"] = {вид: {ref: ["текст (источник[: рассказавший])"]}}; ключа нет, если
#   отбор пуст или [master] knowledge_max = 0.
#   Отбор (PromptBuilder.knowledge_refs): npc -- NPC сцены и known_npcs; location -- локация героя
#   и context_plan.location_ids; god -- боги из hero.favor; faction и situation -- все; creature --
#   только combat_classify/combat_narrate и только по monster_id участников боя.
#   Записи движка о знакомстве и месте (seen, префиксы «Знакомство: »/«Место: ») не идут.
#   Потолок knowledge_max: новейшие по (at_s, порядок журнала).
import json
from types import SimpleNamespace

import pytest
from master_kit import app_cfg, make_ctx

from ai_dm.master.prompt import PromptBuilder
from ai_dm.state.combat import CombatState, Participant
from ai_dm.state.knowledge import KnowledgeEntry


def entry(text, kind="npc", ref="grakh", source="rumor", at_s=0, from_ref=None):
    return KnowledgeEntry(
        kind=kind, ref=ref, text=text, source=source, at_s=at_s, from_ref=from_ref
    )


def state(ctx, mode="explore", cfg=None):
    request = PromptBuilder(cfg or app_cfg()).build(ctx, "Осматриваюсь.", mode)
    return json.loads(request.messages[0].content[0].text)


def knowledge(ctx, mode="explore", cfg=None):
    return state(ctx, mode, cfg).get("knowledge")


def capped(limit):
    cfg = app_cfg()
    cfg.master.knowledge_max = limit
    return cfg


def plan(npc_ids=(), location_ids=()):
    return SimpleNamespace(npc_ids=list(npc_ids), location_ids=list(location_ids))


@pytest.fixture
def ctx(registry, cfg):
    return make_ctx(registry, cfg)


def fill(ctx, *entries):
    ctx.hero.knowledge += list(entries)


def in_combat(ctx, *monsters):
    parts = [Participant(ref="hero", side="heroes", group_id="h")]
    parts += [
        Participant(ref=f"e{i}", side="enemies", group_id="e", monster_id=m)
        for i, m in enumerate(monsters)
    ]
    ctx.bundle.session.active_combat = CombatState(
        id="c1", zones=[], participants=parts, groups={}
    )


def bestiary(ref="goblin_warrior", text="Бой: Воин-гоблин — победа"):
    return entry(text, kind="creature", ref=ref, source="seen")


# наличие блока

def test_no_key_for_empty_journal(ctx):
    assert "knowledge" not in state(ctx)


def test_scene_npc_entry_is_shown(ctx):
    fill(ctx, entry("Хранит ключ от склепа"))
    assert knowledge(ctx) == {"npc": {"grakh": ["Хранит ключ от склепа (rumor)"]}}


def test_key_absent_when_nothing_selected(ctx):
    fill(ctx, entry("далеко", ref="aldric"))
    assert "knowledge" not in state(ctx)


def test_zero_max_turns_block_off(ctx):
    fill(ctx, entry("Хранит ключ"))
    assert "knowledge" not in state(ctx, cfg=capped(0))


def test_default_max_is_30():
    assert app_cfg().master.knowledge_max == 30


def test_negative_max_is_rejected():
    from pydantic import ValidationError

    from ai_dm.config.app import MasterConfig

    data = app_cfg().master.model_dump()
    data["knowledge_max"] = -1
    with pytest.raises(ValidationError):
        MasterConfig.model_validate(data)


# формат строк

def test_told_line_has_teller(ctx):
    fill(ctx, entry("Знает про подвал", source="told", from_ref="mira"))
    assert knowledge(ctx)["npc"]["grakh"] == ["Знает про подвал (told: mira)"]


def test_lines_of_one_entity_keep_journal_order(ctx):
    fill(ctx, entry("первое", at_s=5), entry("второе", at_s=1))
    assert knowledge(ctx)["npc"]["grakh"] == ["первое (rumor)", "второе (rumor)"]


def test_key_order_in_block_is_stable(ctx):
    fill(ctx, entry("с", kind="situation", ref="plague"), entry("н"))
    assert list(knowledge(ctx)) == ["npc", "situation"]


# отбор по сцене (knowledge_refs напрямую)

def refs(ctx, scene_ids=(), npc_ids=(), location_ids=()):
    scene_npcs = [{"id": i} for i in scene_ids]
    return PromptBuilder(app_cfg()).knowledge_refs(ctx, plan(npc_ids, location_ids), scene_npcs)


def test_refs_npc_are_scene_and_known(ctx):
    assert refs(ctx, ["a"], ["b"])["npc"] == {"a", "b"}


def test_refs_npc_empty_without_scene_and_known(ctx):
    assert refs(ctx)["npc"] == set()


def test_refs_location_is_hero_place_and_plan(ctx):
    assert refs(ctx, location_ids=["forest"])["location"] == {"vale", "forest"}


def test_refs_location_hero_place_always_there(ctx):
    assert refs(ctx)["location"] == {"vale"}


def test_refs_god_from_hero_favor(ctx):
    ctx.hero.favor = {"selune": 2, "morrah": -1}
    assert refs(ctx)["god"] == {"selune", "morrah"}


def test_refs_god_empty_without_favor(ctx):
    assert refs(ctx)["god"] == set()


def test_refs_faction_and_situation_take_all(ctx):
    got = refs(ctx)
    assert got["faction"] is None
    assert got["situation"] is None


def test_refs_no_creature_in_explore(ctx):
    assert "creature" not in refs(ctx)


def test_refs_no_creature_in_explore_even_in_combat_state(ctx):
    in_combat(ctx, "goblin_warrior")
    assert "creature" not in refs(ctx)


@pytest.mark.parametrize("mode", ["combat_classify", "combat_narrate"])
def test_refs_creature_from_participants_in_combat_modes(mode, registry, cfg):
    ctx = make_ctx(registry, cfg, mode=mode)
    in_combat(ctx, "goblin_warrior", "black_bear")
    assert refs(ctx)["creature"] == {"goblin_warrior", "black_bear"}


def test_refs_creature_skips_participants_without_monster_id(registry, cfg):
    ctx = make_ctx(registry, cfg, mode="combat_classify")
    in_combat(ctx, "goblin_warrior")
    assert refs(ctx)["creature"] == {"goblin_warrior"}


def test_refs_creature_absent_in_combat_mode_without_combat(registry, cfg):
    ctx = make_ctx(registry, cfg, mode="combat_narrate")
    assert "creature" not in refs(ctx)


def test_refs_npc_choice_mode_has_no_creature(registry, cfg):
    ctx = make_ctx(registry, cfg, mode="npc_choice", npc_options=["a"])
    in_combat(ctx, "goblin_warrior")
    assert "creature" not in refs(ctx)


# отбор в собранном состоянии

def test_other_location_entry_is_not_shown(ctx):
    fill(ctx, entry("Заброшен", kind="location", ref="goblin_den"))
    assert "knowledge" not in state(ctx)


def test_hero_location_entry_is_shown(ctx):
    fill(ctx, entry("Рынок по средам", kind="location", ref="vale"))
    assert knowledge(ctx) == {"location": {"vale": ["Рынок по средам (rumor)"]}}


def test_planned_neighbour_location_entry_is_shown(ctx):
    fill(ctx, entry("Старая чаща", kind="location", ref="forest"))
    assert "forest" in knowledge(ctx)["location"]


def test_god_entry_shown_only_with_favor(ctx):
    fill(ctx, entry("Селунэ: доволен", kind="god", ref="selune", source="deduced"))
    assert "knowledge" not in state(ctx)
    ctx.hero.favor["selune"] = 1
    assert knowledge(ctx) == {"god": {"selune": ["Селунэ: доволен (deduced)"]}}


def test_faction_and_situation_entries_always_shown(ctx):
    fill(
        ctx,
        entry("Скупает долги", kind="faction", ref="guild"),
        entry("В деревне мор", kind="situation", ref="plague"),
    )
    got = knowledge(ctx)
    assert got["faction"] == {"guild": ["Скупает долги (rumor)"]}
    assert got["situation"] == {"plague": ["В деревне мор (rumor)"]}


def test_creature_entry_not_in_explore(ctx):
    fill(ctx, bestiary())
    assert "knowledge" not in state(ctx)


def test_creature_entry_in_combat_for_participant(registry, cfg):
    ctx = make_ctx(registry, cfg, mode="combat_narrate")
    in_combat(ctx, "goblin_warrior")
    fill(ctx, bestiary())
    assert knowledge(ctx, "combat_narrate")["creature"] == {
        "goblin_warrior": ["Бой: Воин-гоблин — победа (seen)"]
    }


def test_creature_entry_in_combat_skipped_for_non_participant(registry, cfg):
    ctx = make_ctx(registry, cfg, mode="combat_classify")
    in_combat(ctx, "goblin_warrior")
    fill(ctx, bestiary("black_bear", "Бой: Медведь — победа"))
    assert "knowledge" not in state(ctx, "combat_classify")


# записи движка

def test_meeting_entry_is_hidden(ctx):
    fill(ctx, entry("Знакомство: Гракх", source="seen"))
    assert "knowledge" not in state(ctx)


def test_visited_entry_is_hidden(ctx):
    fill(ctx, entry("Место: Вейл", kind="location", ref="vale", source="seen"))
    assert "knowledge" not in state(ctx)


def test_hidden_engine_entry_does_not_hide_narrator_entry_of_same_entity(ctx):
    fill(ctx, entry("Знакомство: Гракх", source="seen"), entry("Хранит ключ"))
    assert knowledge(ctx)["npc"]["grakh"] == ["Хранит ключ (rumor)"]


def test_secret_entry_is_shown(ctx):
    fill(ctx, entry("сестра жива", source="deduced"))
    assert knowledge(ctx)["npc"]["grakh"] == ["сестра жива (deduced)"]


def test_narrator_seen_entry_with_ordinary_text_is_shown(ctx):
    fill(ctx, entry("Шрам через всё лицо", source="seen"))
    assert knowledge(ctx)["npc"]["grakh"] == ["Шрам через всё лицо (seen)"]


# потолок

def numbered(n, ref="grakh"):
    return [entry(f"факт {i}", ref=ref, at_s=i) for i in range(n)]


def test_cap_keeps_newest_by_time(ctx):
    fill(ctx, *numbered(5))
    got = knowledge(ctx, cfg=capped(2))
    assert got["npc"]["grakh"] == ["факт 3 (rumor)", "факт 4 (rumor)"]


def test_cap_counts_all_selected_entries(ctx):
    fill(ctx, *numbered(3), entry("мор", kind="situation", ref="plague", at_s=100))
    got = knowledge(ctx, cfg=capped(2))
    assert sum(len(lines) for by_ref in got.values() for lines in by_ref.values()) == 2
    assert got["situation"] == {"plague": ["мор (rumor)"]}


def test_cap_ignores_unselected_entries(ctx):
    fill(ctx, entry("лишняя", ref="aldric", at_s=999), entry("нужная", at_s=1))
    assert knowledge(ctx, cfg=capped(1))["npc"] == {"grakh": ["нужная (rumor)"]}


def test_under_cap_everything_is_shown(ctx):
    fill(ctx, *numbered(5))
    assert len(knowledge(ctx)["npc"]["grakh"]) == 5


# побочных эффектов нет

def test_building_prompt_does_not_change_journal(ctx):
    fill(ctx, entry("Хранит ключ"))
    before = ctx.bundle.model_dump_json()
    state(ctx)
    assert ctx.bundle.model_dump_json() == before


def test_block_is_in_user_message_not_in_system(ctx):
    fill(ctx, entry("УникальнаяЗаметка123"))
    request = PromptBuilder(app_cfg()).build(ctx, "Осматриваюсь.", "explore")
    assert all("УникальнаяЗаметка123" not in block.text for block in request.system)
