from ai_dm.protocol.decision import Decision, Invalid
from ai_dm.protocol.handlers.hero import condition_from_spec


def filled(data) -> dict:
    # только заданные поля: None, пустые строки и пустые списки в файл не попадают
    return {key: value for key, value in data.items() if value not in (None, "", [])}


def trigger_data(spec) -> dict:
    return {"id": spec.id, "if": condition_from_spec(spec), "then": spec.then, "once": True}


def secret_data(spec) -> dict:
    return {"id": spec.id, "text": spec.text, "reveal_if": condition_from_spec(spec)}


def location_data(location) -> dict:
    connections = [{"to": c.to, "distance_m": c.distance_m} for c in location.connections]
    return filled({
        "id": location.id, "name": location.name, "parent_id": location.parent_id,
        "description": location.description, "connections": connections,
    })


def npc_data(npc) -> dict:
    data = {"id": npc.id, "name": npc.name, "named": npc.named, "key": npc.key}
    trade = None
    if npc.trade_kind is not None:
        trade = {"kind": npc.trade_kind}
    data.update(filled({
        "motive": npc.motive, "means": list(npc.means),
        "opportunity": [trigger_data(t) for t in npc.opportunity],
        "secrets": [secret_data(s) for s in npc.secrets],
        "location_id": npc.location_id, "species_id": npc.species_id, "trade": trade,
        "gender": npc.gender, "pronouns": npc.pronouns,
    }))
    return data


def faction_data(faction) -> dict:
    return filled({
        "id": faction.id, "name": faction.name, "motive": faction.motive,
        "means": list(faction.means), "opportunity": [trigger_data(t) for t in faction.opportunity],
        "members": list(faction.members), "regions": list(faction.regions),
    })


def god_data(god) -> dict:
    return filled({
        "id": god.id, "name": god.name, "domains": list(god.domains), "role": god.role,
        "motive": god.motive, "pleased_by": list(god.pleased_by),
        "angered_by": list(god.angered_by), "rivals": list(god.rivals),
        "means": list(god.means), "opportunity": [trigger_data(t) for t in god.opportunity],
        "realm": god.realm, "servants": list(god.servants),
    })


def tone_data(tone) -> dict:
    return filled(tone.model_dump())


def manifest_data(request, campaign_id) -> dict:
    # id и версию манифеста ставит движок, модель их не выдаёт
    start = request.start
    chapter = filled({"number": start.chapter_number, "title": start.chapter_title})
    return {
        "id": campaign_id, "name": request.name, "version": "1",
        "start": filled({
            "date": start.date, "time": start.time, "hero_location": start.hero_location,
            "chapter": chapter, "scene_summary": start.scene_summary,
        }),
        "tone": tone_data(request.tone),
    }


def files_from_request(request, campaign_id) -> dict:
    # имя файла пака -> содержимое (словарь, текст или список записей)
    return {
        "campaign.yaml": manifest_data(request, campaign_id),
        "world.md": request.world_text,
        "truths.md": request.truths or "",
        "locations.yaml": [location_data(x) for x in request.locations],
        "npcs.yaml": [npc_data(x) for x in request.npcs],
        "factions.yaml": [faction_data(x) for x in request.factions],
        "pantheon.yaml": [god_data(x) for x in request.pantheon],
    }


def pack_spec(ctx, request):
    # пак: ровно один принятый вызов; проверку диском и загрузчиком делает исполнитель слоя game
    if ctx.files is not None:
        return Invalid(code="already_done", message="Пак уже принят.")
    try:
        # ValueError -- от condition_from_spec (порог gte у attitude и favor)
        files = files_from_request(request, ctx.task.campaign_id)
    except ValueError as err:
        return Invalid(code="invalid_request", message=str(err))
    ctx.files = files
    return Decision(status="accepted", log=["Пак принят"])
