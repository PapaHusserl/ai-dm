from typing import Literal

from pydantic import BaseModel, Field

from ai_dm.core.dice import roll_damage_dice, roll_dice
from ai_dm.rules.creatures import D20_KINDS, creature_of, is_hero
from ai_dm.rules.modifiers import default_modifier_registry
from ai_dm.rules.modifiers.species import species_effects
from ai_dm.rules.names import ABILITY_SHORT, SKILL_NAMES
from ai_dm.state.creature import CreatureState
from ai_dm.state.hero import HeroState

KINDS = D20_KINDS + ("damage",)

REROLL_WORDS = {"luck": "удача", "heroic_inspiration": "вдохновение"}

DAMAGE_TYPE_WORDS = {
    "bludgeoning": "дробящий", "piercing": "колющий", "slashing": "рубящий",
    "fire": "огненный", "cold": "холодный", "lightning": "электрический",
    "thunder": "звуковой", "acid": "кислотный", "poison": "ядовитый",
    "necrotic": "некротический", "radiant": "излучением", "psychic": "психический",
    "force": "силовой", "falling": "падение",
}

# подписи эффектов и источников без названия в реестре (источник преимущества или помехи)
SOURCE_WORDS = {
    "dodge": "уклонение", "help": "помощь", "divine_favor": "молитва", "divine_curse": "кара",
    "sap": "ослаблен", "vex": "досада", "improvised_advantage": "импровизация",
}

OUTCOME_WORDS = {
    "hit": "попадание",
    "crit": "критическое попадание",
    "miss": "промах",
    "success": "успех",
    "fail": "провал",
}


class RollRequest(BaseModel):
    kind: str
    actor: HeroState | CreatureState
    actor_id: str = ""
    target: HeroState | CreatureState | None = None
    target_id: str | None = None
    ability: str | None = None
    skill: str | None = None
    tags: dict[str, bool | int | str] = Field(default_factory=dict)
    base_adv: Literal["normal", "advantage", "disadvantage"] = "normal"
    # откуда base_adv: «дальность», «враг рядом»; пусто -- не подписывается
    base_adv_label: str = ""
    bonus: int = 0
    # слагаемые бонуса с подписью: («Лов», 4), («мастерство», 2); сумма = bonus
    bonus_parts: list[tuple[str, int]] = Field(default_factory=list)
    # название броска в строке лога: «длинный лук», «Метка охотника»
    label: str = ""
    damage_type: str = ""
    dc: int | None = None
    # пояснение к КД в строке атаки: «бронебойная»
    dc_note: str = ""
    dice: str | None = None
    # игровое время в секундах (для источников «раз в день»)
    now_s: int | None = None


class RollTerm(BaseModel):
    source: str
    value: int
    detail: str = ""
    label: str = ""


class RollLogEntry(BaseModel):
    text: str


class RollResult(BaseModel):
    kind: str
    terms: list[RollTerm]
    total: int
    natural: int | None = None
    d20_rolls: list[int] = Field(default_factory=list)
    advantage: Literal["normal", "advantage", "disadvantage"] = "normal"
    # подписи источников преимущества и помехи (для строки броска)
    advantage_from: list[str] = Field(default_factory=list)
    disadvantage_from: list[str] = Field(default_factory=list)
    dc: int | None = None
    outcome: str | None = None
    rerolls: list[str] = Field(default_factory=list)
    tags: dict[str, bool | int | str] = Field(default_factory=dict)
    log: RollLogEntry


class KeptPair:
    # кости d20 одного броска: одна (обычный) или две (преимущество/помеха)
    def __init__(self, dice, advantage, extra=0):
        self.dice = list(dice)
        self.advantage = advantage
        # сумма всего, кроме d20 (бонус и члены источников): для решения о перебросе
        self.extra = extra
        # все выпавшие грани по порядку (с перебросами)
        self.rolled = list(dice)
        # переброс: (id, выпавшая грань)
        self.steps = []

    @property
    def natural(self) -> int:
        if self.advantage == "advantage":
            return max(self.dice)
        if self.advantage == "disadvantage":
            return min(self.dice)
        return self.dice[0]


def reroll_kept(kept_pair, rng, reroll_id) -> int:
    # заменяет кость, давшую natural (при равенстве -- первую); возвращает новый natural
    index = kept_pair.dice.index(kept_pair.natural)
    face = rng.d(20)
    kept_pair.dice[index] = face
    kept_pair.rolled.append(face)
    kept_pair.steps.append((reroll_id, face))
    return kept_pair.natural


def luck(request, kept_pair, rng, registry, decisions) -> str | None:
    # Luck (полурослик): 1 на к20-тесте перебрасывается
    luck_trait = luck_id(request, registry)
    if luck_trait is None or kept_pair.natural != 1:
        return None
    reroll_kept(kept_pair, rng, luck_trait)
    return luck_trait


def heroic_inspiration(request, kept_pair, rng, registry, decisions) -> str | None:
    actor = request.actor
    if not is_hero(actor) or not actor.heroic_inspiration or decisions is None:
        return None
    natural = kept_pair.natural
    total = natural + kept_pair.extra
    ctx = {"kind": request.kind, "natural": natural, "total": total, "dc": request.dc}
    if decisions.choose(["reroll", "keep"], ctx) != "reroll":
        return None
    reroll_kept(kept_pair, rng, "heroic_inspiration")
    actor.heroic_inspiration = False
    return "heroic_inspiration"


REROLLERS = [luck, heroic_inspiration]


def roll(
    request, rng, registry, *, modifiers=None, decisions=None, rerollers=None
) -> RollResult:
    if request.kind not in KINDS:
        raise ValueError(f"неизвестный вид броска: {request.kind!r}")
    if request.kind == "damage":
        return roll_damage_request(request, rng, registry)
    if modifiers is None:
        modifiers = default_modifier_registry()
    if rerollers is None:
        rerollers = REROLLERS
    mods = modifiers.collect(request, registry)
    return roll_d20(request, rng, registry, mods, decisions, rerollers)


def resolve_advantage(request, mods) -> str:
    advantage = request.base_adv == "advantage" or any(m.advantage for m in mods)
    disadvantage = request.base_adv == "disadvantage" or any(m.disadvantage for m in mods)
    if advantage and not disadvantage:
        return "advantage"
    if disadvantage and not advantage:
        return "disadvantage"
    return "normal"


def advantage_labels(request, mods, registry, kind) -> list[str]:
    # подписи источников преимущества (kind="advantage") или помехи без повторов
    result = []
    if request.base_adv == kind and request.base_adv_label:
        result.append(request.base_adv_label)
    for m in mods:
        if not getattr(m, kind):
            continue
        label = m.label or SOURCE_WORDS.get(m.source) or source_label(registry, m.source)
        if label not in result:
            result.append(label)
    return result


def luck_id(request, registry) -> str | None:
    for trait_id, effect in species_effects(request.actor, registry):
        if effect.type == "reroll" and effect.target == "d20_test" and effect.when == "natural_1":
            return trait_id
    return None


def feat_reroll_id(actor, registry, target: str) -> str | None:
    # id черты героя с эффектом-перебросом на данную цель
    if not is_hero(actor):
        return None
    for feat_id in actor.sheet.feats:
        if not registry.has("feat", feat_id):
            continue
        for effect in registry.get("feat", feat_id).effects:
            if effect.type == "reroll" and effect.target == target:
                return feat_id
    return None


def roll_d20(request, rng, registry, mods, decisions, rerollers) -> RollResult:
    advantage = resolve_advantage(request, mods)
    advantage_from = advantage_labels(request, mods, registry, "advantage")
    disadvantage_from = advantage_labels(request, mods, registry, "disadvantage")
    auto_fail = any(m.auto_fail for m in mods)
    dc = request.dc
    if dc is not None:
        dc += sum(m.dc_bonus for m in mods)
    crit_min = min([20] + [m.crit_min for m in mods if m.crit_min is not None])
    kept_pair = None
    natural = None
    extra_terms = []
    rerolls = []
    if not auto_fail:
        count = 1 if advantage == "normal" else 2
        kept_pair = KeptPair([rng.d(20) for _ in range(count)], advantage)
        natural = kept_pair.natural
    # плоские бонусы и кубики источников (кубики после d20)
    for m in mods:
        if m.flat != 0:
            label = source_label(registry, m.source)
            detail = str(abs(m.flat))
            extra_terms.append(RollTerm(source=m.source, value=m.flat, detail=detail, label=label))
        if m.dice is not None and not auto_fail:
            dice_roll = roll_dice(m.dice, rng)
            detail = f"{dice_roll.expr} ({dice_roll.total})"
            label = source_label(registry, m.source)
            extra_terms.append(
                RollTerm(source=m.source, value=dice_roll.total, detail=detail, label=label)
            )
    if kept_pair is not None and request.kind in D20_KINDS:
        kept_pair.extra = request.bonus + sum(t.value for t in extra_terms)
        for reroller in rerollers:
            reroll_id = reroller(request, kept_pair, rng, registry, decisions)
            if reroll_id is not None:
                rerolls.append(reroll_id)
        natural = kept_pair.natural
    d20_rolls = []
    if kept_pair is not None:
        d20_rolls = kept_pair.rolled
    terms = []
    if natural is not None:
        terms.append(RollTerm(source="d20", value=natural))
    terms += bonus_terms(request)
    terms += extra_terms
    total = sum(t.value for t in terms)
    outcome = d20_outcome(request, dc, natural, total, auto_fail, mods, crit_min)
    # снимаем использованные эффекты (Sap, Vex) у бросающего и у цели
    holders = [creature_of(request.actor)]
    if request.target is not None:
        holders.append(creature_of(request.target))
    for creature in holders:
        for m in mods:
            if m.consumes is not None:
                creature.active_effects[:] = [
                    e for e in creature.active_effects if e is not m.consumes
                ]
    steps = []
    first_dice = None
    if kept_pair is not None:
        steps = kept_pair.steps
        first_dice = kept_pair.rolled[:len(kept_pair.dice)]
    return RollResult(
        kind=request.kind,
        terms=terms,
        total=total,
        natural=natural,
        d20_rolls=d20_rolls,
        advantage=advantage,
        advantage_from=advantage_from,
        disadvantage_from=disadvantage_from,
        dc=dc,
        outcome=outcome,
        rerolls=rerolls,
        tags=dict(request.tags),
        log=RollLogEntry(
            text=d20_log(
                request, dc, terms, first_dice, steps, natural, total, outcome,
                advantage_from, disadvantage_from,
            )
        ),
    )


def source_label(registry, source) -> str:
    # подпись слагаемого от источника-модификатора: название заклинания/умения/черты или сам id
    for kind in ("spell", "feature", "feat"):
        if registry.has(kind, source):
            return registry.get(kind, source).name
    return source


def bonus_terms(request) -> list[RollTerm]:
    # бонус запроса по слагаемым; нулевые не печатаются; без раскладки -- одним слагаемым
    parts = request.bonus_parts
    if not parts and request.bonus != 0:
        label = ""
        if request.kind == "attack":
            label = "бонус атаки"
        parts = [(label, request.bonus)]
    return [
        RollTerm(source="bonus", value=value, detail=str(abs(value)), label=label)
        for label, value in parts if value != 0
    ]


def d20_outcome(request, dc, natural, total, auto_fail, mods, crit_min) -> str | None:
    if dc is None:
        return None
    if request.kind == "attack":
        if auto_fail or natural == 1:
            return "miss"
        if natural >= crit_min:
            return "crit"
        if total < dc:
            return "miss"
        if any(m.auto_crit for m in mods):
            return "crit"
        return "hit"
    if auto_fail:
        return "fail"
    if total >= dc:
        return "success"
    return "fail"


def roll_title(request) -> str:
    # что именно бросается: «Выживание (Мдр)», «Проверка Сил», «Спасбросок Тел»
    short = ABILITY_SHORT.get(request.ability or "", "")
    if request.kind == "check":
        if request.skill:
            name = SKILL_NAMES.get(request.skill, request.skill)
            return f"{name} ({short})" if short else name
        return f"Проверка {short}" if short else "Проверка"
    if request.kind == "save":
        return f"Спасбросок {short}".strip()
    if request.kind == "attack" and request.label:
        return f"Атака ({request.label})"
    # инициатива и прочее в бою подписываются строкой лога боя
    return ""


def advantage_text(advantage_from, disadvantage_from) -> str:
    # «преим.: высота, скрытно» / «помеха: ниже цели» / гашение «(высота / яд)»
    if advantage_from and disadvantage_from:
        both = " / ".join(advantage_from + disadvantage_from)
        return f"преимущество и помеха гасят друг друга ({both})"
    if advantage_from:
        return "преим.: " + ", ".join(advantage_from)
    if disadvantage_from:
        return "помеха: " + ", ".join(disadvantage_from)
    return ""


def d20_log(
    request, dc, terms, first_dice, steps, natural, total, outcome,
    advantage_from=None, disadvantage_from=None,
) -> str:
    title = roll_title(request)
    prefix = f"{title}: " if title else ""
    if natural is None:
        text = "автопровал"
    else:
        shown = ", ".join(str(n) for n in first_dice)
        for reroll_id, face in steps:
            shown += f" → {REROLL_WORDS.get(reroll_id, reroll_id)} {face}"
        if len(first_dice) > 1:
            shown += f" → {natural}"
        note = advantage_text(advantage_from or [], disadvantage_from or [])
        if note and len(first_dice) > 1:
            shown += f", {note}"
        elif note:
            # преимущество и помеха погасили друг друга: кость одна
            shown += f"; {note}"
        text = f"d20 ({shown})"
        for term in terms:
            if term.source == "d20":
                continue
            sign = "-" if term.value < 0 else "+"
            text += f" {sign} {term.detail}"
            if term.label:
                text += f" {term.label}"
        text += f" = {total}"
    if outcome is not None:
        label = "КД" if request.kind == "attack" else "СЛ"
        note = ""
        if request.dc_note:
            note = f" ({request.dc_note})"
        text += f" против {label} {dc}{note} → {OUTCOME_WORDS[outcome]}"
    return prefix + text


def damage_log_text(
    rolled, bonus, crit, other=None, tag=None, parts=None, label="", damage_type=""
) -> str:
    # Урон (длинный лук): 1d8 (5) + 4 Лов = 9 колющий; Метка охотника: 1d6 (3) силовой;
    # Savage: Урон: 1d8 (2 | 6 → 6) + 3 = 9 [savage_attacker]
    faces = ", ".join(str(n) for n in rolled.rolls)
    total = rolled.total
    if other is not None:
        other_faces = ", ".join(str(n) for n in other.rolls)
        chosen = rolled if rolled.total >= other.total else other
        total = chosen.total
        chosen_faces = ", ".join(str(n) for n in chosen.rolls)
        faces = f"{faces} | {other_faces} → {chosen_faces}"
    if not parts and bonus != 0:
        parts = [("", bonus)]
    text = f"{rolled.expr} ({faces})"
    shown = 0
    for part_label, value in parts or []:
        if value == 0:
            continue
        shown += 1
        sign = "-" if value < 0 else "+"
        text += f" {sign} {abs(value)}"
        if part_label:
            text += f" {part_label}"
    if shown > 0 or other is not None or len(rolled.rolls) > 1:
        text += f" = {total}"
    text = f"{label}: {text}" if label else f"Урон: {text}"
    if damage_type:
        text += f" {DAMAGE_TYPE_WORDS.get(damage_type, damage_type)}"
    if crit:
        text += " (крит, кубики ×2)"
    if tag is not None:
        text += f" [{tag}]"
    return text


def roll_damage_request(request, rng, registry) -> RollResult:
    if request.dice is None:
        raise ValueError("для броска урона нужен dice")
    crit = bool(request.tags.get("crit", False))
    rolled = roll_damage_dice(request.dice, request.bonus, rng, crit=crit)
    rerolls = []
    other = None
    tag = None
    # Savage Attacker: кубики оружия бросаются дважды, берётся больший набор.
    # Флаг tags["savage_attacker_used"] («раз в ход») ставит вызывающий по result.rerolls.
    feat_id = feat_reroll_id(request.actor, registry, "weapon_damage")
    if (
        feat_id is not None
        and request.tags.get("weapon")
        and not request.tags.get("savage_attacker_used")
    ):
        other = roll_damage_dice(request.dice, request.bonus, rng, crit=crit)
        rerolls.append(feat_id)
        tag = feat_id
    total = rolled.total
    if other is not None and other.total > total:
        total = other.total
    terms = [
        RollTerm(source="dice", value=total - request.bonus),
        RollTerm(source="bonus", value=request.bonus),
    ]
    text = damage_log_text(
        rolled, request.bonus, crit, other, tag and source_label(registry, tag),
        request.bonus_parts, request.label, request.damage_type,
    )
    return RollResult(
        kind="damage",
        terms=terms,
        total=total,
        rerolls=rerolls,
        tags=dict(request.tags),
        log=RollLogEntry(text=text),
    )
