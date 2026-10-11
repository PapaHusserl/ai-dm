# Б3 (B3-PLAN A2): ImportPromptBuilder -- запрос роли import (режим pack_import).
# system[0] -- import_rules.md, system[1] -- справочник, оба cache=True; messages[0] -- campaign_id
# и выжимка. Префикс (tools + system) не зависит от выжимки (кэш).
import json
import sys
from importlib import resources
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "game"))

from import_kit import import_task, summary_text  # noqa: E402
from master_kit import app_cfg  # noqa: E402

from ai_dm.master.importer import ImportPromptBuilder  # noqa: E402
from ai_dm.protocol.context import CreationContext  # noqa: E402


def build(registry, cfg, text=None, model=None, task=None):
    ctx = CreationContext(registry, cfg, task or import_task())
    builder = ImportPromptBuilder(app_cfg(), model=model)
    return builder.build(ctx, summary_text() if text is None else text, "pack_import")


def reference(request):
    return json.loads(request.system[1].text)


def rules_file():
    path = resources.files("ai_dm.master") / "prompts" / "import_rules.md"
    return path.read_text(encoding="utf-8")


def test_role_is_import(registry, cfg):
    assert build(registry, cfg).role == "import"


def test_model_and_limits_come_from_import_role(registry, cfg):
    request = build(registry, cfg)
    role = app_cfg().roles.import_
    assert request.model == role.model
    assert request.max_tokens == role.max_tokens
    assert request.effort == role.effort
    assert request.max_tokens == 32000


def test_explicit_model_is_used_with_its_profile_role(registry, cfg):
    request = build(registry, cfg, model="gemini-3.8-flash")
    assert request.model == "gemini-3.8-flash"
    assert request.max_tokens == app_cfg().profiles["gemini"].import_.max_tokens


def test_system_has_two_blocks_both_cached(registry, cfg):
    request = build(registry, cfg)
    assert len(request.system) == 2
    assert [b.cache for b in request.system] == [True, True]


def test_system0_is_import_rules_file(registry, cfg):
    request = build(registry, cfg)
    assert request.system[0].text == rules_file()


def test_rules_name_the_tool_and_the_start_location_and_forbid_inventing():
    text = rules_file()
    assert "pack" in text
    assert "hero_location" in text
    assert "не выдумывать" in text


def test_tools_are_the_pack_set(registry, cfg):
    request = build(registry, cfg)
    assert [t.name for t in request.tools] == ["pack"]
    assert request.tools[0].strict is True


def test_reference_has_species_and_items(registry, cfg):
    data = reference(build(registry, cfg))
    assert "human" in data["species_ids"]
    assert "elf" in data["species_ids"]
    assert "crowbar" in data["item_ids"]
    assert data["species_ids"] == sorted(data["species_ids"])


def test_reference_items_exclude_world_items(registry, cfg):
    data = reference(build(registry, cfg))
    world_ids = {i.id for i in registry.all("item") if i.source == "world"}
    assert not world_ids & set(data["item_ids"])


def test_reference_trade_kinds_come_from_config(registry, cfg):
    data = reference(build(registry, cfg))
    assert data["trade_kinds"] == sorted(cfg.trade.presets)
    assert "smith" in data["trade_kinds"]


def test_reference_has_all_seven_condition_kinds(registry, cfg):
    kinds = reference(build(registry, cfg))["condition_kinds"]
    assert set(kinds) == {
        "narrative", "flag", "hero_has", "hero_at", "npc_status", "attitude", "favor",
    }
    assert all(kinds.values())


def test_reference_tone_axes_list_values_and_none(registry, cfg):
    axes = reference(build(registry, cfg))["tone_axes"]
    assert axes["violence"] == ["мягко", "реалистично", "жестоко", "none"]
    assert axes["horror"] == ["нет", "умеренно", "сильно", "none"]
    assert axes["romance"] == ["нет", "намёки", "чувственно", "откровенно", "none"]
    assert axes["language"] == ["сдержанно", "грубо", "none"]


def test_reference_calendar_is_twelve_by_thirty(registry, cfg):
    calendar = reference(build(registry, cfg))["calendar"]
    assert calendar["months"] == 12
    assert calendar["days_per_month"] == 30
    assert calendar["date"] == "YYYY-MM-DD"
    assert calendar["time"] == "HH:MM"


def test_reference_has_limits_and_required(registry, cfg):
    data = reference(build(registry, cfg))
    assert data["limits"]["means_min"] == 1
    assert data["limits"]["means_max"] == 3
    assert data["required"]["locations_min"] == 1
    assert "hero_location" in data["required"]


def test_message_is_marked_for_cache(registry, cfg):
    assert build(registry, cfg).messages[0].cache is True


def test_message_has_campaign_id_and_summary(registry, cfg):
    request = build(registry, cfg, text="Выжимка про дракона.", task=import_task("dragon_pack"))
    [message] = request.messages
    assert message.role == "user"
    data = json.loads(message.content[0].text)
    assert data == {"campaign_id": "dragon_pack", "summary": "Выжимка про дракона."}


def test_prefix_is_byte_identical_for_different_summaries(registry, cfg):
    first = build(registry, cfg, text="Первая выжимка.", task=import_task("a"))
    second = build(registry, cfg, text="Совсем другая выжимка, длиннее.", task=import_task("b"))
    assert [b.model_dump_json() for b in first.system] == [
        b.model_dump_json() for b in second.system
    ]
    assert [t.model_dump_json() for t in first.tools] == [
        t.model_dump_json() for t in second.tools
    ]


def test_world_text_argument_is_ignored(registry, cfg):
    ctx = CreationContext(registry, cfg, import_task())
    builder = ImportPromptBuilder(app_cfg())
    first = builder.build(ctx, "а", "pack_import")
    second = builder.build(ctx, "а", "pack_import", world_text="Мир.")
    assert first.model_dump_json() == second.model_dump_json()


# find_role_cfg

def test_find_role_cfg_without_model_is_default_role():
    builder = ImportPromptBuilder(app_cfg())
    assert builder.find_role_cfg(None) is builder.app_cfg.roles.import_


def test_find_role_cfg_finds_model_in_other_profile():
    app = app_cfg().model_copy(deep=True)
    app.profiles["gemini"].import_.max_tokens = 111
    builder = ImportPromptBuilder(app)
    assert builder.find_role_cfg("gemini-3.8-flash").max_tokens == 111


def test_find_role_cfg_finds_model_of_anthropic_profile():
    app = app_cfg().model_copy(deep=True)
    app.profiles["anthropic"].import_.max_tokens = 222
    app.roles.import_.model = "gemini-3.8-flash"
    builder = ImportPromptBuilder(app)
    assert builder.find_role_cfg("claude-sonnet-5-5").max_tokens == 222


def test_find_role_cfg_unknown_model_falls_back_to_default():
    app = app_cfg()
    builder = ImportPromptBuilder(app)
    assert builder.find_role_cfg("unknown-model") is app.roles.import_
    assert ImportPromptBuilder(app, model="unknown-model").model == "unknown-model"
