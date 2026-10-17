# Ж0 подшаг 2 (docs/plan-zh0.md, пп. 11, 14): память NPC о герое, лимит и вытеснение.
# API (rules/npc_memory.py):
#   remember(npc, scene: SceneState, event: NpcEvent, cfg: NpcMemoryConfig) -> NpcSceneMemory | None
#       запись события в память NPC за сцену scene: записи нет -- новая (scene_id = scene.id,
#       at_s = scene.started_at_s, weight = scene.attitude_spent.get(npc.id, 0)), есть -- событие
#       дописывается в неё. В сцене уже max_events_per_scene событий -> None, память не меняется.
#       Память полна (max_scenes) и сцена новая -> evict(npc), потом запись (новая входит всегда).
#   evict(npc) -> NpcSceneMemory: убирает и возвращает запись с наименьшим (weight, at_s).
#   refresh_weight(npc, scene) -> None: weight записи этой сцены = scene.attitude_spent[npc.id];
#       нет записи -- ничего не делает.
#   memory_data(npc) -> list[dict]: память для промпта, по порядку at_s; у записи ключи scene_id,
#       at_s, weight, events (kind, turn_seq, text).
import json

from ai_dm.config.settings import load_rules_config
from ai_dm.rules.npc_memory import (
    events_full,
    evict,
    goals_data,
    memory_data,
    memory_last,
    refresh_weight,
    remember,
    scene_entry,
)
from ai_dm.state.relations import NpcEvent, NpcGoal, NpcSceneMemory
from ai_dm.state.scene import SceneState
from ai_dm.state.world import NPC

CFG = load_rules_config().npc_memory


def make_npc():
    return NPC(id="aldric", name="Алдрик", means=["торговля"])


def scene(n, spent=0, npc_id="aldric"):
    return SceneState(
        id=f"scene_{n}", started_at_s=n * 100, attitude_spent={npc_id: spent} if spent else {}
    )


def event(kind="helped", text="помог", turn_seq=1):
    return NpcEvent(kind=kind, turn_seq=turn_seq, text=text)


def put(npc, sc, ev=None, cfg=CFG):
    return remember(npc, sc, ev or event(), cfg)


def entry(n, weight, events=1):
    return NpcSceneMemory(
        scene_id=f"scene_{n}", at_s=n * 100, weight=weight, events=[event()] * events
    )


def fill(npc, weights):
    npc.memory = [entry(i, w) for i, w in enumerate(weights, start=1)]


def ids(npc):
    return [m.scene_id for m in npc.memory]


# remember: запись

def test_remember_creates_scene_entry():
    npc = make_npc()
    put(npc, scene(1))
    assert ids(npc) == ["scene_1"]


def test_remember_sets_at_s_from_scene_start():
    npc = make_npc()
    put(npc, scene(3))
    assert npc.memory[0].at_s == 300


def test_remember_keeps_event_fields():
    npc = make_npc()
    put(npc, scene(1), event("gift", "подарил кинжал", turn_seq=7))
    stored = npc.memory[0].events[0]
    assert (stored.kind, stored.text, stored.turn_seq) == ("gift", "подарил кинжал", 7)


def test_remember_returns_the_scene_entry():
    npc = make_npc()
    assert put(npc, scene(1)) is npc.memory[0]


def test_remember_new_entry_weight_is_zero_without_attitude_change():
    npc = make_npc()
    put(npc, scene(1))
    assert npc.memory[0].weight == 0


def test_remember_new_entry_weight_follows_spent_attitude():
    npc = make_npc()
    put(npc, scene(1, spent=7))
    assert npc.memory[0].weight == 7


def test_remember_second_event_goes_into_same_scene_entry():
    npc = make_npc()
    sc = scene(1)
    put(npc, sc, event(text="раз"))
    put(npc, sc, event("insult", "два"))
    assert len(npc.memory) == 1
    assert [e.text for e in npc.memory[0].events] == ["раз", "два"]


def test_remember_different_scenes_make_different_entries():
    npc = make_npc()
    put(npc, scene(1))
    put(npc, scene(2))
    assert ids(npc) == ["scene_1", "scene_2"]


# remember: лимит событий в сцене

def test_remember_events_up_to_limit_are_kept():
    npc = make_npc()
    sc = scene(1)
    for _ in range(CFG.max_events_per_scene):
        assert put(npc, sc) is not None
    assert len(npc.memory[0].events) == CFG.max_events_per_scene


def test_remember_event_over_limit_returns_none():
    npc = make_npc()
    sc = scene(1)
    for _ in range(CFG.max_events_per_scene):
        put(npc, sc)
    assert put(npc, sc) is None


def test_remember_event_over_limit_does_not_change_memory():
    npc = make_npc()
    sc = scene(1)
    for _ in range(CFG.max_events_per_scene):
        put(npc, sc)
    before = npc.model_dump()
    put(npc, sc, event("betrayal", "лишнее"))
    assert npc.model_dump() == before


def test_remember_event_limit_comes_from_config():
    npc = make_npc()
    cfg = load_rules_config(toml_text="[npc_memory]\nmax_events_per_scene = 1\n").npc_memory
    sc = scene(1)
    assert put(npc, sc, cfg=cfg) is not None
    assert put(npc, sc, cfg=cfg) is None


def test_remember_event_limit_is_per_scene():
    npc = make_npc()
    for _ in range(CFG.max_events_per_scene):
        put(npc, scene(1))
    assert put(npc, scene(2)) is not None


# remember: лимит сцен и вытеснение

def test_remember_fills_up_to_max_scenes_without_eviction():
    npc = make_npc()
    for n in range(1, CFG.max_scenes + 1):
        put(npc, scene(n))
    assert len(npc.memory) == CFG.max_scenes


def test_remember_new_scene_over_limit_keeps_max_scenes():
    npc = make_npc()
    fill(npc, [5] * CFG.max_scenes)
    put(npc, scene(99))
    assert len(npc.memory) == CFG.max_scenes


def test_remember_new_scene_over_limit_is_always_stored():
    npc = make_npc()
    fill(npc, [9] * CFG.max_scenes)
    put(npc, scene(99))
    assert "scene_99" in ids(npc)


def test_remember_new_scene_over_limit_evicts_lowest_weight():
    npc = make_npc()
    fill(npc, [5, 5, 1] + [5] * (CFG.max_scenes - 3))
    put(npc, scene(99))
    assert "scene_3" not in ids(npc)


def test_remember_limit_comes_from_config():
    npc = make_npc()
    cfg = load_rules_config(toml_text="[npc_memory]\nmax_scenes = 2\n").npc_memory
    for n in (1, 2, 3):
        put(npc, scene(n), cfg=cfg)
    assert len(npc.memory) == 2


def test_remember_event_into_existing_scene_does_not_evict_when_full():
    npc = make_npc()
    fill(npc, [5] * CFG.max_scenes)
    put(npc, scene(1))
    assert len(npc.memory) == CFG.max_scenes
    assert len(npc.memory[0].events) == 2


def test_remember_event_over_limit_in_full_memory_evicts_nothing():
    npc = make_npc()
    fill(npc, [5] * CFG.max_scenes)
    npc.memory[0].events = [event()] * CFG.max_events_per_scene
    put(npc, scene(1))
    assert len(npc.memory) == CFG.max_scenes


# evict

def test_evict_removes_lowest_weight():
    npc = make_npc()
    fill(npc, [4, 2, 9])
    evict(npc)
    assert ids(npc) == ["scene_1", "scene_3"]


def test_evict_returns_removed_entry():
    npc = make_npc()
    fill(npc, [4, 2, 9])
    assert evict(npc).scene_id == "scene_2"


def test_evict_equal_weights_removes_oldest_by_at_s():
    npc = make_npc()
    fill(npc, [3, 3, 3])
    evict(npc)
    assert ids(npc) == ["scene_2", "scene_3"]


def test_evict_equal_weights_oldest_even_when_list_is_not_ordered():
    npc = make_npc()
    npc.memory = [entry(3, 3), entry(1, 3), entry(2, 3)]
    assert evict(npc).scene_id == "scene_1"


def test_evict_weight_beats_age():
    npc = make_npc()
    fill(npc, [9, 9, 1])
    assert evict(npc).scene_id == "scene_3"


def test_evict_zero_weight_goes_first():
    npc = make_npc()
    fill(npc, [2, 0, 1])
    assert evict(npc).scene_id == "scene_2"


# refresh_weight

def test_refresh_weight_takes_spent_attitude():
    npc = make_npc()
    sc = scene(1)
    put(npc, sc)
    sc.attitude_spent["aldric"] = 13
    refresh_weight(npc, sc)
    assert npc.memory[0].weight == 13


def test_refresh_weight_can_lower_weight():
    npc = make_npc()
    npc.memory = [entry(1, 15)]
    refresh_weight(npc, scene(1, spent=4))
    assert npc.memory[0].weight == 4


def test_refresh_weight_without_spent_gives_zero():
    npc = make_npc()
    npc.memory = [entry(1, 15)]
    refresh_weight(npc, scene(1))
    assert npc.memory[0].weight == 0


def test_refresh_weight_touches_only_its_scene():
    npc = make_npc()
    fill(npc, [5, 5])
    refresh_weight(npc, scene(2, spent=8))
    assert [m.weight for m in npc.memory] == [5, 8]


def test_refresh_weight_ignores_other_npc_spent():
    npc = make_npc()
    npc.memory = [entry(1, 6)]
    refresh_weight(npc, scene(1, spent=9, npc_id="grakh"))
    assert npc.memory[0].weight == 0


def test_refresh_weight_without_entry_does_nothing():
    npc = make_npc()
    fill(npc, [5])
    refresh_weight(npc, scene(7, spent=9))
    assert [m.weight for m in npc.memory] == [5]


# memory_last, goals_data

def test_memory_last_empty_memory_is_none():
    assert memory_last(make_npc()) is None


def test_memory_last_is_last_event_of_latest_scene():
    npc = make_npc()
    npc.memory = [entry(2, 1), entry(1, 9)]
    npc.memory[0].events = [event("helped", "a"), event("gift", "b")]
    assert memory_last(npc) == {"kind": "gift", "text": "b"}


def test_goals_data_shows_only_active_goals():
    npc = make_npc()
    npc.goals = [
        NpcGoal(kind="revenge", target="hero", text="за брата", since_s=1),
        NpcGoal(kind="debt", target="hero", since_s=2, status="done"),
        NpcGoal(kind="love", target="hero", since_s=3, status="dropped"),
    ]
    assert goals_data(npc) == [{"kind": "revenge", "target": "hero", "text": "за брата"}]


def test_goals_data_without_goals_is_empty():
    assert goals_data(make_npc()) == []


# memory_data

def test_memory_data_empty_memory_is_empty_list():
    assert memory_data(make_npc()) == []


def test_memory_data_has_one_item_per_scene():
    npc = make_npc()
    fill(npc, [1, 2, 3])
    assert len(memory_data(npc)) == 3


def test_memory_data_item_keys():
    npc = make_npc()
    fill(npc, [4])
    item = memory_data(npc)[0]
    assert (item["scene_id"], item["at_s"], item["weight"]) == ("scene_1", 100, 4)


def test_memory_data_lists_events_with_kind_and_text():
    npc = make_npc()
    put(npc, scene(1), event("promise", "обещал вернуть долг", turn_seq=3))
    [stored] = memory_data(npc)[0]["events"]
    assert (stored["kind"], stored["text"], stored["turn_seq"]) == (
        "promise", "обещал вернуть долг", 3
    )


def test_memory_data_is_ordered_by_at_s():
    npc = make_npc()
    npc.memory = [entry(3, 1), entry(1, 1), entry(2, 1)]
    assert [m["scene_id"] for m in memory_data(npc)] == ["scene_1", "scene_2", "scene_3"]


def test_memory_data_is_json_serializable():
    npc = make_npc()
    fill(npc, [1, 2])
    assert json.loads(json.dumps(memory_data(npc)))


# scene_entry, events_full

def test_scene_entry_finds_entry_by_scene_id():
    npc = make_npc()
    fill(npc, [1, 2, 3])
    assert scene_entry(npc, scene(2)) is npc.memory[1]


def test_scene_entry_of_other_scene_is_none():
    npc = make_npc()
    fill(npc, [1, 2])
    assert scene_entry(npc, scene(9)) is None


def test_scene_entry_without_memory_is_none():
    assert scene_entry(make_npc(), scene(1)) is None


def test_events_full_without_entry_is_false():
    assert events_full(make_npc(), scene(1), CFG) is False


def test_events_full_other_scene_entry_is_false():
    npc = make_npc()
    npc.memory = [entry(1, 0, events=CFG.max_events_per_scene)]
    assert events_full(npc, scene(2), CFG) is False


def test_events_full_one_below_limit_is_false():
    npc = make_npc()
    npc.memory = [entry(1, 0, events=CFG.max_events_per_scene - 1)]
    assert events_full(npc, scene(1), CFG) is False


def test_events_full_exactly_at_limit_is_true():
    npc = make_npc()
    npc.memory = [entry(1, 0, events=CFG.max_events_per_scene)]
    assert events_full(npc, scene(1), CFG) is True


def test_events_full_takes_limit_from_cfg():
    npc = make_npc()
    npc.memory = [entry(1, 0, events=2)]
    small = CFG.model_copy(update={"max_events_per_scene": 2})
    big = CFG.model_copy(update={"max_events_per_scene": 3})
    assert (events_full(npc, scene(1), small), events_full(npc, scene(1), big)) == (True, False)
