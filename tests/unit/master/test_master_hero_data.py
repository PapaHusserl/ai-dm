# state_data.hero: класс, подкласс, умения, заклинания, ячейки и спутник героя
# (docs/plan-ranger-2-5.md, разд. 5 п. 11). Ожидаемые ключи hero:
#   class -- id класса; subclass -- id подкласса или None; features -- список {id, name,
#   description} текстовых и выбранных умений; spells_prepared -- sheet.spells_prepared;
#   spell_slots -- {"<круг>": {"current": int, "max": int}}; favored_enemy -- {"current", "max"}
#   у следопыта; companion -- {name, kind, notes}, у героя без спутника ключа нет или None.
import json
from importlib import resources

from master_kit import app_cfg, make_bundle, make_ctx

from ai_dm.game.starter import ranger_choices
from ai_dm.master.prompt import PromptBuilder
from ai_dm.rules.builder import build_character
from ai_dm.rules.progression import sync_resources
from ai_dm.state.hero import Companion


def grey_ctx(registry, cfg, subclass="beast_master", companion=True):
    bundle = make_bundle(registry)
    old = bundle.heroes[0]
    hero = build_character(ranger_choices("hero"), registry)
    hero.location_id = old.location_id
    hero.sheet.primary.level = 3
    hero.sheet.primary.subclass_id = subclass
    hero.sheet.prepared_of()[:] = ["cure_wounds", "fog_cloud"]
    sync_resources(hero, registry)
    if companion:
        hero.companions = [Companion(name="Акела", kind="волк", notes="доверен Йоргеном")]
    bundle.heroes[0] = hero
    return make_ctx(registry, cfg, bundle=bundle)


def hero_data(ctx):
    request = PromptBuilder(app_cfg()).build(ctx, "Осматриваюсь.", "explore")
    return json.loads(request.messages[0].content[0].text)["hero"]


def test_hero_data_has_class_and_subclass(registry, cfg):
    data = hero_data(grey_ctx(registry, cfg))
    assert data["class"] == "ranger"
    assert data["subclass"] == "beast_master"


def test_hero_data_has_prepared_spells(registry, cfg):
    data = hero_data(grey_ctx(registry, cfg))
    assert "cure_wounds" in data["spells_prepared"]
    assert "fog_cloud" in data["spells_prepared"]


def test_hero_data_has_spell_slots_with_current_and_max(registry, cfg):
    data = hero_data(grey_ctx(registry, cfg))
    assert data["spell_slots"]["1"] == {"current": 3, "max": 3}


def test_hero_data_slots_follow_current_value(registry, cfg):
    ctx = grey_ctx(registry, cfg)
    ctx.bundle.heroes[0].creature.resources["spell_slot:1"].current = 1
    assert hero_data(ctx)["spell_slots"]["1"] == {"current": 1, "max": 3}


def test_hero_data_has_favored_enemy_uses(registry, cfg):
    assert hero_data(grey_ctx(registry, cfg))["favored_enemy"] == {"current": 2, "max": 2}


def test_hero_data_has_hit_dice(registry, cfg):
    assert hero_data(grey_ctx(registry, cfg))["hit_dice"] == {"current": 3, "max": 3}


def test_hero_data_hit_dice_follow_current_value(registry, cfg):
    ctx = grey_ctx(registry, cfg)
    ctx.bundle.heroes[0].creature.resources["hit_dice:d10"].current = 2
    assert hero_data(ctx)["hit_dice"] == {"current": 2, "max": 3}


def test_hero_data_hit_dice_drop_after_a_short_rest_with_one_die(registry, cfg):
    from protocol_kit import req

    from ai_dm.protocol.apply import apply

    ctx = grey_ctx(registry, cfg)
    ctx.bundle.heroes[0].creature.hp_current = 1
    apply(ctx, req("rest", kind="short", hit_dice=1))
    assert hero_data(ctx)["hit_dice"] == {"current": 2, "max": 3}


def test_hero_data_hit_dice_sum_over_several_pools(registry, cfg):
    from ai_dm.state.creature import ResourcePool

    ctx = grey_ctx(registry, cfg)
    ctx.bundle.heroes[0].creature.resources["hit_dice:d8"] = ResourcePool(current=1, max=2)
    assert hero_data(ctx)["hit_dice"] == {"current": 4, "max": 5}


def test_hero_data_without_hit_dice_pools_has_no_key(registry, cfg):
    ctx = grey_ctx(registry, cfg)
    resources = ctx.bundle.heroes[0].creature.resources
    for name in [n for n in resources if n.startswith("hit_dice:")]:
        del resources[name]
    assert "hit_dice" not in hero_data(ctx)


def test_rules_say_short_rest_hit_dice_not_above_current():
    text = (resources.files("ai_dm.master") / "prompts" / "narrator_rules.md").read_text(
        encoding="utf-8"
    )
    assert "`hit_dice`" in text
    assert "не больше `current`" in text


def test_hero_data_has_companion(registry, cfg):
    companion = hero_data(grey_ctx(registry, cfg))["companion"]
    assert companion["name"] == "Акела"
    assert companion["kind"] == "волк"
    assert companion["notes"] == "доверен Йоргеном"


def test_hero_data_without_companion_has_no_companion(registry, cfg):
    data = hero_data(grey_ctx(registry, cfg, companion=False))
    assert data.get("companion") is None


def test_hero_data_lists_text_features_of_the_subclass(registry, cfg):
    ids = [f["id"] for f in hero_data(grey_ctx(registry, cfg))["features"]]
    assert "beast_companion" in ids
    assert "pack_sense" in ids


def test_hero_data_features_have_name_and_description(registry, cfg):
    features = hero_data(grey_ctx(registry, cfg))["features"]
    companion = [f for f in features if f["id"] == "beast_companion"][0]
    assert companion["name"]
    assert companion["description"]


def test_hero_data_of_hunter_has_no_beast_features(registry, cfg):
    ctx = grey_ctx(registry, cfg, subclass="hunter", companion=False)
    ids = [f["id"] for f in hero_data(ctx)["features"]]
    assert "beast_companion" not in ids
    assert "pack_sense" not in ids


def test_hero_data_of_fighter_keeps_basic_fields(registry, cfg):
    data = hero_data(make_ctx(registry, cfg))
    assert data["name"] == "Арн"
    assert data["class"] == "fighter"
    assert data["level"] == 1
    assert data.get("companion") is None


def test_rules_say_companion_does_not_fight_before_stage_7():
    text = (resources.files("ai_dm.master") / "prompts" / "narrator_rules.md").read_text(
        encoding="utf-8"
    ).lower()
    assert "спутник" in text


# Б1а (B1-PLAN A4): means и background_description героя -- только когда непусты

def test_hero_data_has_means_when_hero_has_them(registry, cfg):
    ctx = make_ctx(registry, cfg)
    ctx.hero.means = ["острый ум", "старый долг"]
    assert hero_data(ctx)["means"] == ["острый ум", "старый долг"]


def test_hero_data_has_no_means_key_when_empty(registry, cfg):
    ctx = make_ctx(registry, cfg)
    ctx.hero.means = []
    assert "means" not in hero_data(ctx)


def test_hero_data_has_background_description_when_set(registry, cfg):
    ctx = make_ctx(registry, cfg)
    ctx.hero.sheet.background.description = "Вырос в бродячем цирке."
    assert hero_data(ctx)["background_description"] == "Вырос в бродячем цирке."


def test_hero_data_has_no_background_description_key_when_empty(registry, cfg):
    ctx = make_ctx(registry, cfg)
    ctx.hero.sheet.background.description = ""
    assert "background_description" not in hero_data(ctx)


def test_default_hero_data_has_neither_new_key(registry, cfg):
    data = hero_data(make_ctx(registry, cfg))
    assert "means" not in data
    assert "background_description" not in data


def test_hero_data_never_shows_opportunity(registry, cfg):
    from ai_dm.state.triggers import Trigger

    ctx = make_ctx(registry, cfg)
    ctx.hero.opportunity = [
        Trigger.model_validate({"id": "o1", "if": {"narrative": "x"}, "then": "тайный план"})
    ]
    request = PromptBuilder(app_cfg()).build(ctx, "Осматриваюсь.", "explore")
    assert "тайный план" not in request.messages[0].content[0].text
    assert "opportunity" not in hero_data(ctx)


def test_hero_data_of_srd_background_preset_is_built(registry, cfg):
    from ai_dm.game.starter import fighter_choices

    ctx = make_ctx(registry, cfg)
    ctx.bundle.heroes[0] = build_character(fighter_choices("hero"), registry)
    data = hero_data(ctx)
    assert data["name"] == "Арн"
    assert "means" not in data
    allowed = ("", registry.get("background", "soldier").description)
    assert data.get("background_description", "") in allowed


# К0а: спутников несколько -- в промпт идёт первый, форма ключа прежняя (docs/plan-k0.md, Q4)

def test_hero_data_companion_is_the_first_of_two(registry, cfg):
    from ai_dm.state.hero import Companion

    ctx = grey_ctx(registry, cfg)
    ctx.bundle.heroes[0].companions.append(Companion(name="Мунин", kind="ворон", notes=""))
    assert hero_data(ctx)["companion"]["name"] == "Акела"


def test_hero_data_companion_form_is_a_dict_of_three_fields(registry, cfg):
    companion = hero_data(grey_ctx(registry, cfg))["companion"]
    assert sorted(companion) == ["kind", "name", "notes"]


def test_hero_data_has_no_companions_key(registry, cfg):
    assert "companions" not in hero_data(grey_ctx(registry, cfg))


def test_hero_data_spells_prepared_are_the_class_list(registry, cfg):
    data = hero_data(grey_ctx(registry, cfg))
    assert data["spells_prepared"] == ["cure_wounds", "fog_cloud"]
    assert isinstance(data["spells_prepared"], list)


def test_hero_data_class_and_subclass_are_scalars(registry, cfg):
    data = hero_data(grey_ctx(registry, cfg))
    assert (data["class"], data["subclass"]) == ("ranger", "beast_master")


# Ф1 (BACKLOG 44): companion_due -- у Повелителя зверей нет зверя

def test_hero_data_has_companion_due_for_beast_master_without_beast(registry, cfg):
    data = hero_data(grey_ctx(registry, cfg, companion=False))
    assert data["companion_due"] is True
    assert "companion" not in data


def test_hero_data_with_companion_has_no_companion_due(registry, cfg):
    data = hero_data(grey_ctx(registry, cfg, companion=True))
    assert "companion_due" not in data
    assert data["companion"]["name"] == "Акела"


def test_hero_data_of_hunter_has_neither_companion_nor_due(registry, cfg):
    data = hero_data(grey_ctx(registry, cfg, subclass="hunter", companion=False))
    assert "companion_due" not in data
    assert "companion" not in data


# К1 (В7): в промпт идут только подготовленные заклинания; после смены -- новый список,
# снятые в промпт не попадают

def test_hero_data_after_a_swap_has_the_new_prepared_list(registry, cfg):
    from ai_dm.rules.spellcasting import swap_prepared

    ctx = grey_ctx(registry, cfg)
    swap_prepared(ctx.bundle.heroes[0], registry, ["fog_cloud"], ["longstrider"])
    data = hero_data(ctx)
    assert data["spells_prepared"] == ["cure_wounds", "longstrider"]
    assert "fog_cloud" not in data["spells_prepared"]


def test_hero_data_shows_the_second_circle_slots_when_the_hero_has_them(registry, cfg):
    ctx = grey_ctx(registry, cfg)
    hero = ctx.bundle.heroes[0]
    hero.sheet.primary.level = 5
    sync_resources(hero, registry)
    assert hero_data(ctx)["spell_slots"]["2"] == {"current": 2, "max": 2}
