# Статический мини-пак tests/fixtures/packs/mini/ (STAGE3-PLAN часть C): 3 локации, 4 NPC,
# 1 фракция, 2 бога, событие, структурные и нарративные триггеры. Ожидаемый API: load_pack.
from campaign_kit import load

from ai_dm.state.triggers import Narrative

MINI = "tests/fixtures/packs/mini"


def pack(registry):
    from pathlib import Path

    root = Path(__file__).resolve().parents[3]
    return load(root / MINI, registry)


def test_mini_pack_loads_with_expected_entities(registry):
    p = pack(registry)
    assert [len(p.locations), len(p.npcs), len(p.factions), len(p.pantheon)] == [3, 4, 1, 2]
    assert len(p.events) == 1
    assert [h.id for h in p.heroes] == ["arn"]


def test_mini_pack_has_structural_and_narrative_triggers(registry):
    npcs = {n.id: n for n in pack(registry).npcs}
    assert npcs["aldric"].opportunity[0].if_.type == "flag"
    assert npcs["brann"].opportunity[0].if_.type == "all"
    assert isinstance(npcs["brann"].opportunity[0].if_.items[1], Narrative)
    assert npcs["mara"].opportunity[0].cooldown == "7d"
    assert npcs["aldric"].opportunity[0].once is True


def test_mini_pack_has_secrets_and_god_trigger(registry):
    p = pack(registry)
    assert [s.id for s in next(n for n in p.npcs if n.id == "aldric").secrets] == ["sister", "oath"]
    assert next(g for g in p.pantheon if g.id == "selune").opportunity[0].id == "bless_pilgrim"
