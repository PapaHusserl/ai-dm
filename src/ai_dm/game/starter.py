import uuid

import yaml

from ai_dm.campaign.build import build_world
from ai_dm.campaign.loader import SHIPPED_DIR, load_pack
from ai_dm.game.scene import start_scene
from ai_dm.rules.builder import CharacterChoices

VALE_DIR = SHIPPED_DIR / "vale"
HEROES = ("arn", "liel", "grey")


def preset_choices(preset_id, hero_id) -> CharacterChoices:
    # выборы героя читаются из пресета пака Вейл
    data = yaml.safe_load((VALE_DIR / "heroes" / f"{preset_id}.yaml").read_text(encoding="utf-8"))
    choices = CharacterChoices.model_validate(data["choices"])
    return choices.model_copy(update={"hero_id": hero_id})


def fighter_choices(hero_id="hero") -> CharacterChoices:
    return preset_choices("arn", hero_id)


def wizard_choices(hero_id="hero") -> CharacterChoices:
    return preset_choices("liel", hero_id)


def ranger_choices(hero_id="hero") -> CharacterChoices:
    return preset_choices("grey", hero_id)


def new_world_from_pack(
    registry, cfg, pack, *, hero, seed, world_id=None, saved_at, conflicts=None,
    preset_id=None, difficulty=None,
):
    # conflicts -- список, в который кладутся конфликты уникальности (не загруженное из пака);
    # отказ старта -- StartRefused
    if world_id is None:
        world_id = f"{pack.manifest.id}-{uuid.uuid4().hex[:8]}"
    bundle, found = build_world(
        pack, cfg, registry, hero_id=hero, seed=seed, world_id=world_id, saved_at=saved_at,
        preset_id=preset_id,
    )
    if conflicts is not None:
        conflicts.extend(found)
    if difficulty is not None:
        bundle.world.settings["difficulty"] = difficulty
    start_scene(bundle)
    summary = pack.manifest.start.scene_summary
    if summary:
        bundle.session.current_scene.summary = summary
    return bundle


def new_world(registry, cfg, *, hero, seed, world_id=None, saved_at):
    # мир Вейла из поставляемого пака vale
    if hero not in HEROES:
        raise ValueError(f"неизвестный герой: {hero!r}")
    pack = load_pack(VALE_DIR, registry)
    return new_world_from_pack(
        registry, cfg, pack, hero=hero, seed=seed, world_id=world_id, saved_at=saved_at
    )
