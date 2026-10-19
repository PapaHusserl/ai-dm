import re
from pathlib import Path

import yaml
from pydantic import ValidationError

from ai_dm.campaign.models import (
    CampaignManifest,
    HeroPreset,
    Pack,
    StartChronicle,
    StartMemory,
)
from ai_dm.campaign.presets import PACK_TONE, load_presets
from ai_dm.config.settings import load_rules_config
from ai_dm.core.clock import GameClock
from ai_dm.rules.builder import (
    ValidationErrors,
    build_character,
    means_problems,
    opportunity_problems,
)
from ai_dm.rules.inventory import find_item
from ai_dm.rules.triggers_eval import KnownIds
from ai_dm.state.triggers import (
    AllOf,
    AnyOf,
    Attitude,
    Favor,
    HeroAt,
    HeroHas,
    NotOf,
    NpcAt,
    NpcStatus,
)
from ai_dm.state.world import NPC, Faction, GlobalEvent, God, Location

CAMPAIGNS_DIR = Path(__file__).resolve().parents[3] / "campaigns"

# файл -> модель записи
LIST_FILES = {
    "npcs.yaml": NPC,
    "factions.yaml": Faction,
    "pantheon.yaml": God,
    "locations.yaml": Location,
    "events.yaml": GlobalEvent,
}
CAUSE_RE = re.compile(r"trigger:([^:]+):([^:]+)")


class PackError(Exception):
    def __init__(self, lines):
        super().__init__("\n".join(lines))
        self.lines = list(lines)


def pack_content_dir(path) -> Path | None:
    # слой контента пака для load_registry([...]) или None
    folder = Path(path) / "content"
    if folder.is_dir():
        return folder
    return None


def validation_lines(path, err, prefix="") -> list[str]:
    lines = []
    for e in err.errors():
        field = ".".join(str(part) for part in e["loc"])
        text = e["msg"]
        if e["type"] == "literal_error":
            text += f" (получено: {e['input']!r})"
        lines.append(f"{path}: {prefix}поле {field or '-'}: {text}")
    return lines


def read_yaml(path, errors):
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as err:
        errors.append(f"{path}: некорректный YAML: {err}")
    return None


def read_model(path, model, errors):
    errors_before = len(errors)
    data = read_yaml(path, errors)
    if len(errors) > errors_before:
        return None
    if not isinstance(data, dict):
        errors.append(f"{path}: ожидался один объект (mapping) на файл")
        return None
    try:
        return model.model_validate(data)
    except ValidationError as err:
        errors.extend(validation_lines(path, err))
    return None


def read_list(path, model, errors) -> list:
    if not path.is_file():
        return []
    data = read_yaml(path, errors)
    if data is None:
        return []
    if not isinstance(data, list):
        errors.append(f"{path}: ожидался список")
        return []
    items = []
    for number, item in enumerate(data):
        try:
            items.append(model.model_validate(item))
        except ValidationError as err:
            name = item.get("id", "?") if isinstance(item, dict) else "?"
            errors.extend(validation_lines(path, err, f"запись {number} ({name}), "))
    return items


def condition_refs(condition) -> list[tuple[str, str]]:
    # (вид цели, id): npc, location, god, item
    refs = []
    if isinstance(condition, (AllOf, AnyOf)):
        for item in condition.items:
            refs += condition_refs(item)
    elif isinstance(condition, NotOf):
        refs += condition_refs(condition.item)
    elif isinstance(condition, NpcStatus):
        refs.append(("npc", condition.id))
    elif isinstance(condition, NpcAt):
        refs += [("npc", condition.id), ("location", condition.at)]
    elif isinstance(condition, Attitude):
        refs.append(("npc", condition.npc))
    elif isinstance(condition, HeroAt):
        refs.append(("location", condition.location))
    elif isinstance(condition, Favor):
        refs.append(("god", condition.god))
    elif isinstance(condition, HeroHas):
        refs.append(("item", condition.item))
    return refs


def trigger_refs(triggers) -> list[tuple[str, str, str]]:
    refs = []
    for trigger in triggers:
        for kind, ref in condition_refs(trigger.if_):
            refs.append((f"opportunity[{trigger.id}].if", kind, ref))
    return refs


def entity_refs(kind, entity) -> list[tuple[str, str, str]]:
    # ссылки сущности пака: (поле, вид цели, id); kind: location, god, faction, npc, event
    refs = []
    if kind == "location":
        if entity.parent_id is not None:
            refs.append(("parent_id", "location", entity.parent_id))
        for connection in entity.connections:
            refs.append(("connections", "location", connection.to))
    elif kind == "god":
        refs += [("rivals", "god", ref) for ref in entity.rivals]
        refs += [("servants", "npc", ref) for ref in entity.servants]
        refs += trigger_refs(entity.opportunity)
    elif kind == "faction":
        refs += [("members", "npc", ref) for ref in entity.members]
        refs += [("regions", "location", ref) for ref in entity.regions]
        refs += trigger_refs(entity.opportunity)
    elif kind == "npc":
        if entity.location_id is not None:
            refs.append(("location_id", "location", entity.location_id))
        if entity.species_id is not None:
            refs.append(("species_id", "species", entity.species_id))
        refs += trigger_refs(entity.opportunity)
        for secret in entity.secrets:
            for target, ref in condition_refs(secret.reveal_if):
                refs.append((f"secrets[{secret.id}].reveal_if", target, ref))
    elif kind == "event":
        refs += [("regions", "location", ref) for ref in entity.regions]
        if entity.ends_when is not None:
            for target, ref in condition_refs(entity.ends_when):
                refs.append(("ends_when", target, ref))
    return refs


def ref_exists(target, ref, known, registry) -> bool:
    if target == "item":
        return find_item(registry, ref) is not None
    if target == "species":
        return registry.has("species", ref)
    return ref in known[target]


def check_pack_refs(pack, registry) -> list[str]:
    known = {
        "npc": {npc.id for npc in pack.npcs},
        "god": {god.id for god in pack.pantheon},
        "location": {location.id for location in pack.locations},
    }
    base = Path(pack.path)
    groups = [
        ("location", "locations.yaml", pack.locations),
        ("god", "pantheon.yaml", pack.pantheon),
        ("faction", "factions.yaml", pack.factions),
        ("npc", "npcs.yaml", pack.npcs),
        ("event", "events.yaml", pack.events),
    ]
    errors = []
    for kind, file, entities in groups:
        for entity in entities:
            for field, target, ref in entity_refs(kind, entity):
                if not ref_exists(target, ref, known, registry):
                    errors.append(
                        f"{base / file}: {kind} {entity.id!r}, поле {field}: "
                        f"неизвестный {target} {ref!r}"
                    )
    presets = load_rules_config().trade.presets
    for npc in pack.npcs:
        if npc.trade is not None and npc.trade.kind not in presets:
            errors.append(
                f"{base / 'npcs.yaml'}: npc {npc.id!r}, поле trade.kind: "
                f"неизвестный пресет торговца {npc.trade.kind!r}"
            )
    owners = {}
    for npc in pack.npcs:
        owners[npc.id] = npc.opportunity
    for faction in pack.factions:
        owners[faction.id] = faction.opportunity
    for god in pack.pantheon:
        owners[god.id] = god.opportunity
    for event in pack.events:
        m = CAUSE_RE.fullmatch(event.cause or "")
        if m is not None and not any(t.id == m.group(2) for t in owners.get(m.group(1), [])):
            errors.append(
                f"{base / 'events.yaml'}: event {event.id!r}, поле cause: "
                f"нет триггера {event.cause!r}"
            )
    return errors


def pack_npc_trade(pack_dir, registry) -> dict[str, str] | None:
    # id NPC пака -> пресет торговца: для миграции сейва; None -- пак не загрузился
    if pack_dir is None:
        return {}
    try:
        pack = load_pack(pack_dir, registry)
    except PackError:
        return None
    return {npc.id: npc.trade.kind for npc in pack.npcs if npc.trade is not None}


def pack_monster_scope(pack_dir) -> list[str] | None:
    # список monsters из campaign.yaml; None -- нет файла, невалиден или список пуст (без фильтра)
    path = Path(pack_dir) / "campaign.yaml"
    if not path.is_file():
        return None
    manifest = read_model(path, CampaignManifest, [])
    if manifest is None or not manifest.monsters:
        return None
    return manifest.monsters


def check_manifest_monsters(pack, registry) -> list[str]:
    path = Path(pack.path)
    monsters = pack.manifest.monsters
    errors = []
    for monster_id in monsters:
        if not registry.has("monster", monster_id):
            errors.append(
                f"{path / 'campaign.yaml'}: поле monsters: неизвестный монстр {monster_id!r}"
            )
    if not monsters:
        return errors
    for npc in pack.npcs:
        if npc.combat is not None and npc.combat["monster_id"] not in monsters:
            errors.append(
                f"{path / 'npcs.yaml'}: NPC {npc.id!r}, поле combat.monster_id: "
                f"монстр {npc.combat['monster_id']!r} вне списка monsters в campaign.yaml"
            )
    return errors


def check_manifest(pack, registry) -> list[str]:
    manifest = pack.manifest
    path = Path(pack.path)
    errors = []
    calendar = manifest.calendar
    try:
        GameClock.from_date(manifest.start.date, calendar)
    except ValueError as err:
        errors.append(f"{path / 'campaign.yaml'}: поле start.date: {err}")
    locations = {location.id for location in pack.locations}
    if manifest.start.hero_location not in locations:
        errors.append(
            f"{path / 'campaign.yaml'}: поле start.hero_location: "
            f"неизвестная локация {manifest.start.hero_location!r}"
        )
    preset_ids = [preset.id for preset in pack.heroes]
    for hero_id in manifest.start.heroes:
        if hero_id not in preset_ids:
            errors.append(
                f"{path / 'campaign.yaml'}: поле start.heroes: нет пресета героя {hero_id!r}"
            )
    if manifest.preset and manifest.preset not in [*load_presets(), PACK_TONE]:
        errors.append(
            f"{path / 'campaign.yaml'}: поле preset: неизвестный пресет {manifest.preset!r}"
        )
    gods = {god.id for god in pack.pantheon}
    if calendar is not None:
        for holiday in calendar.holidays:
            if holiday.god_id is not None and holiday.god_id not in gods:
                errors.append(
                    f"{path / 'campaign.yaml'}: поле calendar.holidays: "
                    f"праздник {holiday.name!r}, неизвестный бог {holiday.god_id!r}"
                )
    for kind in manifest.natural_events.kinds:
        for region in kind.regions:
            if region not in locations:
                errors.append(
                    f"{path / 'campaign.yaml'}: поле natural_events.kinds: "
                    f"{kind.type!r}, неизвестная локация {region!r}"
                )
    return errors + check_manifest_monsters(pack, registry)


def check_hero(pack, preset, registry) -> list[str]:
    where = Path(pack.path) / "heroes" / f"{preset.id}.yaml"
    errors = []
    built = build_character(preset.choices, registry)
    if isinstance(built, ValidationErrors):
        errors += [f"{where}: поле choices: {message}" for message in built.messages]
    for entry in preset.inventory_extra:
        if find_item(registry, entry.item_id) is None:
            errors.append(f"{where}: поле inventory_extra: неизвестный предмет {entry.item_id!r}")
    locations = {location.id for location in pack.locations}
    if preset.location_id is not None and preset.location_id not in locations:
        errors.append(f"{where}: поле location_id: неизвестная локация {preset.location_id!r}")
    gods = {god.id for god in pack.pantheon}
    if preset.deity_id is not None and preset.deity_id not in gods:
        errors.append(f"{where}: поле deity_id: неизвестный бог {preset.deity_id!r}")
    for god_id in preset.favor:
        if god_id not in gods:
            errors.append(f"{where}: поле favor: неизвестный бог {god_id!r}")
    if preset.means:
        for _, text in means_problems(preset.means):
            errors.append(f"{where}: поле means: {text}")
    # known собирается здесь: campaign.build.known_ids импортировать нельзя (цикл через uniqueness)
    known = KnownIds(
        npcs={npc.id for npc in pack.npcs}, locations=locations, pantheon=gods,
    )
    for _, text in opportunity_problems(preset, known, registry):
        errors.append(f"{where}: поле opportunity: {text}")
    if preset.birth_date is not None:
        try:
            GameClock.from_date(preset.birth_date, pack.manifest.calendar)
        except ValueError as err:
            errors.append(f"{where}: поле birth_date: {err}")
    return errors


def load_pack(path, registry) -> Pack:
    # читает и проверяет пак; ошибки -- PackError со строками «файл: поле: что не так»
    path = Path(path)
    errors = []
    if not path.is_dir():
        raise PackError([f"{path}: нет каталога пака"])
    manifest = None
    if (path / "campaign.yaml").is_file():
        manifest = read_model(path / "campaign.yaml", CampaignManifest, errors)
    else:
        errors.append(f"{path / 'campaign.yaml'}: нет обязательного файла")
    if not (path / "world.md").is_file():
        errors.append(f"{path / 'world.md'}: нет обязательного файла")
    lists = {}
    for file, model in LIST_FILES.items():
        lists[file] = read_list(path / file, model, errors)
    heroes = []
    if (path / "heroes").is_dir():
        for hero_path in sorted((path / "heroes").glob("*.yaml")):
            preset = read_model(hero_path, HeroPreset, errors)
            if preset is not None:
                if preset.id != hero_path.stem:
                    errors.append(f"{hero_path}: поле id: ожидалось {hero_path.stem!r}")
                heroes.append(preset)
    start_memory = StartMemory()
    if (path / "start" / "memory.yaml").is_file():
        start_memory = read_model(path / "start" / "memory.yaml", StartMemory, errors)
    start_chronicle = StartChronicle()
    if (path / "start" / "chronicle.yaml").is_file():
        start_chronicle = read_model(path / "start" / "chronicle.yaml", StartChronicle, errors)
    if errors or manifest is None:
        raise PackError(errors)
    truths = ""
    if (path / "truths.md").is_file():
        truths = (path / "truths.md").read_text(encoding="utf-8")
    content_dir = pack_content_dir(path)
    pack = Pack(
        path=str(path),
        manifest=manifest,
        world_text=(path / "world.md").read_text(encoding="utf-8").strip(),
        truths=truths.strip(),
        npcs=lists["npcs.yaml"],
        factions=lists["factions.yaml"],
        pantheon=lists["pantheon.yaml"],
        locations=lists["locations.yaml"],
        events=lists["events.yaml"],
        heroes=heroes,
        start_memory=start_memory,
        start_chronicle=start_chronicle,
        content_dir=None if content_dir is None else str(content_dir),
    )
    errors = check_manifest(pack, registry) + check_pack_refs(pack, registry)
    for preset in heroes:
        errors += check_hero(pack, preset, registry)
    if errors:
        raise PackError(errors)
    if not pack.manifest.start.heroes:
        pack.manifest.start.heroes = [preset.id for preset in heroes]
    return pack
