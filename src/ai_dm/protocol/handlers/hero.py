from ai_dm.protocol.decision import Decision, Invalid
from ai_dm.rules.builder import (
    CharacterChoices,
    HeroSheet,
    background_check,
    origin_feat_keys,
    sheet_check,
)
from ai_dm.state.hero import BackgroundSpec
from ai_dm.state.triggers import Trigger


def background_spec(ctx, request):
    # свободная предыстория: ровно один принятый вызов, проверки -- общие с build_character
    if ctx.background is not None:
        return Invalid(code="already_done", message="Предыстория уже принята.")
    spec = BackgroundSpec(
        name=request.name, abilities=list(request.abilities), skills=list(request.skills),
        tool=request.tool, feat=request.feat, equipment=list(request.equipment),
        gold_cp=request.gold_cp, gold_option_cp=5000, description=request.description or "",
    )
    codes, messages = background_check(spec, ctx.registry, ctx.task.class_skills)
    if codes:
        return Invalid(code=codes[0], message="; ".join(messages))
    ctx.background = spec
    return Decision(status="accepted", log=["Предыстория принята"])


def condition_from_spec(spec) -> dict:
    # плоское условие инструмента -> короткая запись 4.01
    if spec.kind in ("narrative", "flag", "hero_has", "hero_at"):
        return {spec.kind: spec.ref}
    if spec.kind == "npc_status":
        return {"npc_status": {"id": spec.ref, "is": spec.status or "alive"}}
    if spec.gte is None:
        raise ValueError(f"возможность {spec.id!r}: для {spec.kind} нужен порог gte")
    if spec.kind == "attitude":
        return {"attitude": {"npc": spec.ref, "gte": spec.gte}}
    return {"favor": {"god": spec.ref, "gte": spec.gte}}


def sheet_from_request(request) -> HeroSheet:
    # плоские поля инструмента -> HeroSheet; ошибка разбора -- ValueError
    bonus = {ability: 1 for ability in request.bonus_plus1}
    if request.bonus_plus2 is not None:
        bonus[request.bonus_plus2] = 2
    species_choices = {}
    if request.species_skill is not None:
        species_choices["skill"] = request.species_skill
    if request.species_feat is not None:
        species_choices["feat"] = request.species_feat
    b = request.background
    spec = BackgroundSpec(
        name=b.name, abilities=list(b.abilities), skills=list(b.skills), tool=b.tool,
        feat=b.feat, equipment=list(b.equipment), gold_cp=b.gold_cp, gold_option_cp=5000,
        description=b.description or "",
    )
    feat_choices = {}
    picks = [request.feat_skills, request.species_feat_skills]
    for (key, _), chosen in zip(origin_feat_keys(spec, species_choices), picks, strict=False):
        if chosen:
            feat_choices[key] = list(chosen)
    choices = CharacterChoices(
        name=request.name, gender=request.gender, pronouns=request.pronouns or "",
        species_id=request.species_id, class_id=request.class_id,
        background=spec, ability_method=request.ability_method,
        ability_scores=request.ability_scores.model_dump(by_alias=True),
        background_bonus=bonus, class_skills=list(request.class_skills),
        weapon_masteries=list(request.weapon_masteries), fighting_style=request.fighting_style,
        species_choices=species_choices, spells=list(request.spells),
        prepared=list(request.prepared), feat_choices=feat_choices,
        background_gear=request.background_gear, class_kit=request.class_kit,
    )
    opportunity = [
        Trigger.model_validate(
            {"id": t.id, "if": condition_from_spec(t), "then": t.then, "once": True}
        )
        for t in request.opportunity
    ]
    return HeroSheet(
        choices=choices, motive=request.motive, means=list(request.means), opportunity=opportunity
    )


def trigger_spec(trigger) -> dict:
    # Trigger героя -> плоская возможность инструмента (обратно к condition_from_spec)
    cond = trigger.if_
    spec = {"id": trigger.id, "then": trigger.then, "kind": cond.type, "status": "", "gte": 0}
    if cond.type == "npc_status":
        spec.update(ref=cond.id, status=cond.is_)
    elif cond.type in ("attitude", "favor"):
        spec.update(ref=cond.npc if cond.type == "attitude" else cond.god, gte=cond.gte or 0)
    else:
        fields = {"flag": "name", "hero_has": "item", "hero_at": "location", "narrative": "text"}
        spec["ref"] = getattr(cond, fields[cond.type])
    return spec


def request_from_sheet(sheet) -> dict:
    # HeroSheet -> аргументы инструмента hero_sheet (обратно к sheet_from_request), для previous
    c = sheet.choices
    plus2 = [a for a, n in c.background_bonus.items() if n == 2]
    spec = c.background
    keys = [key for key, _ in origin_feat_keys(spec, c.species_choices)]
    picks = [c.feat_choices.get(key, []) for key in keys] + [[], []]
    return {
        "type": "hero_sheet", "name": c.name, "gender": c.gender or "none",
        "pronouns": c.pronouns, "species_id": c.species_id, "class_id": c.class_id,
        "ability_method": c.ability_method, "ability_scores": dict(c.ability_scores),
        "bonus_plus2": plus2[0] if plus2 else "none",
        "bonus_plus1": [a for a, n in c.background_bonus.items() if n == 1],
        "class_skills": list(c.class_skills), "weapon_masteries": list(c.weapon_masteries),
        "fighting_style": c.fighting_style or "", "class_kit": c.class_kit or "",
        "spells": list(c.spells), "prepared": list(c.prepared),
        "species_skill": c.species_choices.get("skill", "none"),
        "species_feat": c.species_choices.get("feat", ""),
        "feat_skills": list(picks[0]), "species_feat_skills": list(picks[1]),
        "background": {
            "name": spec.name, "abilities": list(spec.abilities), "skills": list(spec.skills),
            "tool": spec.tool, "feat": spec.feat, "equipment": list(spec.equipment),
            "gold_cp": spec.gold_cp, "description": spec.description,
        },
        "background_gear": c.background_gear, "motive": sheet.motive, "means": list(sheet.means),
        "opportunity": [trigger_spec(t) for t in sheet.opportunity],
    }


def hero_sheet(ctx, request):
    # лист героя: ровно один принятый вызов; проверка -- общий sheet_check (как у ручной правки)
    if ctx.sheet is not None:
        return Invalid(code="already_done", message="Лист героя уже принят.")
    try:
        sheet = sheet_from_request(request)
    except ValueError as err:
        return Invalid(code="invalid_request", message=str(err))
    codes, messages = sheet_check(
        sheet, ctx.registry, known=ctx.task.known, taken_names=ctx.task.taken_names
    )
    if codes:
        return Invalid(code=codes[0], message="; ".join(messages))
    ctx.sheet = sheet
    return Decision(status="accepted", log=["Лист героя принят"])
