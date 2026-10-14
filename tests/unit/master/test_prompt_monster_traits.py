# Партия К7д, п. 4.2 (Q3а): черты монстров боя в состоянии для рассказчика (docs/K7D-PLAN.md).
#   prompt.monster_trait_notes(participants, registry) -> list[str]: по участникам боя с monster_id
#     (мёртвые и герои пропускаются) строки «<имя монстра>: <имя черты> — <описание черты>» по
#     каждой черте монстра, без повторов, каждая не длиннее 100 символов (длиннее -- обрезается с
#     «…» на конце).
#   combat_data: в боевом блоке combat["monster_traits"] -- этот список, ключ есть только если он не
#     пуст; без активного боя блока combat нет вовсе. В system-блоках черт нет (префикс стабилен).
import json

from master_kit import app_cfg, combat_request, make_ctx
from protocol_kit import goblin

from ai_dm.content.models.monsters import Monster
from ai_dm.master.prompt import PromptBuilder, monster_trait_notes
from ai_dm.protocol.apply import apply
from ai_dm.state.combat import Participant

BASE = {
    "ac": 8, "hp": 15, "cr": "1/4", "name": "Зомби",
    "abilities": {"str": 13, "dex": 6, "con": 16, "int": 3, "wis": 6, "cha": 5},
}


def reg_with(registry, **traits_by_id):
    items = [
        Monster.model_validate({**BASE, "id": key, "traits": traits})
        for key, traits in traits_by_id.items()
    ]
    return registry.with_items({"monster": items})


def part(ref, monster_id, status="active"):
    return Participant(
        ref=ref, side="enemies", group_id="g", zone_id="hall", monster_id=monster_id, status=status
    )


def combat_of(registry, cfg, monster_id, count=2, mode="combat_narrate"):
    ctx = make_ctx(registry, cfg, mode=mode)
    enemies = [
        {"ref": f"g{i}", "monster_id": monster_id, "zone": "hall", "group": "goblins"}
        for i in range(1, count + 1)
    ]
    apply(ctx, combat_request(enemies=enemies))
    return ctx


def state_combat(ctx, mode="combat_narrate"):
    request = PromptBuilder(app_cfg()).build(ctx, "Бью.", mode)
    return json.loads(request.messages[0].content[0].text)["combat"]


# monster_trait_notes

def test_note_names_the_monster_the_trait_and_its_text(registry):
    reg = reg_with(registry, zomb=["undead_fortitude"])
    feature = reg.get("feature", "undead_fortitude")
    [line] = monster_trait_notes([part("z1", "zomb")], reg)
    assert line == f"Зомби: {feature.name} — {feature.description}"[:99] + "…"


def test_note_is_not_longer_than_100(registry):
    reg = reg_with(registry, zomb=["undead_fortitude", "pack_tactics"])
    notes = monster_trait_notes([part("z1", "zomb")], reg)
    assert len(notes) == 2 and all(len(line) <= 100 for line in notes)


def test_short_description_is_kept_whole(registry):
    reg = reg_with(registry, zomb=["nimble_escape"])
    feature = reg.get("feature", "nimble_escape")
    assert monster_trait_notes([part("z1", "zomb")], reg) == [
        f"Зомби: {feature.name} — {feature.description}"
    ]


def test_note_of_exactly_100_chars_is_not_clipped(registry):
    reg = reg_with(registry, zomb=["nimble_escape"])
    feature = reg.get("feature", "nimble_escape")
    exact = f"Зомби: {feature.name} — "
    short = reg.with_items({"feature": [feature.model_copy(
        update={"description": "я" * (100 - len(exact))}
    )]})
    [line] = monster_trait_notes([part("z1", "zomb")], short)
    assert len(line) == 100 and not line.endswith("…")


def test_duplicate_lines_are_collapsed(registry):
    reg = reg_with(registry, zomb=["nimble_escape"])
    notes = monster_trait_notes([part("z1", "zomb"), part("z2", "zomb")], reg)
    assert len(notes) == 1


def test_dead_participants_are_skipped(registry):
    reg = reg_with(registry, zomb=["nimble_escape"])
    assert monster_trait_notes([part("z1", "zomb", "dead")], reg) == []


def test_downed_participants_still_count(registry):
    reg = reg_with(registry, zomb=["nimble_escape"])
    assert len(monster_trait_notes([part("z1", "zomb", "down")], reg)) == 1


def test_heroes_are_skipped(registry):
    hero = Participant(ref="hero", side="heroes", group_id="party", zone_id="hall")
    assert monster_trait_notes([hero], registry) == []


def test_monster_without_traits_gives_nothing(registry):
    reg = reg_with(registry, plain=[])
    assert monster_trait_notes([part("z1", "plain")], reg) == []


def test_different_monsters_each_give_their_lines(registry):
    reg = reg_with(registry, one=["nimble_escape"], two=["pack_tactics"])
    notes = monster_trait_notes([part("a", "one"), part("b", "two")], reg)
    assert [line.split(": ")[1].split(" — ")[0] for line in notes] == [
        reg.get("feature", "nimble_escape").name, reg.get("feature", "pack_tactics").name,
    ]


# combat_data

def test_combat_block_has_monster_traits(registry, cfg):
    reg = reg_with(registry, zomb=["nimble_escape"])
    combat = state_combat(combat_of(reg, cfg, "zomb"))
    assert len(combat["monster_traits"]) == 1
    assert combat["monster_traits"][0].startswith("Зомби: ")


def test_traits_are_in_the_classify_state_too(registry, cfg):
    reg = reg_with(registry, zomb=["nimble_escape"])
    combat = state_combat(combat_of(reg, cfg, "zomb", mode="combat_classify"), "combat_classify")
    assert "monster_traits" in combat


def test_no_key_when_nobody_has_traits(registry, cfg):
    reg = reg_with(registry, plain=[])
    assert "monster_traits" not in state_combat(combat_of(reg, cfg, "plain"))


def test_no_combat_block_outside_a_fight(registry, cfg):
    request = PromptBuilder(app_cfg()).build(make_ctx(registry, cfg), "Иду.", "explore")
    assert json.loads(request.messages[0].content[0].text)["combat"] is None


def test_system_blocks_do_not_carry_the_trait_text(registry, cfg):
    reg = reg_with(registry, zomb=["nimble_escape"])
    request = PromptBuilder(app_cfg()).build(combat_of(reg, cfg, "zomb"), "Бью.", "combat_narrate")
    system = "\n".join(block.text for block in request.system)
    assert reg.get("feature", "nimble_escape").description not in system


def test_goblin_fixture_has_traits_in_the_notes(registry, cfg):
    # goblin_warrior: Проворное бегство -- черта есть, значит и строка есть
    ctx = make_ctx(registry, cfg, mode="combat_narrate")
    apply(ctx, combat_request(enemies=[goblin("g1")]))
    assert state_combat(ctx)["monster_traits"]


def test_notes_do_not_leak_engine_remarks(registry):
    # «Движок: ...» -- пометка для разработчика, рассказчику не нужна
    reg = reg_with(registry, zomb=["undead_fortitude", "pack_tactics", "nimble_escape"])
    assert all("Движок" not in line for line in monster_trait_notes([part("z1", "zomb")], reg))


def test_real_srd_monsters_notes_have_no_engine_remarks(registry):
    from ai_dm.state.combat import Participant as P

    ids = [m.id for m in registry.all("monster")]
    notes = monster_trait_notes(
        [P(ref=f"m{i}", side="enemies", group_id="g", zone_id="z", monster_id=m)
         for i, m in enumerate(ids)], registry,
    )
    assert notes and all("Движок" not in line for line in notes)
