# Ожидаемый API: ai_dm.game.starter.new_world(hero="grey") + бой в TurnRunner (реактивный мок).
# Грей (следопыт): бой проходит и дальним (лук), и ближним (скимитар) оружием.
# Один гоблин-воин против героя с 11 HP: дальний бой -- гоблин в зале, ближний -- в зоне героя.
from game_kit import (
    SAVED_AT,
    combat_of,
    drive,
    make_rig,
    option_ids,
    script_then_react,
    start_combat_call,
    text_step,
    tools_step,
)

from ai_dm.game.starter import new_world

RANGED = "attack:longbow:"
MELEE = "attack:scimitar:"
SEED_RANGED_WINS = 5


def grey_rig(registry, cfg, tmp_path, seed, enemy_zone="hall"):
    bundle = new_world(registry, cfg, hero="grey", seed=seed, world_id="w1", saved_at=SAVED_AT)
    call = start_combat_call()
    call["input"]["enemies"] = [
        {"ref": "g1", "monster_id": "goblin_warrior", "zone": enemy_zone, "group": "goblins"}
    ]
    steps = [tools_step(call), text_step("Гоблин бросается на вас.")]
    rig = make_rig(registry, cfg, tmp_path, script_then_react(steps), bundle=bundle)
    assert rig.runner.play("Бью ногой дверь").committed is True
    return rig


def pick(prefix):
    # первая не оглушающая атака этим оружием; иначе шаг к врагу; иначе конец хода
    def choose(runner):
        ids = option_ids(runner)
        for i, option_id in enumerate(ids):
            if option_id.startswith(prefix) and not option_id.endswith(":nonlethal"):
                return i + 1
        enemy_zones = {
            p.zone_id for p in combat_of(runner).participants
            if p.side == "enemies" and p.status == "active"
        }
        for i, option_id in enumerate(ids):
            if option_id.startswith("move:") and option_id[len("move:"):] in enemy_zones:
                return i + 1
        return len(ids)

    return choose


def test_grey_has_ranged_attack_option_on_enemy_in_next_zone(registry, cfg, tmp_path):
    rig = grey_rig(registry, cfg, tmp_path, SEED_RANGED_WINS)
    assert "attack:longbow:g1" in option_ids(rig.runner)


def test_grey_ranged_combat_ends_in_victory(registry, cfg, tmp_path):
    rig = grey_rig(registry, cfg, tmp_path, SEED_RANGED_WINS)
    results = drive(rig.runner, pick(RANGED))
    assert all(r.committed for r in results)
    assert results[-1].combat_outcome == "victory"
    assert rig.runner.bundle.session.active_combat is None


def test_grey_has_melee_attack_option_on_enemy_in_his_zone(registry, cfg, tmp_path):
    rig = grey_rig(registry, cfg, tmp_path, SEED_RANGED_WINS, enemy_zone="door")
    assert "attack:scimitar:g1" in option_ids(rig.runner)


def test_grey_melee_combat_runs_to_the_end(registry, cfg, tmp_path):
    rig = grey_rig(registry, cfg, tmp_path, SEED_RANGED_WINS, enemy_zone="door")
    results = drive(rig.runner, pick(MELEE))
    assert all(r.committed for r in results)
    assert results[-1].combat_outcome in ("victory", "hero_dead")
    assert rig.runner.bundle.session.active_combat is None

