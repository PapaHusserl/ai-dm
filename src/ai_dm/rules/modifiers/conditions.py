from typing import NamedTuple

from ai_dm.rules.creatures import D20_KINDS, creature_of
from ai_dm.rules.exhaustion import exhaustion_penalty
from ai_dm.rules.modifiers.base import Modifier
from ai_dm.state.creature import AppliedCondition


class Rule(NamedTuple):
    who: str  # "actor" -- состояние у бросающего, "target" -- у цели
    kinds: tuple
    effect: str  # advantage | disadvantage | auto_fail | auto_crit
    abilities: tuple | None = None
    melee: bool | None = None
    # только против тех, кто не является источником состояния (grappled: схвативший)
    other_than_source: bool = False


# вложенные состояния SRD 5.2: состояние влечёт за собой другие
IMPLIED_CONDITIONS = {
    "unconscious": ("incapacitated", "prone"),
    "paralyzed": ("incapacitated",),
    "stunned": ("incapacitated",),
    "petrified": ("incapacitated",),
}

# подписи состояний в строке броска (источник преимущества или помехи)
CONDITION_WORDS = {
    "incapacitated": "недееспособен", "grappled": "схвачен", "poisoned": "яд",
    "prone": "лежит", "paralyzed": "паралич", "unconscious": "без сознания",
    "stunned": "оглушён", "petrified": "окаменел", "blinded": "ослеплён",
    "restrained": "опутан", "invisible": "невидим", "frightened": "страх", "cursed": "проклят",
    "diseased": "болен", "smelly": "вонь",
}

# состояния SRD 5.2, влияющие на броски; остальные (charmed, deafened) на конвейер не влияют
CONDITION_RULES = {
    "incapacitated": [Rule("actor", ("initiative",), "disadvantage")],
    "grappled": [Rule("actor", ("attack",), "disadvantage", other_than_source=True)],
    "poisoned": [Rule("actor", ("attack", "check"), "disadvantage")],
    "prone": [
        Rule("actor", ("attack",), "disadvantage"),
        Rule("target", ("attack",), "advantage", melee=True),
        Rule("target", ("attack",), "disadvantage", melee=False),
    ],
    "paralyzed": [
        Rule("target", ("attack",), "advantage"),
        Rule("target", ("attack",), "auto_crit", melee=True),
        Rule("actor", ("save",), "auto_fail", abilities=("str", "dex")),
    ],
    "unconscious": [
        Rule("target", ("attack",), "advantage"),
        Rule("target", ("attack",), "auto_crit", melee=True),
        Rule("actor", ("save",), "auto_fail", abilities=("str", "dex")),
    ],
    "stunned": [
        Rule("target", ("attack",), "advantage"),
        Rule("actor", ("save",), "auto_fail", abilities=("str", "dex")),
    ],
    "petrified": [
        Rule("target", ("attack",), "advantage"),
        Rule("actor", ("save",), "auto_fail", abilities=("str", "dex")),
    ],
    "blinded": [
        Rule("actor", ("attack",), "disadvantage"),
        Rule("target", ("attack",), "advantage"),
    ],
    "restrained": [
        Rule("actor", ("attack",), "disadvantage"),
        Rule("actor", ("save",), "disadvantage", abilities=("dex",)),
        Rule("target", ("attack",), "advantage"),
    ],
    "invisible": [
        Rule("actor", ("attack", "initiative"), "advantage"),
        Rule("target", ("attack",), "disadvantage"),
    ],
    "frightened": [Rule("actor", ("attack", "check"), "disadvantage")],
    # не SRD: проклятие мастера, помеха на проверки характеристик и спасброски (без атак)
    "cursed": [Rule("actor", ("check", "save"), "disadvantage")],
    # не SRD: болезнь от платной близости, как отравление (У1 П3)
    "diseased": [Rule("actor", ("attack", "check"), "disadvantage")],
    # не SRD: неделя без мытья, помеха на проверки Харизмы (У1 П3)
    "smelly": [Rule("actor", ("check",), "disadvantage", abilities=("cha",))],
}


def rule_matches(rule: Rule, request, applied) -> bool:
    if request.kind not in rule.kinds:
        return False
    if rule.other_than_source and applied.source == request.target_id is not None:
        return False
    if rule.abilities is not None and request.ability not in rule.abilities:
        return False
    return rule.melee is None or bool(request.tags.get("melee", False)) == rule.melee


def rule_modifier(condition_id: str, rule: Rule, applied=None) -> Modifier:
    label = CONDITION_WORDS.get(condition_id, condition_id)
    # невидимость от действия Спрятаться
    if applied is not None and applied.source == "hidden":
        label = "скрытно"
    if rule.effect == "advantage":
        return Modifier(source=condition_id, label=label, advantage=True)
    if rule.effect == "disadvantage":
        return Modifier(source=condition_id, label=label, disadvantage=True)
    if rule.effect == "auto_fail":
        return Modifier(source=condition_id, auto_fail=True)
    return Modifier(source=condition_id, auto_crit=True)


def with_implied(creature) -> list:
    # состояния существа вместе с вложенными (без повторов по id)
    result = list(creature.conditions)
    ids = {c.id for c in result}
    for applied in creature.conditions:
        for implied_id in IMPLIED_CONDITIONS.get(applied.id, ()):
            if implied_id not in ids:
                ids.add(implied_id)
                result.append(AppliedCondition(id=implied_id))
    return result


class ConditionSource:
    id = "conditions"

    def modifiers(self, request, registry) -> list[Modifier]:
        result = []
        holders = [("actor", creature_of(request.actor))]
        if request.target is not None:
            holders.append(("target", creature_of(request.target)))
        for who, creature in holders:
            for applied in with_implied(creature):
                for rule in CONDITION_RULES.get(applied.id, []):
                    if rule.who == who and rule_matches(rule, request, applied):
                        result.append(rule_modifier(applied.id, rule, applied))
        actor = creature_of(request.actor)
        if actor.exhaustion > 0 and request.kind in D20_KINDS:
            result.append(Modifier(source="exhaustion", flat=exhaustion_penalty(actor.exhaustion)))
        return result
