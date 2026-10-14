from ai_dm.core.rng import Rng
from ai_dm.game.starter import fighter_choices
from ai_dm.rules.builder import build_character
from ai_dm.rules.encounter import enemy_cost, party_budget, tier_of
from ai_dm.state.combat import CombatState, Group, Participant, Zone, ZoneFeature
from ai_dm.state.creature import CreatureState
from ai_dm.state.world import WorldState

# обитатели подвала Вейла и старой крипты, от дорогих к дешёвым (порядок задаёт жадный набор)
CELLAR_POOL = ("wight", "ghast", "ghoul", "shadow", "skeleton", "zombie", "giant_rat")
# больше врагов в сцене не ставится
CELLAR_CAP = 6


def fill_budget(budget, pool, registry, cap=CELLAR_CAP) -> list[str]:
    # жадно по порядку пула: каждого вида ставим, пока влезает в остаток бюджета и в cap
    result = []
    left = budget
    for monster_id in pool:
        cost = enemy_cost(monster_id, registry)
        while cost <= left and len(result) < cap:
            result.append(monster_id)
            left -= cost
    return result


def cellar_monster(registry, ref, monster_id, zone_id) -> Participant:
    monster = registry.get("monster", monster_id)
    return Participant(
        ref=ref, side="enemies", group_id="crypt", zone_id=zone_id, monster_id=monster_id,
        name=monster.name, creature=CreatureState(hp_current=monster.hp, hp_max=monster.hp),
    )


def build_cellar(registry, cfg, seed, hero, difficulty):
    # локальный импорт: цикл импортов с sim_combat
    from ai_dm.devtools.sim_combat import Scenario

    if hero is None:
        hero = build_character(fighter_choices(), registry)
    rng = Rng(seed)
    world = WorldState(world_id="sim", rng=rng.state)
    if difficulty is not None:
        world.settings["difficulty"] = difficulty
    budget = party_budget([hero.sheet.level], registry, tier_of(world, cfg))
    zones = [
        Zone(id="stairs", name="У лестницы", adjacent=["barrels"]),
        Zone(
            id="barrels", name="Бочки", adjacent=["stairs", "crypt"],
            features=[ZoneFeature(kind="cover_half")],
        ),
        Zone(id="crypt", name="Крипта", adjacent=["barrels"]),
    ]
    participants = [
        Participant(
            ref="hero", side="heroes", group_id="party", zone_id="stairs", controller="auto_hero"
        )
    ]
    for index, monster_id in enumerate(fill_budget(budget, CELLAR_POOL, registry)):
        zone_id = ("crypt", "barrels")[index % 2]
        participants.append(cellar_monster(registry, f"enemy_{index + 1}", monster_id, zone_id))
    groups = {"party": Group(leader_id="hero")}
    if len(participants) > 1:
        groups["crypt"] = Group(leader_id=participants[1].ref, intent="kill")
    state = CombatState(id="fight_1", zones=zones, participants=participants, groups=groups)
    return Scenario(state, world, {hero.id: hero}, registry, cfg, rng)
