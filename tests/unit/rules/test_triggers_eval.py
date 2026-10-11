# Ожидаемый API: ai_dm.rules.triggers_eval (шаг 14, ТЗ 4.01, ARCHITECTURE B14)
#   Truth(str, Enum): TRUE = "TRUE", FALSE = "FALSE", NEEDS_NARRATIVE = "NEEDS_NARRATIVE"
#   Evaluation(BaseModel): truth: Truth, narrative: list[str], residual: Condition | None
#       narrative -- плоский список текстов нарративных листьев, от которых зависит ответ (только
#       при NEEDS_NARRATIVE; при TRUE / FALSE -- пустой список)
#       residual (партия 4, B6) -- остаток дерева условия: выполненные структурные листья
#       выброшены (TRUE-ветки all убираются, any с TRUE -> вся ветка TRUE), нарративные листья
#       и not / all / any над ними сохранены. NEEDS_NARRATIVE -> непустое дерево (уходит модели
#       world); TRUE / FALSE -> None.
#   evaluate(condition: Condition, world: WorldState, hero: HeroState | None = None) -> Evaluation
#       состояние -- мир плюс ТЕКУЩИЙ герой (отдельным аргументом: у мира нет «текущего героя»).
#       hero=None (D12): условия о герое (hero_has, hero_at, hero_dead, favor) -> FALSE,
#       мировые условия считаются как обычно.
#       Чистая функция, состояние не меняет. Неизвестный id (NPC, локация, бог) -> FALSE,
#       не исключение (битые ссылки ловит validate_refs).
#     all:  любой FALSE -> FALSE (доминирует, нарратив не спрашиваем: narrative == []);
#           иначе любой NEEDS_NARRATIVE -> NEEDS_NARRATIVE (narrative -- все такие листья по
#           порядку); иначе TRUE. Пустой all -> TRUE.
#     any:  любой TRUE -> TRUE (доминирует, narrative == []); иначе любой NEEDS_NARRATIVE ->
#           NEEDS_NARRATIVE (narrative -- все такие листья); иначе FALSE. Пустой any -> FALSE.
#     not:  TRUE <-> FALSE, NEEDS_NARRATIVE остаётся NEEDS_NARRATIVE; narrative -- те же тексты,
#           residual -- NotOf(остаток внутреннего): {not: {narrative: X}} -> NotOf(Narrative(X)).
#     narrative: всегда NEEDS_NARRATIVE, narrative == [text].
#     flag:          значение флага -- bool и равно value (D9): не-bool (1, 0, "yes") -> FALSE;
#                    нет флага -> считается False (value=False -> TRUE)
#     hero_has:      у героя есть запись инвентаря item_id == item с qty > 0
#     npc_status:    world.npcs[id].status == is_
#     hero_at:       hero.location_id == location
#     npc_at:        world.npcs[id].location_id == at
#     time_after:    world.clock.now_s >= seconds (граница включена: ровно в seconds -- TRUE)
#     attitude:      npc.attitude >= gte и npc.attitude <= lte (заданные границы -- обе должны
#                    выполняться; границы включены)
#     favor:         hero.favor.get(god, 0) >= gte и <= lte (благосклонность героя к богу)
#     event_active:  в world.events есть событие с этим id и оно идёт сейчас (D7):
#                    (started_s is None or started_s <= now)
#                    and (ends_at_s is None or now < ends_at_s),
#                    now = world.clock.now_s
#     hero_dead:     hero.status == "dead"
#   validate_refs(condition, world, registry=None) -> list[str]
#       по одной строке на каждую битую ссылку (в строке есть сам битый id); пустой список --
#       всё в порядке. Проверяются: npc_status.id / npc_at.id / attitude.npc -> world.npcs;
#       hero_at.location / npc_at.at -> world.locations; favor.god -> world.pantheon;
#       flag не проверяется (флаги живые). event_active НЕ проверяется (D7: события возникают
#       позже, ТЗ 4.1.2). hero_has без реестра не проверяется; с registry (D8) -- item должен
#       быть в weapon / armor / item реестра, иначе строка с битым id. Обходит all / any / not.
#   is_ready(trigger: Trigger, now_s: int) -> bool
#       state != "active" -> False; once и fired_count > 0 -> False; cooldown задан и
#       last_fired_at не None -> now_s - last_fired_at >= Duration.parse(cooldown).seconds.
#       Условие `if` здесь НЕ проверяется (только готовность по счётчикам и времени).
#   fire(trigger: Trigger, now_s: int) -> None
#       fired_count += 1, last_fired_at = now_s; если once -- state = "fired".
#       Без once state остаётся "active" (повторный запуск ограничивает cooldown).
import pytest
from pydantic import TypeAdapter

from ai_dm.content.registry import ContentRegistry
from ai_dm.core.rng import Rng
from ai_dm.rules.triggers_eval import Truth, evaluate, fire, is_ready, validate_refs
from ai_dm.state.creature import CreatureState
from ai_dm.state.hero import BackgroundSpec, CharacterSheet, ClassLevel, HeroState, InventoryEntry
from ai_dm.state.triggers import AllOf, AnyOf, Condition, Narrative, NotOf, Trigger
from ai_dm.state.world import NPC, GlobalEvent, God, Location, WorldState

DAY = 86400
CONDITION = TypeAdapter(Condition)


def cond(data):
    return CONDITION.validate_python(data)


def make_hero():
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
        id="h1", ordinal=1, name="Арн", sheet=sheet,
        creature=CreatureState(hp_current=12, hp_max=12),
        inventory=[InventoryEntry(item_id="blood_grail", qty=1, cost_cp=0)],
        location_id="port",
        favor={"sun": 3},
    )


def make_world():
    world = WorldState(world_id="w1", rng=Rng(1).state)
    world.npcs["mentor_aldric"] = NPC(
        id="mentor_aldric", name="Олдрик", means=["магия крови"],
        status="alive", attitude=20, location_id="crypt",
    )
    world.locations["port"] = Location(id="port", name="Порт")
    world.locations["crypt"] = Location(id="crypt", name="Склеп")
    world.pantheon["sun"] = God(id="sun", name="Солнцеликий")
    world.events.append(GlobalEvent(id="grey_plague", type="plague"))
    world.flags["met_aldric"] = True
    world.clock.now_s = 1000
    return world


def truth(data, world=None, hero=None):
    world = world or make_world()
    hero = hero or make_hero()
    return evaluate(cond(data), world, hero).truth


STEAL_GRAIL = {
    "all": [
        {"hero_has": "blood_grail"},
        {"npc_status": {"id": "mentor_aldric", "is": "alive"}},
    ]
}


# --- steal_grail (ТЗ 4.01) ---


def test_steal_grail_true_with_grail_and_alive_aldric():
    assert truth(STEAL_GRAIL) == Truth.TRUE


def test_steal_grail_false_without_grail():
    hero = make_hero()
    hero.inventory = []
    assert truth(STEAL_GRAIL, hero=hero) == Truth.FALSE


def test_steal_grail_false_when_aldric_dead():
    world = make_world()
    world.npcs["mentor_aldric"].status = "dead"
    assert truth(STEAL_GRAIL, world=world) == Truth.FALSE


def test_steal_grail_short_and_full_notation_give_same_result():
    full = {
        "type": "all",
        "items": [
            {"type": "hero_has", "item": "blood_grail"},
            {"type": "npc_status", "id": "mentor_aldric", "is": "alive"},
        ],
    }
    assert truth(full) == truth(STEAL_GRAIL)


# --- десять структурных условий: TRUE и FALSE ---


def test_flag_true_when_set():
    assert truth({"flag": "met_aldric"}) == Truth.TRUE


def test_flag_false_when_missing():
    assert truth({"flag": "never_set"}) == Truth.FALSE


def test_flag_false_when_set_to_false():
    world = make_world()
    world.flags["met_aldric"] = False
    assert truth({"flag": "met_aldric"}, world=world) == Truth.FALSE


def test_flag_with_value_false_true_when_missing():
    assert truth({"type": "flag", "name": "never_set", "value": False}) == Truth.TRUE


def test_flag_int_one_is_not_true():
    world = make_world()
    world.flags["met_aldric"] = 1
    assert truth({"flag": "met_aldric"}, world=world) == Truth.FALSE


def test_flag_int_zero_is_not_false():
    world = make_world()
    world.flags["met_aldric"] = 0
    assert truth({"type": "flag", "name": "met_aldric", "value": False}, world=world) == Truth.FALSE


def test_flag_string_is_not_true():
    world = make_world()
    world.flags["met_aldric"] = "yes"
    assert truth({"flag": "met_aldric"}, world=world) == Truth.FALSE


def test_flag_bool_false_matches_value_false():
    world = make_world()
    world.flags["met_aldric"] = False
    assert truth({"type": "flag", "name": "met_aldric", "value": False}, world=world) == Truth.TRUE


def test_hero_has_true_when_item_in_inventory():
    assert truth({"hero_has": "blood_grail"}) == Truth.TRUE


def test_hero_has_false_when_item_absent():
    assert truth({"hero_has": "holy_symbol"}) == Truth.FALSE


def test_hero_has_false_when_qty_zero():
    hero = make_hero()
    hero.inventory[0].qty = 0
    assert truth({"hero_has": "blood_grail"}, hero=hero) == Truth.FALSE


def test_npc_status_true_when_matches():
    assert truth({"npc_status": {"id": "mentor_aldric", "is": "alive"}}) == Truth.TRUE


def test_npc_status_false_when_differs():
    assert truth({"npc_status": {"id": "mentor_aldric", "is": "dead"}}) == Truth.FALSE


def test_npc_status_false_for_unknown_npc():
    assert truth({"npc_status": {"id": "ghost", "is": "alive"}}) == Truth.FALSE


def test_hero_at_true_in_same_location():
    assert truth({"hero_at": "port"}) == Truth.TRUE


def test_hero_at_false_in_other_location():
    assert truth({"hero_at": "crypt"}) == Truth.FALSE


def test_npc_at_true_in_same_location():
    assert truth({"npc_at": {"id": "mentor_aldric", "at": "crypt"}}) == Truth.TRUE


def test_npc_at_false_in_other_location():
    assert truth({"npc_at": {"id": "mentor_aldric", "at": "port"}}) == Truth.FALSE


def test_time_after_false_one_second_before():
    assert truth({"time_after": 1001}) == Truth.FALSE


def test_time_after_true_exactly_at_boundary():
    assert truth({"time_after": 1000}) == Truth.TRUE


def test_time_after_true_one_second_later():
    assert truth({"time_after": 999}) == Truth.TRUE


def test_attitude_gte_true_on_boundary():
    assert truth({"attitude": {"npc": "mentor_aldric", "gte": 20}}) == Truth.TRUE


def test_attitude_gte_false_below():
    assert truth({"attitude": {"npc": "mentor_aldric", "gte": 21}}) == Truth.FALSE


def test_attitude_lte_true_on_boundary():
    assert truth({"attitude": {"npc": "mentor_aldric", "lte": 20}}) == Truth.TRUE


def test_attitude_lte_false_above():
    assert truth({"attitude": {"npc": "mentor_aldric", "lte": 19}}) == Truth.FALSE


def test_attitude_both_bounds_true_inside_range():
    assert truth({"attitude": {"npc": "mentor_aldric", "gte": 10, "lte": 30}}) == Truth.TRUE


def test_attitude_both_bounds_false_outside_range():
    assert truth({"attitude": {"npc": "mentor_aldric", "gte": 30, "lte": 40}}) == Truth.FALSE


def test_attitude_false_for_unknown_npc():
    assert truth({"attitude": {"npc": "ghost", "gte": -100}}) == Truth.FALSE


def test_favor_gte_true_on_boundary():
    assert truth({"favor": {"god": "sun", "gte": 3}}) == Truth.TRUE


def test_favor_gte_false_below():
    assert truth({"favor": {"god": "sun", "gte": 4}}) == Truth.FALSE


def test_favor_lte_true_for_god_without_favor_entry():
    # нет записи благосклонности -- считается 0
    assert truth({"favor": {"god": "moon", "lte": 0}}) == Truth.TRUE


def test_favor_lte_false_above():
    assert truth({"favor": {"god": "sun", "lte": 2}}) == Truth.FALSE


def test_event_active_true_when_event_present():
    assert truth({"event_active": "grey_plague"}) == Truth.TRUE


def test_event_active_false_when_event_absent():
    assert truth({"event_active": "blood_moon"}) == Truth.FALSE


def event_world(started_s, ends_at_s):
    world = make_world()
    world.events[0].started_s = started_s
    world.events[0].ends_at_s = ends_at_s
    return world


def test_event_active_false_before_start():
    world = event_world(1001, None)
    assert truth({"event_active": "grey_plague"}, world=world) == Truth.FALSE


def test_event_active_true_exactly_at_start():
    world = event_world(1000, None)
    assert truth({"event_active": "grey_plague"}, world=world) == Truth.TRUE


def test_event_active_true_just_before_end():
    world = event_world(None, 1001)
    assert truth({"event_active": "grey_plague"}, world=world) == Truth.TRUE


def test_event_active_false_exactly_at_end():
    world = event_world(None, 1000)
    assert truth({"event_active": "grey_plague"}, world=world) == Truth.FALSE


def test_event_active_false_after_end():
    world = event_world(100, 500)
    assert truth({"event_active": "grey_plague"}, world=world) == Truth.FALSE


def test_event_active_true_inside_window():
    world = event_world(500, 2000)
    assert truth({"event_active": "grey_plague"}, world=world) == Truth.TRUE


def test_hero_dead_false_for_living_hero():
    assert truth({"hero_dead": True}) == Truth.FALSE


def test_hero_dead_true_for_dead_hero():
    hero = make_hero()
    hero.status = "dead"
    assert truth({"hero_dead": True}, hero=hero) == Truth.TRUE


# --- all / any / not и нарративные листья ---


def test_narrative_alone_needs_narrative_with_text():
    result = evaluate(cond({"narrative": "герой узнаёт тайну"}), make_world(), make_hero())
    assert result.truth == Truth.NEEDS_NARRATIVE
    assert result.narrative == ["герой узнаёт тайну"]


def test_structural_result_has_no_narrative_leaves():
    result = evaluate(cond({"flag": "met_aldric"}), make_world(), make_hero())
    assert result.narrative == []


def test_all_true_and_narrative_needs_narrative():
    data = {"all": [{"flag": "met_aldric"}, {"narrative": "тайна раскрыта"}]}
    result = evaluate(cond(data), make_world(), make_hero())
    assert result.truth == Truth.NEEDS_NARRATIVE
    assert result.narrative == ["тайна раскрыта"]


def test_all_false_dominates_narrative():
    data = {"all": [{"flag": "never_set"}, {"narrative": "тайна раскрыта"}]}
    result = evaluate(cond(data), make_world(), make_hero())
    assert result.truth == Truth.FALSE
    assert result.narrative == []


def test_all_false_after_narrative_still_false():
    data = {"all": [{"narrative": "тайна раскрыта"}, {"flag": "never_set"}]}
    assert truth(data) == Truth.FALSE


def test_all_collects_every_narrative_leaf_in_order():
    data = {"all": [{"narrative": "первое"}, {"flag": "met_aldric"}, {"narrative": "второе"}]}
    result = evaluate(cond(data), make_world(), make_hero())
    assert result.narrative == ["первое", "второе"]


def test_any_true_dominates_narrative():
    data = {"any": [{"narrative": "тайна раскрыта"}, {"flag": "met_aldric"}]}
    result = evaluate(cond(data), make_world(), make_hero())
    assert result.truth == Truth.TRUE
    assert result.narrative == []


def test_any_false_and_narrative_needs_narrative():
    data = {"any": [{"flag": "never_set"}, {"narrative": "тайна раскрыта"}]}
    result = evaluate(cond(data), make_world(), make_hero())
    assert result.truth == Truth.NEEDS_NARRATIVE
    assert result.narrative == ["тайна раскрыта"]


def test_any_all_false_is_false():
    assert truth({"any": [{"flag": "never_set"}, {"hero_at": "crypt"}]}) == Truth.FALSE


def test_not_inverts_true():
    assert truth({"not": {"flag": "met_aldric"}}) == Truth.FALSE


def test_not_inverts_false():
    assert truth({"not": {"flag": "never_set"}}) == Truth.TRUE


def test_not_of_narrative_stays_needs_narrative():
    result = evaluate(cond({"not": {"narrative": "герой солгал"}}), make_world(), make_hero())
    assert result.truth == Truth.NEEDS_NARRATIVE
    assert result.narrative == ["герой солгал"]


def test_not_of_narrative_residual_is_not_of_narrative():
    result = evaluate(cond({"not": {"narrative": "герой солгал"}}), make_world(), make_hero())
    assert result.residual == NotOf(item=Narrative(text="герой солгал"))


def test_not_of_needs_narrative_all_stays_needs_narrative():
    data = {"not": {"all": [{"flag": "met_aldric"}, {"narrative": "герой солгал"}]}}
    assert truth(data) == Truth.NEEDS_NARRATIVE


# --- residual (B6) ---


def residual_of(data):
    return evaluate(cond(data), make_world(), make_hero()).residual


def collapse(node):
    # all / any с одним элементом считаем равным самому элементу
    if isinstance(node, (AllOf, AnyOf)) and len(node.items) == 1:
        return collapse(node.items[0])
    return node


def leaf_types(node):
    if isinstance(node, (AllOf, AnyOf)):
        return {t for item in node.items for t in leaf_types(item)}
    if isinstance(node, NotOf):
        return leaf_types(node.item)
    return {node.type}


def test_residual_of_plain_narrative_is_that_narrative():
    assert residual_of({"narrative": "тайна"}) == Narrative(text="тайна")


def test_residual_of_all_drops_true_structural_leaves():
    data = {"all": [{"flag": "met_aldric"}, {"narrative": "тайна"}]}
    assert collapse(residual_of(data)) == Narrative(text="тайна")


def test_residual_of_all_keeps_all_narrative_leaves_in_order():
    data = {"all": [{"narrative": "первое"}, {"flag": "met_aldric"}, {"narrative": "второе"}]}
    residual = residual_of(data)
    assert isinstance(residual, AllOf)
    assert residual.items == [Narrative(text="первое"), Narrative(text="второе")]


def test_residual_of_any_with_narrative_keeps_narrative():
    data = {"any": [{"flag": "never_set"}, {"narrative": "тайна"}]}
    residual = residual_of(data)
    assert residual is not None
    assert Narrative(text="тайна") in (
        residual.items if isinstance(residual, AnyOf) else [residual]
    )


def test_residual_of_not_over_all_keeps_not_all_narrative():
    data = {"not": {"all": [{"flag": "met_aldric"}, {"narrative": "герой солгал"}]}}
    residual = residual_of(data)
    assert isinstance(residual, NotOf)
    assert collapse(residual.item) == Narrative(text="герой солгал")


def test_residual_of_mixed_tree_has_only_narrative_leaves():
    data = {
        "all": [
            {"flag": "met_aldric"},
            {"any": [{"hero_at": "crypt"}, {"narrative": "первое"}]},
            {"not": {"narrative": "второе"}},
            {"hero_at": "port"},
        ]
    }
    residual = residual_of(data)
    assert residual is not None
    assert leaf_types(residual) == {"narrative"}


def test_residual_of_mixed_tree_keeps_not_over_narrative():
    data = {"all": [{"flag": "met_aldric"}, {"not": {"narrative": "второе"}}]}
    assert collapse(residual_of(data)) == NotOf(item=Narrative(text="второе"))


def test_residual_is_none_when_true():
    assert residual_of({"flag": "met_aldric"}) is None
    assert residual_of({"any": [{"narrative": "тайна"}, {"flag": "met_aldric"}]}) is None


def test_residual_is_none_when_false():
    assert residual_of({"flag": "never_set"}) is None
    assert residual_of({"all": [{"flag": "never_set"}, {"narrative": "тайна"}]}) is None


def test_residual_is_none_when_not_inverts_structural():
    assert residual_of({"not": {"flag": "never_set"}}) is None


def test_residual_present_whenever_needs_narrative():
    data = {"all": [{"flag": "met_aldric"}, {"narrative": "тайна"}]}
    result = evaluate(cond(data), make_world(), make_hero())
    assert result.truth == Truth.NEEDS_NARRATIVE
    assert result.residual is not None


# --- hero=None (D12) ---


def truth_without_hero(data):
    return evaluate(cond(data), make_world()).truth


@pytest.mark.parametrize(
    "data",
    [
        {"hero_has": "blood_grail"},
        {"hero_at": "port"},
        {"hero_dead": True},
        {"favor": {"god": "sun", "gte": 1}},
        {"favor": {"god": "sun", "lte": 100}},
    ],
)
def test_hero_conditions_are_false_without_hero(data):
    assert truth_without_hero(data) == Truth.FALSE


def test_world_conditions_work_without_hero():
    assert truth_without_hero({"flag": "met_aldric"}) == Truth.TRUE
    assert truth_without_hero({"npc_status": {"id": "mentor_aldric", "is": "alive"}}) == Truth.TRUE
    assert truth_without_hero({"time_after": 1000}) == Truth.TRUE


def test_all_mixing_world_and_hero_leaf_is_false_without_hero():
    assert truth_without_hero({"all": [{"flag": "met_aldric"}, {"hero_at": "port"}]}) == Truth.FALSE


def test_any_mixing_world_and_hero_leaf_is_true_by_world_without_hero():
    assert truth_without_hero({"any": [{"hero_at": "port"}, {"flag": "met_aldric"}]}) == Truth.TRUE


def test_nested_any_inside_all_resolves_by_structure():
    data = {
        "all": [
            {"any": [{"flag": "never_set"}, {"hero_at": "port"}]},
            {"not": {"npc_status": {"id": "mentor_aldric", "is": "dead"}}},
        ]
    }
    assert truth(data) == Truth.TRUE


def test_empty_all_is_true():
    assert truth({"all": []}) == Truth.TRUE


def test_empty_any_is_false():
    assert truth({"any": []}) == Truth.FALSE


def test_evaluate_does_not_change_world():
    world = make_world()
    before = world.model_dump_json()
    evaluate(cond(STEAL_GRAIL), world, make_hero())
    assert world.model_dump_json() == before


# --- validate_refs ---


def test_validate_refs_empty_for_good_condition():
    assert validate_refs(cond(STEAL_GRAIL), make_world()) == []


def test_validate_refs_reports_unknown_npc_in_status():
    refs = validate_refs(cond({"npc_status": {"id": "ghost", "is": "alive"}}), make_world())
    assert len(refs) == 1
    assert "ghost" in refs[0]


def test_validate_refs_reports_unknown_npc_in_attitude():
    refs = validate_refs(cond({"attitude": {"npc": "ghost", "gte": 0}}), make_world())
    assert len(refs) == 1
    assert "ghost" in refs[0]


def test_validate_refs_reports_unknown_location_in_hero_at():
    refs = validate_refs(cond({"hero_at": "nowhere"}), make_world())
    assert len(refs) == 1
    assert "nowhere" in refs[0]


def test_validate_refs_reports_both_npc_and_location_in_npc_at():
    refs = validate_refs(cond({"npc_at": {"id": "ghost", "at": "nowhere"}}), make_world())
    assert len(refs) == 2
    assert any("ghost" in r for r in refs)
    assert any("nowhere" in r for r in refs)


def test_validate_refs_reports_unknown_god():
    refs = validate_refs(cond({"favor": {"god": "void", "gte": 1}}), make_world())
    assert len(refs) == 1
    assert "void" in refs[0]


def test_validate_refs_ignores_unknown_event():
    # события возникают позже (ТЗ 4.1.2): ссылка на ещё не существующее -- не ошибка
    assert validate_refs(cond({"event_active": "blood_moon"}), make_world()) == []


def test_validate_refs_ignores_flag_and_hero_has():
    assert validate_refs(cond({"flag": "anything"}), make_world()) == []
    assert validate_refs(cond({"hero_has": "anything"}), make_world()) == []


def make_registry():
    items = {
        "weapon": {"longsword": object()},
        "armor": {"chain_mail": object()},
        "item": {"blood_grail": object()},
    }
    return ContentRegistry(items)


@pytest.mark.parametrize("item", ["longsword", "chain_mail", "blood_grail"])
def test_validate_refs_with_registry_accepts_known_item(item):
    assert validate_refs(cond({"hero_has": item}), make_world(), make_registry()) == []


def test_validate_refs_with_registry_reports_unknown_item():
    refs = validate_refs(cond({"hero_has": "no_such_item"}), make_world(), make_registry())
    assert len(refs) == 1
    assert "no_such_item" in refs[0]


def test_validate_refs_with_registry_walks_into_all():
    data = {"all": [{"hero_has": "blood_grail"}, {"hero_has": "no_such_item"}]}
    refs = validate_refs(cond(data), make_world(), make_registry())
    assert len(refs) == 1
    assert "no_such_item" in refs[0]


def test_validate_refs_with_registry_still_ignores_event_active():
    refs = validate_refs(cond({"event_active": "blood_moon"}), make_world(), make_registry())
    assert refs == []


def test_validate_refs_walks_into_all_any_not():
    data = {
        "all": [
            {"any": [{"hero_at": "nowhere"}, {"flag": "x"}]},
            {"not": {"npc_status": {"id": "ghost", "is": "alive"}}},
        ]
    }
    refs = validate_refs(cond(data), make_world())
    assert len(refs) == 2
    assert any("nowhere" in r for r in refs)
    assert any("ghost" in r for r in refs)


# --- is_ready / fire ---


def make_trigger(**extra):
    data = {"id": "steal_grail", "if": {"hero_has": "blood_grail"}, "then": "выкрадет"}
    data.update(extra)
    return Trigger.model_validate(data)


def test_fresh_trigger_is_ready():
    assert is_ready(make_trigger(), 0) is True


def test_disabled_trigger_is_not_ready():
    assert is_ready(make_trigger(state="disabled"), 0) is False


def test_fired_state_trigger_is_not_ready():
    assert is_ready(make_trigger(state="fired"), 0) is False


def test_once_trigger_ready_before_first_fire():
    assert is_ready(make_trigger(once=True), 100) is True


def test_once_trigger_not_ready_after_fire():
    trigger = make_trigger(once=True)
    fire(trigger, 100)
    assert is_ready(trigger, 10**9) is False


def test_once_trigger_with_fired_count_not_ready():
    assert is_ready(make_trigger(once=True, fired_count=1, last_fired_at=5), 10**9) is False


def test_cooldown_trigger_ready_if_never_fired():
    assert is_ready(make_trigger(cooldown="7d"), 0) is True


def test_cooldown_not_ready_at_6_days_23_hours():
    trigger = make_trigger(cooldown="7d", fired_count=1, last_fired_at=1000)
    assert is_ready(trigger, 1000 + 7 * DAY - 3600) is False


def test_cooldown_not_ready_one_second_before_boundary():
    trigger = make_trigger(cooldown="7d", fired_count=1, last_fired_at=1000)
    assert is_ready(trigger, 1000 + 7 * DAY - 1) is False


def test_cooldown_ready_exactly_at_7_days():
    trigger = make_trigger(cooldown="7d", fired_count=1, last_fired_at=1000)
    assert is_ready(trigger, 1000 + 7 * DAY) is True


def test_cooldown_ready_after_8_days():
    trigger = make_trigger(cooldown="7d", fired_count=1, last_fired_at=1000)
    assert is_ready(trigger, 1000 + 8 * DAY) is True


def test_fire_increments_count_and_sets_time():
    trigger = make_trigger()
    fire(trigger, 500)
    assert trigger.fired_count == 1
    assert trigger.last_fired_at == 500


def test_fire_twice_counts_two_and_keeps_last_time():
    trigger = make_trigger()
    fire(trigger, 500)
    fire(trigger, 900)
    assert trigger.fired_count == 2
    assert trigger.last_fired_at == 900


def test_fire_once_trigger_sets_state_fired():
    trigger = make_trigger(once=True)
    fire(trigger, 500)
    assert trigger.state == "fired"


def test_fire_repeatable_trigger_stays_active():
    trigger = make_trigger()
    fire(trigger, 500)
    assert trigger.state == "active"


def test_cooldown_trigger_blocked_right_after_fire():
    trigger = make_trigger(cooldown="7d")
    fire(trigger, 500)
    assert is_ready(trigger, 501) is False


def test_cooldown_trigger_ready_again_after_cooldown_since_fire():
    trigger = make_trigger(cooldown="7d")
    fire(trigger, 500)
    assert is_ready(trigger, 500 + 7 * DAY) is True


@pytest.mark.parametrize("state", ["disabled", "fired"])
def test_non_active_state_blocks_even_with_cooldown_elapsed(state):
    trigger = make_trigger(cooldown="7d", state=state, fired_count=1, last_fired_at=0)
    assert is_ready(trigger, 100 * DAY) is False


# --- Б1а (B1-PLAN A1): validate_refs с KnownIds и с WorldState ---

def make_known():
    from ai_dm.rules.triggers_eval import KnownIds

    return KnownIds(npcs={"mentor_aldric"}, locations={"port", "crypt"}, pantheon={"sun"})


BROKEN_CONDITIONS = [
    {"npc_status": {"id": "ghost", "is": "alive"}},
    {"attitude": {"npc": "ghost", "gte": 0}},
    {"hero_at": "nowhere"},
    {"npc_at": {"id": "ghost", "at": "nowhere"}},
    {"favor": {"god": "void", "gte": 1}},
    {"all": [{"hero_at": "nowhere"}, {"not": {"npc_status": {"id": "ghost", "is": "dead"}}}]},
]


@pytest.mark.parametrize("data", BROKEN_CONDITIONS)
def test_validate_refs_known_ids_and_world_give_same_texts(data):
    from ai_dm.rules.triggers_eval import KnownIds

    from_world = validate_refs(cond(data), make_world())
    world = make_world()
    known = KnownIds(set(world.npcs), set(world.locations), set(world.pantheon))
    from_known = validate_refs(cond(data), known)
    assert from_known == from_world
    assert from_known != []


def test_validate_refs_known_ids_accepts_good_condition():
    assert validate_refs(cond(STEAL_GRAIL), make_known()) == []


def test_validate_refs_known_ids_reports_unknown_npc_text():
    refs = validate_refs(cond({"npc_status": {"id": "ghost", "is": "dead"}}), make_known())
    assert refs == ["npc_status: неизвестный NPC 'ghost'"]


def test_validate_refs_known_ids_ignores_flag_and_event():
    assert validate_refs(cond({"flag": "x"}), make_known()) == []
    assert validate_refs(cond({"event_active": "blood_moon"}), make_known()) == []


def test_validate_refs_known_ids_checks_hero_has_only_with_registry(registry):
    data = {"hero_has": "no_such_item"}
    assert validate_refs(cond(data), make_known()) == []
    assert len(validate_refs(cond(data), make_known(), registry)) == 1


def test_validate_refs_checks_hero_has_inside_not_and_all_with_registry(registry):
    broken = {"hero_has": "no_such_item"}
    assert len(validate_refs(cond({"not": broken}), make_world(), registry)) == 1
    assert len(validate_refs(cond({"all": [broken, {"flag": "x"}]}), make_world(), registry)) == 1
    assert validate_refs(cond({"not": broken}), make_world()) == []
