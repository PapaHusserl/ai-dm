# Сюжетные предметы, партия А (CUSTOM-ITEMS-PLAN, разд. 1): реестр с наложением в ходе игры.
#   TurnRunner.registry / GameApp.registry -- свойства: базовый реестр (base_registry) плюс
#   сюжетные предметы мира (rules.custom_items.world_registry); базовый реестр не меняется.
#   Ход с give_custom_item: после коммита runner.registry знает предмет; сорванный ход ничего
#   не оставляет; предметы загруженного/подставленного мира видны сразу.
from game_kit import make_app, make_rig, scripted, text_step, tools_step
from protocol_kit import make_bundle

from ai_dm.state.world import CustomItem

FATAL = [{"error": "fatal", "message": "ключ отозван"}]


def give_call(call_id="gc-1", name="Ржавый ключ", **fields):
    data = {
        "type": "give_custom_item", "name": name, "description": "Ключ от ворот", "qty": 1,
        "weight_lb": 0, "cost_cp": 0, "quest": True,
    }
    data.update(fields)
    return {"id": call_id, "name": "give_custom_item", "input": data}


def take_call(call_id="tk-1", item_id="custom_1"):
    return {
        "id": call_id, "name": "take_item",
        "input": {"type": "take_item", "item_id": item_id, "qty": 1, "why": "given",
                  "holder_npc_id": "grakh"},
    }


def key_world_bundle(registry):
    bundle = make_bundle(registry)
    bundle.world.custom_items["custom_1"] = CustomItem(
        id="custom_1", name="Ржавый ключ", created_s=0, quest=True
    )
    bundle.world.custom_item_seq = 1
    return bundle


def test_runner_registry_without_custom_items_knows_the_srd(registry, cfg, tmp_path):
    rig = make_rig(registry, cfg, tmp_path, scripted([text_step("Тихо.")]))
    assert rig.runner.registry.has("weapon", "longsword")
    assert rig.runner.registry.has("item", "custom_1") is False


def test_runner_keeps_the_base_registry(registry, cfg, tmp_path):
    rig = make_rig(registry, cfg, tmp_path, scripted([text_step("Тихо.")]))
    assert rig.runner.base_registry is registry


def test_runner_registry_knows_items_of_the_loaded_world(registry, cfg, tmp_path):
    bundle = key_world_bundle(registry)
    rig = make_rig(registry, cfg, tmp_path, scripted([text_step("Тихо.")]), bundle=bundle)
    assert rig.runner.registry.get("item", "custom_1").name == "Ржавый ключ"


def test_runner_registry_is_cached_while_the_catalog_is_the_same(registry, cfg, tmp_path):
    bundle = key_world_bundle(registry)
    rig = make_rig(registry, cfg, tmp_path, scripted([text_step("Тихо.")]), bundle=bundle)
    assert rig.runner.registry is rig.runner.registry


def test_turn_with_give_custom_item_adds_the_item_to_the_runner_registry(registry, cfg, tmp_path):
    steps = [tools_step(give_call()), text_step("Вам вручают ключ.")]
    rig = make_rig(registry, cfg, tmp_path, scripted(steps))
    result = rig.runner.play("Беру ключ")
    assert result.committed is True
    assert result.requests == ["give_custom_item"]
    assert rig.runner.registry.get("item", "custom_1").name == "Ржавый ключ"
    assert registry.has("item", "custom_1") is False


def test_turn_with_give_custom_item_puts_it_in_the_hero_inventory(registry, cfg, tmp_path):
    steps = [tools_step(give_call()), text_step("Вам вручают ключ.")]
    rig = make_rig(registry, cfg, tmp_path, scripted(steps))
    rig.runner.play("Беру ключ")
    hero = rig.runner.bundle.heroes[0]
    assert [e.item_id for e in hero.inventory].count("custom_1") == 1
    assert rig.runner.bundle.world.custom_items["custom_1"].quest is True


def test_give_and_take_in_one_turn_both_apply(registry, cfg, tmp_path):
    steps = [tools_step(give_call(), take_call()), text_step("Ключ отдан.")]
    rig = make_rig(registry, cfg, tmp_path, scripted(steps))
    result = rig.runner.play("Отдаю ключ")
    assert result.committed is True
    assert result.requests == ["give_custom_item", "take_item"]
    hero = rig.runner.bundle.heroes[0]
    assert all(e.item_id != "custom_1" for e in hero.inventory)
    assert "custom_1" in rig.runner.bundle.world.custom_items


def test_failed_turn_leaves_no_custom_item(registry, cfg, tmp_path):
    steps = [tools_step(give_call())] + FATAL
    rig = make_rig(registry, cfg, tmp_path, scripted(steps))
    before = rig.runner.bundle.model_dump_json()
    result = rig.runner.play("Беру ключ")
    assert result.committed is False
    assert rig.runner.bundle.model_dump_json() == before
    assert rig.runner.bundle.world.custom_items == {}
    assert rig.runner.registry.has("item", "custom_1") is False


def test_second_turn_gives_the_next_id(registry, cfg, tmp_path):
    steps = [
        tools_step(give_call()), text_step("Раз."),
        tools_step(give_call(name="Записка", quest=False)), text_step("Два."),
    ]
    rig = make_rig(registry, cfg, tmp_path, scripted(steps))
    rig.runner.play("a")
    rig.runner.play("b")
    assert set(rig.runner.bundle.world.custom_items) == {"custom_1", "custom_2"}
    assert rig.runner.registry.has("item", "custom_2")


def test_app_registry_comes_from_the_runner(registry, tmp_path):
    bundle = key_world_bundle(registry)
    app = make_app(registry, tmp_path, scripted([text_step("Тихо.")]), bundle=bundle)
    assert app.registry is app.runner.registry
    assert app.registry.has("item", "custom_1")


def test_app_keeps_the_base_registry(registry, tmp_path):
    app = make_app(registry, tmp_path, scripted([text_step("Тихо.")]))
    assert app.base_registry is registry
    assert app.registry.has("item", "custom_1") is False


def test_app_registry_sees_an_item_given_in_a_turn(registry, tmp_path):
    steps = [tools_step(give_call()), text_step("Вам вручают ключ.")]
    app = make_app(registry, tmp_path, scripted(steps))
    app.runner.play("Беру ключ")
    assert app.registry.get("item", "custom_1").name == "Ржавый ключ"
