# К1 «Концентрация по часам»: страховки конца хода и границы сцены (docs/plan-k1.md, п. 2.6; В2а).
#   TurnRunner.attempt: после explore_turn/combat_turn -- expire_concentration героя; ловит
#     концентрацию, чей срок вышел раньше хода (сейв загружен), и любые сдвиги часов без обработчика
#     (left_to_die); ровно в срок -- кончилась; бессрочная (until_s None) и будущая -- держатся.
#   scene.close_scene: после ensure_min_advance (10 мин) -- тот же вызов: Благословение вне боя
#     (1 мин) снимается до автосейва; без сдвига часов просроченная всё равно снимается.
import game_kit
from game_kit import (
    advance_call,
    drive,
    end_turn_number,
    make_rig,
    script_then_react,
    scripted,
    start_combat_call,
    text_step,
    tools_step,
)
from protocol_kit import make_bundle

from ai_dm.game.scene import close_scene
from ai_dm.state.creature import ActiveEffect, Concentration, Expiry


def blessed(bundle, until_s, now_s=0):
    # герой держит Благословение: объект концентрации, метка заклинания и эффект-модификатор
    hero = bundle.heroes[0]
    bundle.world.clock.advance(now_s)
    hero.creature.concentration = Concentration(spell_id="bless", circle=1, until_s=until_s)
    hero.creature.active_effects.append(
        ActiveEffect(
            id="bless", source=hero.id, kind="modifier",
            params={"target": "attack_roll", "dice": "1d4"},
            expires=Expiry(kind="concentration", owner=hero.id),
        )
    )
    return hero


def play(registry, cfg, tmp_path, bundle, steps=None):
    steps = steps or [text_step("Идёшь дальше.")]
    rig = make_rig(registry, cfg, tmp_path, scripted(steps), bundle=bundle)
    result = rig.runner.play("Иду")
    return rig, result


# конец хода

def test_turn_ends_a_concentration_that_ran_out_before_it(registry, cfg, tmp_path):
    bundle = make_bundle(registry)
    blessed(bundle, until_s=500, now_s=1000)
    rig, result = play(registry, cfg, tmp_path, bundle)
    assert result.committed is True
    assert rig.runner.bundle.heroes[0].creature.concentration is None


def test_turn_removes_the_effects_of_the_ended_concentration(registry, cfg, tmp_path):
    bundle = make_bundle(registry)
    blessed(bundle, until_s=500, now_s=1000)
    rig, _ = play(registry, cfg, tmp_path, bundle)
    assert rig.runner.bundle.heroes[0].creature.active_effects == []


def test_turn_ends_a_concentration_exactly_at_its_limit(registry, cfg, tmp_path):
    bundle = make_bundle(registry)
    blessed(bundle, until_s=1000, now_s=1000)
    rig, _ = play(registry, cfg, tmp_path, bundle)
    assert rig.runner.bundle.heroes[0].creature.concentration is None


def test_turn_keeps_a_concentration_that_has_time_left(registry, cfg, tmp_path):
    bundle = make_bundle(registry)
    blessed(bundle, until_s=1001, now_s=1000)
    rig, _ = play(registry, cfg, tmp_path, bundle)
    assert rig.runner.bundle.heroes[0].creature.concentration is not None
    assert len(rig.runner.bundle.heroes[0].creature.active_effects) == 1


def test_turn_keeps_an_unlimited_concentration_of_an_old_save(registry, cfg, tmp_path):
    bundle = make_bundle(registry)
    blessed(bundle, until_s=None, now_s=10**6)
    rig, _ = play(registry, cfg, tmp_path, bundle)
    assert rig.runner.bundle.heroes[0].creature.concentration is not None


def test_turn_without_concentration_is_unchanged(registry, cfg, tmp_path):
    bundle = make_bundle(registry)
    rig, result = play(registry, cfg, tmp_path, bundle)
    assert result.committed is True
    assert rig.runner.bundle.heroes[0].creature.concentration is None


def test_advance_time_in_a_turn_ends_the_concentration_once(registry, cfg, tmp_path):
    bundle = make_bundle(registry)
    blessed(bundle, until_s=60, now_s=0)
    steps = [tools_step(advance_call(category="hour")), text_step("Час спустя.")]
    rig, result = play(registry, cfg, tmp_path, bundle, steps)
    assert rig.runner.bundle.heroes[0].creature.concentration is None
    assert result.requests == ["advance_time"]


def test_rolled_back_turn_does_not_touch_the_concentration(registry, cfg, tmp_path):
    from game_kit import BAD_CHECK

    bundle = make_bundle(registry)
    hero = blessed(bundle, until_s=500, now_s=1000)
    steps = [tools_step(BAD_CHECK)] * 8
    rig = make_rig(registry, cfg, tmp_path, scripted(steps), bundle=bundle)
    result = rig.runner.play("Иду")
    assert result.committed is False
    assert hero.creature.concentration is not None


# граница сцены

def test_close_scene_min_advance_ends_a_short_concentration(registry, cfg):
    bundle = make_bundle(registry)
    hero = blessed(bundle, until_s=60)
    close_scene(bundle, "end_scene", cfg)
    assert bundle.world.clock.now_s == cfg.time.min_advance_s == 600
    assert hero.creature.concentration is None
    assert hero.creature.active_effects == []


def test_close_scene_keeps_a_concentration_that_outlasts_the_minimum(registry, cfg):
    bundle = make_bundle(registry)
    hero = blessed(bundle, until_s=3600)
    close_scene(bundle, "end_scene", cfg)
    assert hero.creature.concentration is not None


def test_close_scene_ends_an_overdue_concentration_even_without_a_time_shift(registry, cfg):
    bundle = make_bundle(registry)
    hero = blessed(bundle, until_s=100, now_s=900)
    close_scene(bundle, "end_scene", cfg)
    assert bundle.world.clock.now_s == 900
    assert hero.creature.concentration is None


def test_close_scene_keeps_an_unlimited_concentration(registry, cfg):
    bundle = make_bundle(registry)
    hero = blessed(bundle, until_s=None)
    close_scene(bundle, "end_scene", cfg)
    assert hero.creature.concentration is not None


def test_close_scene_still_sets_the_reason(registry, cfg):
    bundle = make_bundle(registry)
    blessed(bundle, until_s=60)
    close_scene(bundle, "turn_limit", cfg)
    assert bundle.session.current_scene.closed_reason == "turn_limit"


# поражение с left_to_die: часы уходят на часы внутри хода боя, концентрацию снимает attempt

def test_left_to_die_turn_ends_the_concentration(registry, cfg, tmp_path, monkeypatch):
    monkeypatch.setattr(
        game_kit, "defeat_input",
        lambda: {"type": "defeat_outcome", "consequences": ["left_to_die"]},
    )
    steps = [
        tools_step(start_combat_call(intent="capture")), text_step("Гоблины бросаются на вас."),
    ]
    bundle = make_bundle(registry)
    hero = bundle.heroes[0]
    hero.creature.hp_current = 1
    hero.creature.concentration = Concentration(spell_id="hunters_mark", circle=1, until_s=3600)
    hero.creature.active_effects.append(
        ActiveEffect(
            id="hunters_mark", source=hero.id, kind="mark_pending",
            params={"target": "g1", "dice": "1d6", "damage_type": "force"},
            expires=Expiry(kind="concentration", owner=hero.id),
        )
    )
    rig = make_rig(registry, cfg, tmp_path, script_then_react(steps), bundle=bundle)
    assert rig.runner.play("Бью ногой дверь").committed is True
    results = drive(rig.runner, end_turn_number)
    assert results[-1].combat_outcome == "defeat_pending"
    assert rig.runner.bundle.world.clock.now_s >= 3600
    held = rig.runner.bundle.heroes[0]
    assert held.creature.concentration is None
    assert [e.kind for e in held.creature.active_effects] == []
