# Ожидаемый API: ai_dm.rules.rests (hero: HeroState, clock: GameClock -- world.clock, мутируются)
#   short_rest(hero, registry, rng, clock, cfg, *, hit_dice=0) -> int
#       тратит hit_dice костей хитов из пула hero.creature.resources["hit_dice:d10"] (ResourcePool;
#       пул заводит builder/resource_maxes -- в этой партии тест кладёт его сам): за каждую --
#       бросок кости класса (class.hit_die, d10 у воина) + мод. ТЕЛ, лечение через healing.heal.
#       Возвращает суммарно восстановленные HP. Больше костей, чем есть (или пула нет) ->
#       ValueError, состояние и часы не меняются. Пулы с recover on short_rest:
#       +amount (не выше max), данные -- из умений героя в реестре (Second Wind +1);
#       ячейки (spell_slot:N) не трогает.
#       Часы двигаются на time_ops.short_rest_seconds(cfg) (1 ч) через clock.advance.
#       cfg: RulesConfig -- обязательный (аудит 1 п. 2.8), в тестах передаётся по имени
#   long_rest(hero, registry, clock, cfg) -> None
#       HP = hp_max; hit_dice = max (SRD 5.2: все потраченные кости); все пулы с recover long_rest
#       "all" -> max; ячейки spell_slot:N -> max; exhaustion -1 (не ниже 0); если у вида героя есть
#       умение Resourceful (человек) -- hero.heroic_inspiration = True; часы +
#       time_ops.long_rest_seconds(cfg) (8 ч); с пользовательским cfg -- на его значение
#       Длинный отдых при 0 HP (живой, но без сознания) -> ValueError (SRD 5.2: нужен хотя бы 1 HP),
#       состояние и часы не меняются. Мёртвый (hero.status == "dead"): short_rest и long_rest ->
#       ValueError, состояние и часы не меняются (B3).
#   derived.LONG_REST_FULL = ("hit_dice", "spell_slot:") -- префиксы пулов, полностью
#       восстанавливаемых длинным отдыхом (D4)
#   Один пул восстанавливается по recover не более одного раза за отдых: дубли эффектов
#       (одно умение дважды) не удваивают восстановление (D4)
import pytest

from ai_dm.config.settings import load_rules_config
from ai_dm.core.clock import GameClock
from ai_dm.core.rng import Rng
from ai_dm.rules import rests
from ai_dm.rules.derived import LONG_REST_FULL
from ai_dm.rules.rests import long_rest, short_rest
from ai_dm.rules.time_ops import long_rest_seconds, short_rest_seconds
from ai_dm.state.creature import CreatureState, ResourcePool
from ai_dm.state.hero import BackgroundSpec, CharacterSheet, ClassLevel, HeroState


class ScriptedRng(Rng):
    def __init__(self, *rolls):
        super().__init__(1)
        self.rolls = list(rolls)

    def randbelow(self, n):
        sides, face = self.rolls.pop(0)
        assert sides == n
        return face - 1


def make_hero(species="human", class_id="fighter", hp=3, **creature):
    # ТЕЛ 15 -> мод. +2
    sheet = CharacterSheet(
        species_id=species,
        classes=[ClassLevel(class_id=class_id)], level_history=[class_id] * 1,
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
        creature=CreatureState(hp_current=hp, hp_max=20, **creature),
    )


def pool(current, maximum):
    return ResourcePool(current=current, max=maximum)


def make_fighter(hp=3, hit_dice=2, second_wind=0, **kwargs):
    return make_hero(
        hp=hp,
        resources={"hit_dice:d10": pool(hit_dice, 2), "second_wind": pool(second_wind, 2)},
        **kwargs,
    )


# короткий отдых

def test_short_rest_without_spending_dice_keeps_hp(registry, cfg):
    hero = make_fighter()
    assert short_rest(hero, registry, ScriptedRng(), GameClock(), cfg=cfg) == 0
    assert hero.creature.hp_current == 3


def test_short_rest_spends_hit_die_and_adds_con_mod(registry, cfg):
    hero = make_fighter()
    healed = short_rest(hero, registry, ScriptedRng((10, 6)), GameClock(), cfg=cfg, hit_dice=1)
    assert healed == 8
    assert hero.creature.hp_current == 11


def test_short_rest_decrements_hit_dice_pool(registry, cfg):
    hero = make_fighter()
    short_rest(hero, registry, ScriptedRng((10, 6)), GameClock(), cfg=cfg, hit_dice=1)
    assert hero.creature.resources["hit_dice:d10"].current == 1


def test_short_rest_two_dice(registry, cfg):
    hero = make_fighter()
    rng = ScriptedRng((10, 6), (10, 3))
    healed = short_rest(hero, registry, rng, GameClock(), cfg=cfg, hit_dice=2)
    assert healed == 8 + 5
    assert hero.creature.resources["hit_dice:d10"].current == 0


def test_short_rest_healing_is_capped_at_max_hp(registry, cfg):
    hero = make_fighter(hp=18)
    healed = short_rest(hero, registry, ScriptedRng((10, 6)), GameClock(), cfg=cfg, hit_dice=1)
    assert healed == 2
    assert hero.creature.hp_current == 20


def test_short_rest_more_dice_than_available_is_error(registry, cfg):
    hero = make_fighter(hit_dice=1)
    clock = GameClock()
    with pytest.raises(ValueError):
        short_rest(hero, registry, ScriptedRng(), clock, cfg=cfg, hit_dice=2)
    assert hero.creature.hp_current == 3
    assert hero.creature.resources["hit_dice:d10"].current == 1
    assert clock.now_s == 0


def test_short_rest_without_hit_dice_pool_is_error_when_spending(registry, cfg):
    hero = make_hero()
    with pytest.raises(ValueError):
        short_rest(hero, registry, ScriptedRng(), GameClock(), cfg=cfg, hit_dice=1)


def test_short_rest_recovers_one_second_wind(registry, cfg):
    hero = make_fighter(second_wind=0)
    short_rest(hero, registry, ScriptedRng(), GameClock(), cfg=cfg)
    assert hero.creature.resources["second_wind"].current == 1


def test_short_rest_second_wind_not_above_max(registry, cfg):
    hero = make_fighter(second_wind=2)
    short_rest(hero, registry, ScriptedRng(), GameClock(), cfg=cfg)
    assert hero.creature.resources["second_wind"].current == 2


def test_short_rest_second_wind_from_one_to_two(registry, cfg):
    hero = make_fighter(second_wind=1)
    short_rest(hero, registry, ScriptedRng(), GameClock(), cfg=cfg)
    assert hero.creature.resources["second_wind"].current == 2


def test_short_rest_does_not_restore_spell_slots(registry, cfg):
    hero = make_hero(class_id="wizard", resources={"spell_slot:1": pool(0, 2)})
    short_rest(hero, registry, ScriptedRng(), GameClock(), cfg=cfg)
    assert hero.creature.resources["spell_slot:1"].current == 0


def test_short_rest_advances_clock_by_one_hour(registry, cfg):
    clock = GameClock(now_s=1000)
    short_rest(make_fighter(), registry, ScriptedRng(), clock, cfg=cfg)
    assert clock.now_s == 1000 + short_rest_seconds(cfg=cfg)
    assert short_rest_seconds(cfg=cfg) == 3600


def test_short_rest_is_deterministic_by_seed(registry, cfg):
    heroes = [make_fighter(), make_fighter()]
    for hero in heroes:
        short_rest(hero, registry, Rng(8), GameClock(), cfg=cfg, hit_dice=2)
    assert heroes[0].creature == heroes[1].creature


# длинный отдых

def test_long_rest_restores_full_hp(registry, cfg):
    hero = make_fighter()
    long_rest(hero, registry, GameClock(), cfg=cfg)
    assert hero.creature.hp_current == 20


def test_long_rest_restores_hit_dice(registry, cfg):
    hero = make_fighter(hit_dice=0)
    long_rest(hero, registry, GameClock(), cfg=cfg)
    assert hero.creature.resources["hit_dice:d10"].current == 2


def test_long_rest_restores_second_wind_fully(registry, cfg):
    hero = make_fighter(second_wind=0)
    long_rest(hero, registry, GameClock(), cfg=cfg)
    assert hero.creature.resources["second_wind"].current == 2


def test_long_rest_restores_spell_slots(registry, cfg):
    hero = make_hero(
        class_id="wizard",
        resources={"spell_slot:1": pool(0, 2), "spell_slot:2": pool(1, 1)},
    )
    long_rest(hero, registry, GameClock(), cfg=cfg)
    assert hero.creature.resources["spell_slot:1"].current == 2
    assert hero.creature.resources["spell_slot:2"].current == 1


def test_long_rest_removes_one_exhaustion_level(registry, cfg):
    hero = make_fighter(exhaustion=2)
    long_rest(hero, registry, GameClock(), cfg=cfg)
    assert hero.creature.exhaustion == 1


def test_long_rest_exhaustion_not_below_zero(registry, cfg):
    hero = make_fighter(exhaustion=0)
    long_rest(hero, registry, GameClock(), cfg=cfg)
    assert hero.creature.exhaustion == 0


def test_long_rest_gives_heroic_inspiration_to_human(registry, cfg):
    hero = make_fighter()
    long_rest(hero, registry, GameClock(), cfg=cfg)
    assert hero.heroic_inspiration is True


def test_long_rest_does_not_give_inspiration_to_elf(registry, cfg):
    hero = make_fighter(species="elf")
    long_rest(hero, registry, GameClock(), cfg=cfg)
    assert hero.heroic_inspiration is False


def test_long_rest_keeps_existing_inspiration_of_elf(registry, cfg):
    hero = make_fighter(species="elf")
    hero.heroic_inspiration = True
    long_rest(hero, registry, GameClock(), cfg=cfg)
    assert hero.heroic_inspiration is True


def test_long_rest_advances_clock_by_eight_hours(registry, cfg):
    clock = GameClock(now_s=1000)
    long_rest(make_fighter(), registry, clock, cfg=cfg)
    assert clock.now_s == 1000 + long_rest_seconds(cfg=cfg)
    assert long_rest_seconds(cfg=cfg) == 28800


# длинный отдых при 0 HP и мёртвый герой (B3)

def test_long_rest_at_zero_hp_is_error(registry, cfg):
    hero = make_fighter(hp=0, hit_dice=0)
    clock = GameClock(now_s=1000)
    with pytest.raises(ValueError):
        long_rest(hero, registry, clock, cfg=cfg)
    assert hero.creature.hp_current == 0
    assert hero.creature.resources["hit_dice:d10"].current == 0
    assert clock.now_s == 1000


def test_long_rest_at_one_hp_is_allowed(registry, cfg):
    hero = make_fighter(hp=1)
    long_rest(hero, registry, GameClock(), cfg=cfg)
    assert hero.creature.hp_current == 20


def test_long_rest_of_dead_hero_is_error(registry, cfg):
    hero = make_fighter(hp=3)
    hero.status = "dead"
    clock = GameClock()
    with pytest.raises(ValueError):
        long_rest(hero, registry, clock, cfg=cfg)
    assert hero.creature.hp_current == 3
    assert clock.now_s == 0


def test_short_rest_of_dead_hero_is_error(registry, cfg):
    hero = make_fighter(hp=3)
    hero.status = "dead"
    clock = GameClock()
    with pytest.raises(ValueError):
        short_rest(hero, registry, ScriptedRng(), clock, cfg=cfg)
    assert clock.now_s == 0


def test_short_rest_of_dead_hero_with_hit_dice_does_not_spend_them(registry, cfg):
    hero = make_fighter(hp=3)
    hero.status = "dead"
    with pytest.raises(ValueError):
        short_rest(hero, registry, ScriptedRng(), GameClock(), cfg=cfg, hit_dice=1)
    assert hero.creature.resources["hit_dice:d10"].current == 2
    assert hero.creature.hp_current == 3


# константа и дубли recover (D4)

def test_long_rest_full_prefixes():
    assert LONG_REST_FULL == ("hit_dice:", "spell_slot:")


def doubled_effects(monkeypatch):
    real = rests.hero_effects
    monkeypatch.setattr(rests, "hero_effects", lambda hero, registry: real(hero, registry) * 2)


def test_duplicated_recover_effect_does_not_double_short_rest_recovery(registry, monkeypatch, cfg):
    hero = make_fighter(second_wind=0)
    doubled_effects(monkeypatch)
    short_rest(hero, registry, ScriptedRng(), GameClock(), cfg=cfg)
    assert hero.creature.resources["second_wind"].current == 1


def test_duplicated_recover_effect_does_not_break_long_rest(registry, monkeypatch, cfg):
    hero = make_fighter(second_wind=0)
    doubled_effects(monkeypatch)
    long_rest(hero, registry, GameClock(), cfg=cfg)
    assert hero.creature.resources["second_wind"].current == 2


# пользовательский cfg (аудит 1 п. 2.8)

def test_long_rest_uses_custom_cfg_duration(registry):
    custom = load_rules_config(toml_text="[time]\nlong_rest_s = 7200\n")
    clock = GameClock(now_s=1000)
    long_rest(make_fighter(), registry, clock, cfg=custom)
    assert clock.now_s == 1000 + 7200


def test_short_rest_uses_custom_cfg_duration(registry):
    custom = load_rules_config(toml_text="[time]\nshort_rest_s = 1800\n")
    clock = GameClock(now_s=1000)
    short_rest(make_fighter(), registry, ScriptedRng(), clock, cfg=custom)
    assert clock.now_s == 1000 + 1800


def test_long_rest_with_custom_cfg_advances_clock_hours_by_two(registry):
    custom = load_rules_config(toml_text="[time]\nlong_rest_s = 7200\n")
    clock = GameClock.from_date("1247-03-12")
    before = clock.now_s
    long_rest(make_fighter(), registry, clock, cfg=custom)
    assert (clock.now_s - before) // 3600 == 2


def test_rests_require_cfg(registry):
    with pytest.raises(TypeError):
        long_rest(make_fighter(), registry, GameClock())
    with pytest.raises(TypeError):
        short_rest(make_fighter(), registry, ScriptedRng(), GameClock())
