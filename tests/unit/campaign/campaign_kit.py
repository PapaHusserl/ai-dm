# Общие помощники тестов слоя campaign (этап 3, партия 1). Не фикстуры pytest, а функции.
# Мини-пак собирается во временном каталоге из питоновских словарей (YAML пишется на лету),
# чтобы каждый тест ломал ровно одну деталь.
#
# Ожидаемый API (STAGE3-PLAN A2, models.py уже есть у кабана):
#   ai_dm.campaign.loader.load_pack(path, registry) -> Pack; при ошибке -- PackError с .lines
#       (список строк: файл, поле, причина); возвращён он или поднят -- helper pack_errors
#       понимает оба варианта.
#   ai_dm.campaign.uniqueness.collect_conflicts(world, heroes, pack) -> (accepted, conflicts);
#       accepted -- объект со списками locations / pantheon / factions / npcs (как у Pack);
#       conflict.file / .kind / .id / .name / .reason.
#   ai_dm.campaign.merge.merge_new(bundle, pack) -> report: .added (список), .conflicts (список)
from pathlib import Path

import yaml

from ai_dm.campaign.presets import SHIPPED_DIR
from ai_dm.core.rng import Rng
from ai_dm.state.memory import Chronicle, Memory
from ai_dm.state.save import Manifest, SaveBundle
from ai_dm.state.session import SessionState
from ai_dm.state.world import WorldState

ROOT = Path(__file__).resolve().parents[3]
VALE_DIR = SHIPPED_DIR / "vale"
SAVED_AT = "2026-01-01T12:00:00Z"


def arn_choices():
    return {
        "name": "Арн", "species_id": "human", "class_id": "fighter", "background": "soldier",
        "ability_method": "standard_array",
        "ability_scores": {"str": 15, "dex": 13, "con": 14, "int": 8, "wis": 10, "cha": 12},
        "background_bonus": {"str": 2, "con": 1},
        "class_skills": ["perception", "survival"],
        "weapon_masteries": ["longsword", "greatsword", "shortsword"],
        "fighting_style": "defense",
        "inventory": ["chain_mail", "shield", "longsword"],
        "equip": ["chain_mail", "shield", "longsword"],
        "species_choices": {"skill": "stealth", "feat": "skilled"},
        "feat_choices": {"skilled": ["medicine", "religion", "nature"]},
        "hero_id": "hero",
    }


def default_files():
    # три локации, бог, фракция, два NPC (Олдрик с триггером и секретом), один пресет героя
    return {
        "campaign.yaml": {
            "id": "mini", "name": "Мини", "version": "1.0",
            "start": {"date": "0100-03-01", "hero_location": "tavern", "heroes": ["arn"]},
        },
        "world.md": "Мини-мир: город с таверной и подвалом.\n",
        "truths.md": "Подвал всегда сырой.\n",
        "locations.yaml": [
            {"id": "town", "name": "Город", "connections": [{"to": "tavern", "distance_m": 100}]},
            {"id": "tavern", "name": "Таверна", "parent_id": "town",
             "connections": [{"to": "cellar", "distance_m": 10}]},
            {"id": "cellar", "name": "Подвал", "parent_id": "tavern"},
        ],
        "pantheon.yaml": [
            {"id": "selune", "name": "Селунэ", "rivals": []},
        ],
        "factions.yaml": [
            {"id": "guild", "name": "Гильдия воров", "members": ["aldric"], "regions": ["town"]},
        ],
        "npcs.yaml": [
            {"id": "aldric", "name": "Олдрик", "named": True, "key": True,
             "location_id": "tavern", "species_id": "human", "means": ["связи"],
             "opportunity": [{"id": "steal", "if": {"flag": "grail_seen"}, "then": "крадёт",
                              "once": True}],
             "secrets": [{"id": "sister", "text": "сестра в беде",
                          "reveal_if": {"flag": "found"}}]},
            {"id": "guard", "name": "Стражник", "named": False, "location_id": "town",
             "means": ["меч"]},
        ],
        "heroes/arn.yaml": {"id": "arn", "choices": arn_choices(), "location_id": "tavern"},
    }


def write_pack(root, files=None):
    # value None -- файл не создаётся; str -- пишется как есть; иначе -- YAML
    if files is None:
        files = default_files()
    pack_dir = Path(root) / "mini"
    for name, value in files.items():
        if value is None:
            continue
        path = pack_dir / name
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(value, str):
            path.write_text(value, encoding="utf-8")
        else:
            path.write_text(yaml.safe_dump(value, allow_unicode=True), encoding="utf-8")
    return pack_dir


def load(path, registry):
    from ai_dm.campaign.loader import load_pack

    return load_pack(path, registry)


def pack_errors(path, registry):
    # строки ошибок пака или None, если пак загрузился
    from ai_dm.campaign.loader import PackError, load_pack

    try:
        result = load_pack(path, registry)
    except PackError as err:
        return list(err.lines)
    if isinstance(result, PackError):
        return list(result.lines)
    return None


def text_of(lines):
    return "\n".join(lines)


def empty_world(world_id="w1"):
    return WorldState(world_id=world_id, rng=Rng(1).state)


def world_from_pack(pack, world_id="w1"):
    # мир со всеми сущностями пака, как после создания нового мира без конфликтов
    world = empty_world(world_id)
    world.campaign_id = pack.manifest.id
    world.campaign_version = pack.manifest.version
    world.lore.world_text = pack.world_text
    world.lore.truths = pack.truths
    for kind in ("locations", "pantheon", "factions", "npcs"):
        for entity in getattr(pack, kind):
            getattr(world, kind)[entity.id] = entity.model_copy(deep=True)
    return world


def bundle_from_world(world):
    manifest = Manifest(
        schema_version=3, engine_version="0.1.0", world_id=world.world_id,
        campaign_id=world.campaign_id, slot="auto", saved_at=SAVED_AT, current_hero_id=None,
        heroes=[],
    )
    return SaveBundle(
        manifest=manifest, world=world, chronicle=Chronicle(), memory=Memory(), heroes=[],
        session=SessionState(),
    )


def ids(entities):
    return [e.id for e in entities]
