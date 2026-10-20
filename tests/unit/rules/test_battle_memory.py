# Ж8 П1 (docs/plan-zh8.md): общий бой пишет движок каждому спутнику героя (kind battle).
#   nearby_companions -- живые NPC с follows == hero.id;
#   battle_text -- «в бою рядом с героем против <враги> (<исход>)», до NPC_EVENT_TEXT_MAX знаков;
#   remember_battle -- событие battle спутникам; нет сцены / герой мёртв -- без памяти.
import game_kit  # noqa: F401  (путь к master_kit)
import pytest
from master_kit import combat_ctx

from ai_dm.rules.battle_memory import battle_text, nearby_companions, remember_battle
from ai_dm.rules.npc_memory import remember
from ai_dm.state.relations import NPC_EVENT_TEXT_MAX, NpcEvent
from ai_dm.state.world import NPC


def setup(registry, cfg, follows=True, status="alive"):
    bundle = combat_ctx(registry, cfg).bundle
    hero = bundle.heroes[0]
    npc = NPC(
        id="lira", name="Лира", means=["бой"], status=status, follows=hero.id if follows else None
    )
    bundle.world.npcs["lira"] = npc
    return bundle, hero, npc


def battle_events(npc):
    return [e for m in npc.memory for e in m.events if e.kind == "battle"]


def fight(bundle, hero, outcome="victory", cfg=None):
    remember_battle(bundle, hero, bundle.session.active_combat, outcome, cfg)


# nearby_companions

def test_nearby_companions_includes_alive_follower(registry, cfg):
    bundle, hero, npc = setup(registry, cfg)
    assert nearby_companions(bundle.world, hero) == [npc]


def test_nearby_companions_skips_not_following(registry, cfg):
    bundle, hero, _ = setup(registry, cfg, follows=False)
    assert nearby_companions(bundle.world, hero) == []


def test_nearby_companions_skips_not_alive(registry, cfg):
    bundle, hero, _ = setup(registry, cfg, status="dead")
    assert nearby_companions(bundle.world, hero) == []


def test_nearby_companions_skips_follower_of_someone_else(registry, cfg):
    bundle, hero, npc = setup(registry, cfg)
    npc.follows = "other_hero"
    assert nearby_companions(bundle.world, hero) == []


# battle_text

def test_battle_text_victory_lists_enemies(registry, cfg):
    bundle, hero, _ = setup(registry, cfg)
    text = battle_text(bundle.session.active_combat, {hero.id: hero}, "victory")
    assert text == "в бою рядом с героем против Воин-гоблин 1, Воин-гоблин 2 (победа)"


def test_battle_text_fled(registry, cfg):
    bundle, hero, _ = setup(registry, cfg)
    text = battle_text(bundle.session.active_combat, {hero.id: hero}, "fled")
    assert text.endswith("(бегство)")


def test_battle_text_ended_by_master(registry, cfg):
    bundle, hero, _ = setup(registry, cfg)
    text = battle_text(bundle.session.active_combat, {hero.id: hero}, "ended_by_master")
    assert text.endswith("(бой прерван)")


@pytest.mark.parametrize("outcome", ["defeat_pending", "hero_dying"])
def test_battle_text_hero_fell_outcomes(registry, cfg, outcome):
    bundle, hero, _ = setup(registry, cfg)
    text = battle_text(bundle.session.active_combat, {hero.id: hero}, outcome)
    assert text.endswith("(герой пал)")


def test_battle_text_unknown_outcome_is_hero_fell(registry, cfg):
    bundle, hero, _ = setup(registry, cfg)
    text = battle_text(bundle.session.active_combat, {hero.id: hero}, "что-то")
    assert text.endswith("(герой пал)")


def test_battle_text_has_no_heroes_among_enemies(registry, cfg):
    bundle, hero, _ = setup(registry, cfg)
    text = battle_text(bundle.session.active_combat, {hero.id: hero}, "victory")
    assert hero.name not in text


def test_battle_text_same_names_are_not_repeated(registry, cfg):
    bundle, hero, _ = setup(registry, cfg)
    state = bundle.session.active_combat
    for part in state.participants:
        if part.side == "enemies":
            part.name = "Волк"
    # participant_name нумерует одинаковые имена; повтор имени после нумерации исключён
    names = battle_text(state, {hero.id: hero}, "victory").split("против ")[1].split(" (")[0]
    parts = names.split(", ")
    assert len(parts) == len(set(parts))


def test_battle_text_many_long_names_is_cut_with_ellipsis(registry, cfg):
    bundle, hero, _ = setup(registry, cfg)
    state = bundle.session.active_combat
    enemies = [p for p in state.participants if p.side == "enemies"]
    for i in range(10):
        clone = enemies[0].model_copy(deep=True)
        clone.ref = f"x{i}"
        clone.name = f"Свирепый гоблин-налётчик номер{i}"
        state.participants.append(clone)
    text = battle_text(state, {hero.id: hero}, "victory")
    assert len(text) <= NPC_EVENT_TEXT_MAX
    assert text.endswith("…")


# remember_battle

def test_remember_battle_writes_event_to_companion(registry, cfg):
    bundle, hero, npc = setup(registry, cfg)
    fight(bundle, hero, cfg=cfg)
    [event] = battle_events(npc)
    assert event.text == "в бою рядом с героем против Воин-гоблин 1, Воин-гоблин 2 (победа)"


def test_remember_battle_event_has_turn_seq_and_scene(registry, cfg):
    bundle, hero, npc = setup(registry, cfg)
    bundle.session.turn_seq = 7
    fight(bundle, hero, cfg=cfg)
    assert npc.memory[0].scene_id == bundle.session.current_scene.id
    assert npc.memory[0].events[0].turn_seq == 7


def test_remember_battle_defeat_pending_text(registry, cfg):
    bundle, hero, npc = setup(registry, cfg)
    fight(bundle, hero, "defeat_pending", cfg)
    assert battle_events(npc)[0].text.endswith("(герой пал)")


def test_remember_battle_not_following_npc_has_no_memory(registry, cfg):
    bundle, hero, npc = setup(registry, cfg, follows=False)
    fight(bundle, hero, cfg=cfg)
    assert npc.memory == []


def test_remember_battle_not_alive_npc_has_no_memory(registry, cfg):
    bundle, hero, npc = setup(registry, cfg, status="dead")
    fight(bundle, hero, cfg=cfg)
    assert npc.memory == []


def test_remember_battle_dead_hero_writes_nothing(registry, cfg):
    bundle, hero, npc = setup(registry, cfg)
    hero.status = "dead"
    fight(bundle, hero, cfg=cfg)
    assert npc.memory == []


def test_remember_battle_without_scene_writes_nothing(registry, cfg):
    bundle, hero, npc = setup(registry, cfg)
    bundle.session.current_scene = None
    fight(bundle, hero, cfg=cfg)
    assert npc.memory == []


def test_remember_battle_second_fight_in_same_scene_keeps_one_event(registry, cfg):
    bundle, hero, npc = setup(registry, cfg)
    fight(bundle, hero, cfg=cfg)
    fight(bundle, hero, "fled", cfg)
    assert len(battle_events(npc)) == 1


def test_remember_battle_skips_companion_who_remembers_and_writes_next(registry, cfg):
    bundle, hero, first = setup(registry, cfg)
    second = NPC(id="borin", name="Борин", means=["бой"], follows=hero.id)
    bundle.world.npcs["borin"] = second
    remember(first, bundle.session.current_scene,
             NpcEvent(kind="battle", turn_seq=1, text="старый бой"), cfg.npc_memory)
    fight(bundle, hero, cfg=cfg)
    assert len(battle_events(second)) == 1


def test_remember_battle_second_fight_keeps_first_text(registry, cfg):
    bundle, hero, npc = setup(registry, cfg)
    fight(bundle, hero, cfg=cfg)
    fight(bundle, hero, "fled", cfg)
    assert battle_events(npc)[0].text.endswith("(победа)")
