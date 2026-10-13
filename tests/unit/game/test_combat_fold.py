# Р1 «Память боя» (R1-PLAN п.2): чистые функции свёртки ходов боя в game/combat_fold.py.
# Записи -- TurnRecord руками (как в test_offer_stale.py), состояние боя -- CombatState руками,
# бандл -- make_bundle. Решения проектировщика: Q1а старт по всему recent_turns, не найден --
# записи текущей сцены; Q2а потери из состояния; Q3а префикс «Свёрнуты ходы N–M»; Q4а при
# ended_by_master стоящие на ногах -- «сдался».
import pytest
from game_kit import make_bundle

from ai_dm.combat.end import OUTCOME_WORDS
from ai_dm.game.combat_fold import (
    defeated_text,
    enemy_names,
    fight_start,
    fight_tail,
    fold_fight,
    fold_text,
    losses_text,
    trophies_text,
)
from ai_dm.game.scene import hero_of
from ai_dm.state.combat import CombatState, Group, Participant
from ai_dm.state.hero import InventoryEntry
from ai_dm.state.scene import TurnRecord
from ai_dm.state.session import LastCombat


def rec(seq, requests=(), scene="scene_1", text=None, rolls=()):
    return TurnRecord(
        turn_seq=seq, at_s=seq * 10, player_input=f"ввод {seq}",
        narration=text or f"рассказ {seq}", requests=list(requests), rolls=list(rolls),
        scene_id=scene,
    )


def part(ref, side="enemies", name="", status="active", monster_id="goblin_warrior"):
    return Participant(
        ref=ref, side=side, group_id="g", name=name, status=status,
        monster_id=None if side == "heroes" else monster_id,
    )


def make_state(participants, outcome="victory", rounds=3):
    return CombatState(
        id="combat_1", zones=[], participants=participants,
        groups={"g": Group(leader_id=participants[0].ref)}, round=rounds, outcome=outcome,
    )


def hero_part():
    return part("hero", side="heroes", name="Арн")


def goblins(status="active"):
    return [
        part("g1", name="Воин-гоблин", status=status),
        part("g2", name="Воин-гоблин", status=status),
    ]


def hero_for(registry):
    return hero_of(make_bundle(registry))


def text_of(registry, state, last_combat=None, first=2, last=5):
    bundle = make_bundle(registry)
    bundle.session.last_combat = last_combat
    return fold_text(bundle, state, registry, [rec(first), rec(last)])


# fight_start

def test_fight_start_none_without_start_combat():
    assert fight_start([rec(1), rec(2, ["skill_check"])]) is None


def test_fight_start_empty_list():
    assert fight_start([]) is None


def test_fight_start_single():
    assert fight_start([rec(1), rec(2, ["start_combat"]), rec(3)]) == 1


def test_fight_start_takes_the_last_of_two():
    turns = [rec(1, ["start_combat"]), rec(2), rec(3, ["start_combat"]), rec(4)]
    assert fight_start(turns) == 2


def test_fight_start_counts_among_other_requests():
    assert fight_start([rec(1), rec(2, ["skill_check", "start_combat"])]) == 1


def test_fight_start_last_record_counts():
    assert fight_start([rec(1), rec(2, ["start_combat"])]) == 1


def test_fight_start_first_record_counts():
    assert fight_start([rec(1, ["start_combat"]), rec(2)]) == 0


# fight_tail

def test_fight_tail_is_after_start():
    turns = [rec(1), rec(2, ["start_combat"]), rec(3), rec(4)]
    assert fight_tail(turns, "scene_1") == 2


def test_fight_tail_without_start_is_first_record_of_current_scene():
    turns = [rec(1, scene="s1"), rec(2, scene="s1"), rec(3, scene="s2"), rec(4, scene="s2")]
    assert fight_tail(turns, "s2") == 2


def test_fight_tail_without_start_and_scene_records_is_len():
    turns = [rec(1, scene="s1"), rec(2, scene="s1")]
    assert fight_tail(turns, "s2") == 2


def test_fight_tail_empty_list():
    assert fight_tail([], "s1") == 0


def test_fight_tail_start_in_previous_scene_folds_records_after_it():
    turns = [rec(1, ["start_combat"], scene="s1"), rec(2, scene="s1"),
             rec(3, scene="s2"), rec(4, scene="s2")]
    assert fight_tail(turns, "s2") == 1


def test_fight_tail_start_wins_over_scene_search():
    turns = [rec(1, scene="s2"), rec(2, ["start_combat"], scene="s2"), rec(3, scene="s2")]
    assert fight_tail(turns, "s2") == 2


def test_fight_tail_picks_first_of_scene_not_last():
    turns = [rec(1, scene="s1"), rec(2, scene="s2"), rec(3, scene="s1"), rec(4, scene="s2")]
    assert fight_tail(turns, "s2") == 1


# enemy_names

def test_enemy_names_numbers_same_names(registry):
    state = make_state([hero_part(), *goblins()])
    assert enemy_names(state, hero_for(registry)) == ["Воин-гоблин 1", "Воин-гоблин 2"]


def test_enemy_names_unique_without_number(registry):
    state = make_state([hero_part(), part("g1", name="Воин-гоблин"), part("b", name="Гракх")])
    assert enemy_names(state, hero_for(registry)) == ["Воин-гоблин", "Гракх"]


def test_enemy_names_empty_name_is_ref(registry):
    state = make_state([hero_part(), part("g1", name="")])
    assert enemy_names(state, hero_for(registry)) == ["g1"]


def test_enemy_names_skip_heroes_and_companions(registry):
    state = make_state([
        hero_part(), part("ally", side="heroes", name="Лия"), part("g1", name="Волк"),
    ])
    assert enemy_names(state, hero_for(registry)) == ["Волк"]


# defeated_text

@pytest.mark.parametrize("status,word", [
    ("dead", "убит"), ("down", "без сознания"), ("fled", "бежал"), ("surrendered", "сдался"),
])
def test_defeated_text_word_per_status(registry, status, word):
    state = make_state([hero_part(), part("g1", name="Волк", status=status)])
    text = defeated_text(state, hero_for(registry))
    assert "Волк" in text
    assert word in text


def test_defeated_text_active_enemy_not_mentioned(registry):
    state = make_state([hero_part(), part("g1", name="Волк", status="active")], outcome="fled")
    assert "Волк" not in defeated_text(state, hero_for(registry))


def test_defeated_text_ended_by_master_active_are_surrendered(registry):
    state = make_state(
        [hero_part(), part("g1", name="Волк", status="active")], outcome="ended_by_master"
    )
    text = defeated_text(state, hero_for(registry))
    assert "Волк" in text
    assert "сдался" in text


def test_defeated_text_ended_by_master_keeps_real_statuses(registry):
    state = make_state(
        [hero_part(), part("g1", name="Волк", status="dead")], outcome="ended_by_master"
    )
    text = defeated_text(state, hero_for(registry))
    assert "убит" in text
    assert "сдался" not in text


def test_defeated_text_numbers_same_names(registry):
    state = make_state([hero_part(), *goblins("dead")])
    text = defeated_text(state, hero_for(registry))
    assert text == "Воин-гоблин 1 — убит, Воин-гоблин 2 — убит"


def test_defeated_text_ignores_heroes_side(registry):
    state = make_state([hero_part(), part("ally", side="heroes", name="Лия", status="dead")])
    assert "Лия" not in defeated_text(state, hero_for(registry))


def test_defeated_text_nobody_down_is_empty(registry):
    state = make_state([hero_part(), part("g1", name="Волк")], outcome="hero_dead")
    assert defeated_text(state, hero_for(registry)) == ""


# losses_text

def test_losses_none_for_unhurt_hero(registry):
    state = make_state([hero_part(), *goblins("dead")])
    assert losses_text(state, hero_for(registry)) == ""


def test_losses_hurt_hero_shows_hp_from_creature(registry):
    hero = hero_for(registry)
    hero.creature.hp_current = 7
    state = make_state([hero_part(), *goblins("dead")])
    text = losses_text(state, hero)
    assert f"7/{hero.creature.hp_max}" in text
    assert "HP" in text
    assert hero.name in text


def test_losses_hero_at_zero_hp(registry):
    hero = hero_for(registry)
    hero.creature.hp_current = 0
    text = losses_text(make_state([hero_part(), *goblins()], "hero_dead"), hero)
    assert f"0/{hero.creature.hp_max}" in text


def test_losses_down_companion(registry):
    state = make_state([hero_part(), part("ally", side="heroes", name="Лия", status="down")])
    assert losses_text(state, hero_for(registry)) == "Лия — без сознания"


def test_losses_dead_companion(registry):
    state = make_state([hero_part(), part("ally", side="heroes", name="Лия", status="dead")])
    assert losses_text(state, hero_for(registry)) == "Лия — погиб"


def test_losses_active_companion_not_listed(registry):
    state = make_state([hero_part(), part("ally", side="heroes", name="Лия")])
    assert losses_text(state, hero_for(registry)) == ""


def test_losses_fled_companion_not_listed(registry):
    state = make_state([hero_part(), part("ally", side="heroes", name="Лия", status="fled")])
    assert losses_text(state, hero_for(registry)) == ""


def test_losses_enemy_down_is_not_a_loss(registry):
    state = make_state([hero_part(), part("g1", name="Волк", status="dead")])
    assert "Волк" not in losses_text(state, hero_for(registry))


def test_losses_hero_hp_and_companion_together(registry):
    hero = hero_for(registry)
    hero.creature.hp_current = 5
    state = make_state([hero_part(), part("ally", side="heroes", name="Лия", status="dead")])
    assert losses_text(state, hero) == f"Арн HP 5/{hero.creature.hp_max}, Лия — погиб"


# trophies_text

def test_trophies_none_without_last_combat(registry):
    assert trophies_text(None, registry) == ""


def test_trophies_empty_gear(registry):
    assert trophies_text(LastCombat(), registry) == ""


def test_trophies_single_has_no_multiplier(registry):
    last = LastCombat(gear=[InventoryEntry(item_id="dagger", qty=1, cost_cp=200)])
    text = trophies_text(last, registry)
    assert text == registry.get("weapon", "dagger").name
    assert "×" not in text


def test_trophies_quantity_over_one_has_multiplier(registry):
    last = LastCombat(gear=[InventoryEntry(item_id="dagger", qty=2, cost_cp=200)])
    assert trophies_text(last, registry) == f"{registry.get('weapon', 'dagger').name} ×2"


def test_trophies_quality_is_a_prefix(registry):
    last = LastCombat(gear=[InventoryEntry(item_id="dagger", qty=1, cost_cp=50, quality="junk")])
    text = trophies_text(last, registry)
    assert text.startswith("Ржавый")
    assert registry.get("weapon", "dagger").name.lower() in text


def test_trophies_lists_all_entries(registry):
    last = LastCombat(gear=[
        InventoryEntry(item_id="dagger", cost_cp=200),
        InventoryEntry(item_id="longsword", cost_cp=1500),
    ])
    names = [registry.get("weapon", i).name for i in ("dagger", "longsword")]
    assert trophies_text(last, registry) == ", ".join(names)


# fold_text

def test_fold_text_has_range_enemies_outcome_and_rounds(registry):
    state = make_state([hero_part(), *goblins("dead")], "victory", rounds=4)
    text = text_of(registry, state, first=3, last=7)
    assert text.startswith("Свёрнуты ходы 3–7")
    assert "Бой: Воин-гоблин 1, Воин-гоблин 2 — победа, раундов: 4" in text
    assert OUTCOME_WORDS["victory"] in text
    assert "раундов: 4" in text


def test_fold_text_exact_text_with_every_part(registry):
    state = make_state([hero_part(), *goblins("dead")], "victory", rounds=4)
    last = LastCombat(gear=[InventoryEntry(item_id="dagger", qty=2, cost_cp=200)])
    bundle = make_bundle(registry)
    bundle.heroes[0].creature.hp_current = 9
    bundle.session.last_combat = last
    text = fold_text(bundle, state, registry, [rec(3), rec(7)])
    dagger = registry.get("weapon", "dagger").name
    assert text == (
        "Свёрнуты ходы 3–7. Бой: Воин-гоблин 1, Воин-гоблин 2 — "
        f"{OUTCOME_WORDS['victory']}, раундов: 4; "
        "побеждены: Воин-гоблин 1 — убит, Воин-гоблин 2 — убит; "
        f"потери: Арн HP 9/{bundle.heroes[0].creature.hp_max}; "
        f"трофеи: {dagger} ×2"
    )


@pytest.mark.parametrize("outcome", sorted(OUTCOME_WORDS))
def test_fold_text_outcome_word_for_each_outcome(registry, outcome):
    state = make_state([hero_part(), *goblins("dead")], outcome)
    assert OUTCOME_WORDS[outcome] in text_of(registry, state)


def test_fold_text_names_every_enemy_even_active(registry):
    state = make_state([hero_part(), part("g1", name="Волк"), part("g2", name="Гракх")],
                       "hero_dead")
    text = text_of(registry, state)
    assert "Волк" in text
    assert "Гракх" in text


def test_fold_text_defeated_part(registry):
    state = make_state([hero_part(), *goblins("dead")])
    assert "побеждены" in text_of(registry, state)


def test_fold_text_no_defeated_part_when_nobody_down(registry):
    state = make_state([hero_part(), *goblins()], "hero_dead")
    assert "побеждены" not in text_of(registry, state)


def test_fold_text_ended_by_master_names_surrendered(registry):
    state = make_state([hero_part(), *goblins()], "ended_by_master")
    text = text_of(registry, state)
    assert "завершён мастером" in text
    assert "сдался" in text


def test_fold_text_no_trophies_without_last_combat(registry):
    state = make_state([hero_part(), *goblins("dead")])
    assert "трофеи" not in text_of(registry, state, None)


def test_fold_text_no_trophies_for_empty_gear(registry):
    state = make_state([hero_part(), *goblins("dead")])
    assert "трофеи" not in text_of(registry, state, LastCombat(defeated=["goblin_warrior"]))


def test_fold_text_trophies_with_quantity_and_quality(registry):
    state = make_state([hero_part(), *goblins("dead")])
    last = LastCombat(gear=[
        InventoryEntry(item_id="dagger", qty=2, cost_cp=50, quality="worn"),
    ])
    text = text_of(registry, state, last)
    assert "трофеи" in text
    assert "Поношенный" in text
    assert "×2" in text


def test_fold_text_unhurt_hero_has_no_hp(registry):
    state = make_state([hero_part(), *goblins("dead")])
    text = text_of(registry, state)
    assert "HP" not in text
    assert "потери" not in text


def test_fold_text_hurt_hero_has_hp_of_creature(registry):
    bundle = make_bundle(registry)
    hero = hero_of(bundle)
    hero.creature.hp_current = 9
    state = make_state([hero_part(), *goblins("dead")])
    text = fold_text(bundle, state, registry, [rec(2), rec(5)])
    assert "потери" in text
    assert f"HP 9/{hero.creature.hp_max}" in text


def test_fold_text_down_companion_is_a_loss_active_is_not(registry):
    state = make_state([
        hero_part(), part("a1", side="heroes", name="Лия", status="down"),
        part("a2", side="heroes", name="Борин"), *goblins("dead"),
    ])
    text = text_of(registry, state)
    assert "Лия" in text
    assert "Борин" not in text


def test_fold_text_parts_are_separated_by_semicolon_without_empty_ones(registry):
    state = make_state([hero_part(), *goblins("dead")])
    text = text_of(registry, state)
    assert "; ;" not in text
    assert not text.endswith("; ")
    assert not text.endswith(";")
    assert "; побеждены" in text


def test_fold_text_is_deterministic(registry):
    state = make_state([hero_part(), *goblins("dead")])
    assert text_of(registry, state) == text_of(registry, state)


# fold_fight

def bundle_with(registry, turns, scene_id="scene_1", last_combat=None):
    bundle = make_bundle(registry)
    bundle.memory.recent_turns = list(turns)
    bundle.session.current_scene.id = scene_id
    bundle.session.last_combat = last_combat
    return bundle


def finished_state():
    return make_state([hero_part(), *goblins("dead")])


def fight(n_mid, extra=()):
    # [до боя, старт, n_mid промежуточных]
    return [rec(1), rec(2, ["start_combat"]), *[rec(3 + i) for i in range(n_mid)], *extra]


def test_fold_fight_zero_middle_turns_changes_nothing(registry):
    bundle = bundle_with(registry, fight(0))
    before = list(bundle.memory.recent_turns)
    assert fold_fight(bundle, finished_state(), registry) is False
    assert bundle.memory.recent_turns == before


def test_fold_fight_one_middle_turn_changes_nothing(registry):
    bundle = bundle_with(registry, fight(1))
    before = list(bundle.memory.recent_turns)
    assert fold_fight(bundle, finished_state(), registry) is False
    assert bundle.memory.recent_turns == before


def test_fold_fight_two_middle_turns_make_one_record(registry):
    bundle = bundle_with(registry, fight(2))
    assert fold_fight(bundle, finished_state(), registry) is True
    turns = bundle.memory.recent_turns
    assert len(turns) == 3
    assert turns[0].turn_seq == 1
    assert "start_combat" in turns[1].requests


def test_fold_fight_keeps_start_and_earlier_records_verbatim(registry):
    original = fight(3)
    bundle = bundle_with(registry, [r.model_copy(deep=True) for r in original])
    fold_fight(bundle, finished_state(), registry)
    assert bundle.memory.recent_turns[:2] == original[:2]


def test_fold_fight_record_fields_come_from_the_last_folded(registry):
    turns = fight(3)
    bundle = bundle_with(registry, turns)
    fold_fight(bundle, finished_state(), registry)
    record = bundle.memory.recent_turns[-1]
    assert record.turn_seq == turns[-1].turn_seq
    assert record.at_s == turns[-1].at_s
    assert record.scene_id == turns[-1].scene_id
    assert record.player_input == ""
    assert record.requests == []
    assert record.rolls == []


def test_fold_fight_record_text_is_fold_text_with_range(registry):
    turns = fight(3)
    bundle = bundle_with(registry, turns)
    state = finished_state()
    fold_fight(bundle, state, registry)
    expected = fold_text(bundle, state, registry, turns[2:])
    assert bundle.memory.recent_turns[-1].narration == expected
    assert "Свёрнуты ходы 3–5" in expected


def test_fold_fight_uses_last_combat_for_trophies(registry):
    last = LastCombat(gear=[InventoryEntry(item_id="dagger", qty=2, cost_cp=200)])
    bundle = bundle_with(registry, fight(2), last_combat=last)
    fold_fight(bundle, finished_state(), registry)
    assert "×2" in bundle.memory.recent_turns[-1].narration


def test_fold_fight_without_last_combat_has_no_trophies(registry):
    bundle = bundle_with(registry, fight(2), last_combat=None)
    fold_fight(bundle, finished_state(), registry)
    assert "трофеи" not in bundle.memory.recent_turns[-1].narration


def test_fold_fight_second_call_does_nothing(registry):
    bundle = bundle_with(registry, fight(3))
    state = finished_state()
    assert fold_fight(bundle, state, registry) is True
    once = [r.model_copy(deep=True) for r in bundle.memory.recent_turns]
    assert fold_fight(bundle, state, registry) is False
    assert bundle.memory.recent_turns == once


def test_fold_fight_is_deterministic(registry):
    first = bundle_with(registry, fight(3))
    second = bundle_with(registry, fight(3))
    fold_fight(first, finished_state(), registry)
    fold_fight(second, finished_state(), registry)
    assert first.memory.recent_turns == second.memory.recent_turns


def test_fold_fight_old_fight_is_not_touched(registry):
    old = [rec(1, ["start_combat"]), rec(2), rec(3), rec(4), rec(5, ["start_combat"]),
           rec(6), rec(7)]
    bundle = bundle_with(registry, old)
    fold_fight(bundle, finished_state(), registry)
    assert bundle.memory.recent_turns[:5] == old[:5]
    assert len(bundle.memory.recent_turns) == 6


def test_fold_fight_start_in_previous_scene_folds_only_after_start(registry):
    turns = [rec(1, scene="s1"), rec(2, ["start_combat"], scene="s1"), rec(3, scene="s1"),
             rec(4, scene="s2"), rec(5, scene="s2")]
    bundle = bundle_with(registry, turns, scene_id="s2")
    assert fold_fight(bundle, finished_state(), registry) is True
    result = bundle.memory.recent_turns
    assert [r.turn_seq for r in result] == [1, 2, 5]
    assert result[1].scene_id == "s1"
    assert result[2].scene_id == "s2"
    assert "Свёрнуты ходы 3–5" in result[2].narration


def test_fold_fight_without_start_folds_current_scene_records(registry):
    turns = [rec(1, scene="s1"), rec(2, scene="s1"), rec(3, scene="s2"), rec(4, scene="s2"),
             rec(5, scene="s2")]
    bundle = bundle_with(registry, turns, scene_id="s2")
    assert fold_fight(bundle, finished_state(), registry) is True
    result = bundle.memory.recent_turns
    assert [r.turn_seq for r in result] == [1, 2, 5]
    assert "Свёрнуты ходы 3–5" in result[2].narration


def test_fold_fight_without_start_and_one_scene_record_changes_nothing(registry):
    turns = [rec(1, scene="s1"), rec(2, scene="s1"), rec(3, scene="s2")]
    bundle = bundle_with(registry, turns, scene_id="s2")
    assert fold_fight(bundle, finished_state(), registry) is False
    assert len(bundle.memory.recent_turns) == 3


def test_fold_fight_empty_memory(registry):
    bundle = bundle_with(registry, [])
    assert fold_fight(bundle, finished_state(), registry) is False
    assert bundle.memory.recent_turns == []


def test_fold_fight_does_not_touch_the_state(registry):
    bundle = bundle_with(registry, fight(2))
    state = finished_state()
    before = state.model_dump_json()
    fold_fight(bundle, state, registry)
    assert state.model_dump_json() == before
