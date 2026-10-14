import argparse
import sys
import typing
from dataclasses import dataclass

from ai_dm.combat.engine import CombatEngine
from ai_dm.config.settings import load_rules_config
from ai_dm.content.loader import load_registry
from ai_dm.core.rng import Rng
from ai_dm.game.starter import fighter_choices, wizard_choices
from ai_dm.rules.builder import build_character
from ai_dm.state.combat import CombatState, Group, Outcome, Participant, Zone, ZoneFeature
from ai_dm.state.creature import CreatureState
from ai_dm.state.world import WorldState

SCENARIOS = ("goblins3",)
VARIANTS = ("default", "weak")
OUTCOMES = typing.get_args(Outcome)
INTENTS = ("kill", "capture", "rob", "drive_off", "spare")


class Scenario:
    def __init__(self, state, world, heroes, registry, cfg, rng):
        self.state = state
        self.world = world
        self.heroes = heroes
        self.registry = registry
        self.cfg = cfg
        self.rng = rng

    def engine(self, controllers=None) -> CombatEngine:
        return CombatEngine(
            self.state, self.world, self.heroes, self.registry, self.cfg, self.rng, controllers
        )


@dataclass
class SimResult:
    outcome: str | None
    rounds: int
    log: list
    events: list
    scenario: Scenario


def goblin(registry, ref, zone_id) -> Participant:
    hit_points = registry.get("monster", "goblin_warrior").hp
    return Participant(
        ref=ref, side="enemies", group_id="goblins", zone_id=zone_id,
        monster_id="goblin_warrior", name="Воин-гоблин",
        creature=CreatureState(hp_current=hit_points, hp_max=hit_points),
    )


def build_goblins3(registry, cfg, seed, variant, intent) -> Scenario:
    if variant not in VARIANTS:
        raise ValueError(f"неизвестный вариант: {variant!r}")
    if variant == "weak":
        hero = build_character(wizard_choices(), registry)
    else:
        hero = build_character(fighter_choices(), registry)
    zones = [
        Zone(id="door", name="У двери", adjacent=["hall"]),
        Zone(id="hall", name="Центр зала", adjacent=["door", "balcony"]),
        Zone(
            id="balcony", name="Балкон", adjacent=["hall"],
            features=[ZoneFeature(kind="cover_half")],
        ),
    ]
    participants = [
        Participant(
            ref="hero", side="heroes", group_id="party", zone_id="door", controller="auto_hero"
        ),
        goblin(registry, "goblin_1", "hall"),
        goblin(registry, "goblin_2", "hall"),
        goblin(registry, "goblin_3", "balcony"),
    ]
    groups = {
        "party": Group(leader_id="hero"),
        "goblins": Group(leader_id="goblin_1", intent=intent),
    }
    state = CombatState(id="fight_1", zones=zones, participants=participants, groups=groups)
    rng = Rng(seed)
    world = WorldState(world_id="sim", rng=rng.state)
    return Scenario(state, world, {hero.id: hero}, registry, cfg, rng)


def build_scenario(
    name, registry, cfg, seed, *, variant="default", intent="kill", hero=None, difficulty=None
) -> Scenario:
    if name not in SCENARIOS:
        raise ValueError(f"неизвестный сценарий: {name!r}")
    scenario = build_goblins3(registry, cfg, seed, variant, intent)
    if hero is not None:
        scenario.heroes = {hero.id: hero}
    if difficulty is not None:
        scenario.world.settings["difficulty"] = difficulty
    return scenario


def simulate(scenario, max_rounds=None) -> SimResult:
    engine = scenario.engine()
    events = engine.start()
    events += engine.run_to_end(max_rounds)
    state = scenario.state
    return SimResult(state.outcome, state.round, state.log, events, scenario)


def find_seed(
    name, outcome, *, registry, cfg, variant="default", intent="kill", limit=500
) -> int | None:
    if outcome not in OUTCOMES:
        raise ValueError(f"неизвестный исход: {outcome!r}")
    for seed in range(limit):
        scenario = build_scenario(name, registry, cfg, seed, variant=variant, intent=intent)
        if simulate(scenario).outcome == outcome:
            return seed
    return None


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="sim_combat")
    parser.add_argument("--scenario", choices=SCENARIOS, default="goblins3")
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--variant", choices=VARIANTS, default="default")
    parser.add_argument("--intent", choices=INTENTS, default="kill")
    parser.add_argument("--find-outcome", choices=OUTCOMES)
    parser.add_argument("--limit", type=int, default=500)
    args = parser.parse_args(argv)
    registry = load_registry()
    cfg = load_rules_config()
    if args.find_outcome is not None:
        seed = find_seed(
            args.scenario, args.find_outcome, registry=registry, cfg=cfg,
            variant=args.variant, intent=args.intent, limit=args.limit,
        )
        if seed is None:
            print("none")
            return 1
        print(seed)
        return 0
    scenario = build_scenario(
        args.scenario, registry, cfg, args.seed, variant=args.variant, intent=args.intent
    )
    result = simulate(scenario)
    for line in result.log:
        print(line)
    print(f"outcome: {result.outcome} rounds: {result.rounds}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
