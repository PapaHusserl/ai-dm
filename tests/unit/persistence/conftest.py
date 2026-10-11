# Фикстуры сейва: `saves` -- корень сохранений во временном каталоге (внутри <world_id>/slots/...),
# `bundle` -- полный бандл (мир с NPC / триггерами / флагами / событием / тоном, два героя с
# кириллическими именами), `empty_bundle` -- бандл с пустыми pantheon, memory, chronicle,
# events и без героев. manifest у обоих согласован: schema_version=CURRENT_SCHEMA_VERSION,
# slot="auto", saved_at="2026-01-01T12:00:00Z", heroes -- id героев по порядку.
import pytest

from ai_dm.core.rng import Rng
from ai_dm.persistence.migrations import CURRENT_SCHEMA_VERSION
from ai_dm.state.creature import CreatureState
from ai_dm.state.hero import BackgroundSpec, CharacterSheet, ClassLevel, HeroState, InventoryEntry
from ai_dm.state.memory import Chronicle, Memory
from ai_dm.state.save import Manifest, SaveBundle
from ai_dm.state.session import SessionState
from ai_dm.state.world import NPC, GlobalEvent, Tone, WorldState


def make_hero(hero_id, ordinal, name):
    sheet = CharacterSheet(
        species_id="human",
        classes=[ClassLevel(class_id="fighter")], level_history=["fighter"] * 1,
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
        id=hero_id, ordinal=ordinal, name=name, sheet=sheet,
        creature=CreatureState(hp_current=12, hp_max=12),
        inventory=[InventoryEntry(item_id="longsword", qty=1, cost_cp=0)],
        money_cp=1235,
    )


def make_world():
    npc = NPC.model_validate(
        {
            "id": "mentor_aldric",
            "name": "Олдрик",
            "named": True,
            "key": True,
            "means": ["магия крови", "долг гильдии воров"],
            "motive": "спасти сестру",
            "attitude": 20,
            "opportunity": [
                {
                    "id": "steal_grail",
                    "if": {
                        "all": [
                            {"hero_has": "blood_grail"},
                            {"npc_status": {"id": "mentor_aldric", "is": "alive"}},
                        ]
                    },
                    "then": "выкрадет Грааль",
                    "once": True,
                },
            ],
            "secrets": [
                {"id": "sister_vampire", "text": "сестра -- вампир", "reveal_if": {"flag": "found"}}
            ],
        }
    )
    world = WorldState(world_id="w1", campaign_id="vale", rng=Rng(7).state)
    world.npcs[npc.id] = npc
    world.flags["met_aldric"] = True
    world.events.append(GlobalEvent(id="grey_plague", type="plague", regions=["port_vale"]))
    world.tone = Tone(mood="мрачный", violence="реалистично", hard_limits=["насилие над детьми"])
    return world


def make_manifest(heroes, current):
    return Manifest(
        schema_version=CURRENT_SCHEMA_VERSION,
        engine_version="0.1.0",
        world_id="w1",
        campaign_id="vale",
        slot="auto",
        saved_at="2026-01-01T12:00:00Z",
        current_hero_id=current,
        heroes=heroes,
    )


@pytest.fixture
def saves(tmp_path):
    return tmp_path / "saves"


@pytest.fixture
def bundle():
    return SaveBundle(
        manifest=make_manifest(["h1", "h2"], "h1"),
        world=make_world(),
        chronicle=Chronicle(),
        memory=Memory(),
        heroes=[make_hero("h1", 1, "Арн"), make_hero("h2", 2, "Бранка Рыжая")],
        session=SessionState(),
    )


@pytest.fixture
def empty_bundle():
    return SaveBundle(
        manifest=make_manifest([], None),
        world=WorldState(world_id="w1", campaign_id="vale", rng=Rng(1).state),
        chronicle=Chronicle(),
        memory=Memory(),
        heroes=[],
        session=SessionState(),
    )
