# Автофлаги (rules.auto_flags) и триггеры по ним: флаг ставит движок по событию, триггер на границе
# сцены срабатывает. Ожидаемый API: ai_dm.world_sim.triggers.check -- см. world_sim_kit.py.
import pytest
from world_sim_kit import has_ref, mini_bundle, run_check

from ai_dm.core.events import DomainEvent
from ai_dm.rules.auto_flags import apply_events
from ai_dm.state.triggers import Trigger

EVENTS = [
    ("npc_dead:guard", DomainEvent(type="npc_died", data={"id": "guard"})),
    ("visited:cellar", DomainEvent(type="location_visited", data={"id": "cellar"})),
    ("combat_ended:c1", DomainEvent(type="combat_ended", data={"id": "c1"})),
    ("item_gained:crowbar", DomainEvent(type="item_gained", data={"item": "crowbar", "qty": 1})),
]


def add_trigger(bundle, flag):
    bundle.world.npcs["mara"].opportunity.append(
        Trigger(id="by_auto", **{"if": {"flag": flag}}, then="отреагировала", once=True)
    )


@pytest.mark.parametrize("flag, event", EVENTS)
def test_trigger_fires_on_auto_flag(flag, event, registry, cfg):
    bundle = mini_bundle(registry, cfg)
    add_trigger(bundle, flag)
    apply_events(bundle.world, [event])
    assert has_ref(run_check(bundle).fired, "by_auto")


@pytest.mark.parametrize("flag, event", EVENTS)
def test_trigger_waits_without_auto_flag(flag, event, registry, cfg):
    bundle = mini_bundle(registry, cfg)
    add_trigger(bundle, flag)
    assert not has_ref(run_check(bundle).fired, "by_auto")


def test_trigger_by_npc_status_dead_fires_after_death_event(registry, cfg):
    from ai_dm.rules.mortality_guard import remove_creature

    bundle = mini_bundle(registry, cfg)
    events = remove_creature(bundle.world, "mara", "dead", "goal", by="aldric")
    apply_events(bundle.world, events)
    assert has_ref(run_check(bundle).fired, "guild", "guild_hunt")
