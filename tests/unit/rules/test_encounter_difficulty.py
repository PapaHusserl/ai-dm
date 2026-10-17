# Партия К7к, п. 3.1: сложность кампании задаёт уровень бюджета боя (docs/plan-k7k.md, В3а).
#   DIFFICULTY_TIERS = {"easy": "low", "normal": "moderate", "hard": "high"};
#   tier_of(world, cfg) -> str: world.settings["difficulty"] через словарь; нет или неизвестно
#   (в том числе не строка) -> cfg.encounter.tier;
#   party_budget(levels, registry, tier) и budget_text(level, budget, enemies, registry, tier)
#   получают уровень строкой (low/moderate/high), не cfg; таблица encounter_budget:
#   ур. 1 -- 50 / 75 / 100 ПО;
#   start_combat считает tier_of один раз: бюджет и строка «Бюджет боя: N ПО (ур. L, <слово>)»
#   идут по сложности мира; основания сверх бюджета (warn_danger, hero) работают как раньше.
import pytest
from protocol_kit import combat_request, goblin, make_bundle, make_ctx, req, zone

from ai_dm.config.settings import load_rules_config
from ai_dm.protocol.apply import apply
from ai_dm.rules.encounter import DIFFICULTY_TIERS, budget_text, party_budget, tier_of
from ai_dm.state.world import DangerMark


def plain_world(registry, **settings):
    world = make_bundle(registry).world
    world.settings.update(settings)
    return world


def high_cfg():
    return load_rules_config(toml_text='[encounter]\ntier = "high"\n')


class Spec:
    def __init__(self, monster_id):
        self.monster_id = monster_id


def refs_of(ctx):
    state = ctx.bundle.session.active_combat
    return [p.ref for p in state.participants if p.side == "enemies"]


def fight(registry, cfg, difficulty, count, **fields):
    ctx = make_ctx(registry, cfg)
    if difficulty is not None:
        ctx.bundle.world.settings["difficulty"] = difficulty
    zones = [zone("door", ["hall"]), zone("hall", ["door", "balcony"]), zone("balcony", ["hall"])]
    enemies = [goblin(f"g{n}") for n in range(1, count + 1)]
    groups = [{"id": "goblins", "leader": "g1", "intent": "kill"}]
    request = req(
        "start_combat", zones=zones, enemies=enemies, groups=groups, hero_zone="door", **fields
    )
    return ctx, apply(ctx, request)


# словарь

def test_difficulty_tiers_mapping():
    assert DIFFICULTY_TIERS == {"easy": "low", "normal": "moderate", "hard": "high"}


# tier_of

def test_tier_of_without_setting_follows_the_config(registry, cfg):
    assert tier_of(plain_world(registry), cfg) == "moderate"


def test_tier_of_without_setting_follows_a_changed_config(registry):
    assert tier_of(plain_world(registry), high_cfg()) == "high"


@pytest.mark.parametrize(
    "value, tier", [("easy", "low"), ("normal", "moderate"), ("hard", "high")]
)
def test_tier_of_maps_difficulty(registry, cfg, value, tier):
    assert tier_of(plain_world(registry, difficulty=value), cfg) == tier


def test_setting_wins_over_the_config(registry):
    assert tier_of(plain_world(registry, difficulty="normal"), high_cfg()) == "moderate"


@pytest.mark.parametrize("junk", ["epic", "", "Easy", 3, True])
def test_tier_of_garbage_falls_back_to_the_config(registry, cfg, junk):
    assert tier_of(plain_world(registry, difficulty=junk), cfg) == "moderate"


def test_tier_of_garbage_falls_back_to_a_changed_config(registry):
    assert tier_of(plain_world(registry, difficulty="epic"), high_cfg()) == "high"


def test_tier_of_ignores_other_settings(registry, cfg):
    assert tier_of(plain_world(registry, tone="hard"), cfg) == "moderate"


# party_budget, budget_text

@pytest.mark.parametrize("tier, budget", [("low", 50), ("moderate", 75), ("high", 100)])
def test_party_budget_by_tier_level_1(registry, tier, budget):
    assert party_budget([1], registry, tier) == budget


def test_party_budget_matches_the_table(registry):
    rows = registry.get("table", "encounter_budget").rows
    assert party_budget([1], registry, "low") == rows["1:low"]
    assert party_budget([1], registry, "high") == rows["1:high"]


def test_party_budget_sums_heroes(registry):
    rows = registry.get("table", "encounter_budget").rows
    assert party_budget([1, 3], registry, "high") == rows["1:high"] + rows["3:high"]


def test_budget_text_names_the_tier(registry):
    text = budget_text(1, 50, [Spec("goblin_warrior")], registry, "low")
    assert text == "Бюджет боя: 50 ПО (ур. 1, лёгкий); враги: 50 ПО (Воин-гоблин 50 ×1)"


@pytest.mark.parametrize(
    "tier, word", [("low", "лёгкий"), ("moderate", "умеренный"), ("high", "тяжёлый")]
)
def test_budget_text_tier_words(registry, tier, word):
    text = budget_text(2, 100, [Spec("goblin_warrior")], registry, tier)
    assert f"(ур. 2, {word})" in text


# start_combat

def test_without_setting_budget_is_moderate(registry, cfg):
    ctx, d = fight(registry, cfg, None, 1)
    assert any("Бюджет боя: 75 ПО (ур. 1, умеренный)" in line for line in d.log)


def test_easy_clamps_two_goblins_to_one(registry, cfg):
    ctx, d = fight(registry, cfg, "easy", 2)
    assert d.status == "clamped"
    assert refs_of(ctx) == ["g1"]


def test_easy_budget_line(registry, cfg):
    _, d = fight(registry, cfg, "easy", 2)
    assert "Бюджет боя: 50 ПО (ур. 1, лёгкий); враги: 50 ПО (Воин-гоблин 50 ×1)" in d.log


def test_easy_keeps_one_goblin(registry, cfg):
    ctx, d = fight(registry, cfg, "easy", 1)
    assert d.status == "accepted"
    assert refs_of(ctx) == ["g1"]


def test_normal_clamps_two_goblins_as_before(registry, cfg):
    ctx, d = fight(registry, cfg, "normal", 2)
    assert d.status == "clamped"
    assert "Бюджет боя: 75 ПО (ур. 1, умеренный); враги: 50 ПО (Воин-гоблин 50 ×1)" in d.log


def test_hard_lets_two_goblins_in(registry, cfg):
    ctx, d = fight(registry, cfg, "hard", 2)
    assert d.status == "accepted"
    assert refs_of(ctx) == ["g1", "g2"]


def test_hard_budget_line(registry, cfg):
    _, d = fight(registry, cfg, "hard", 2)
    assert "Бюджет боя: 100 ПО (ур. 1, тяжёлый); враги: 100 ПО (Воин-гоблин 50 ×2)" in d.log


def test_hard_still_clamps_three_goblins(registry, cfg):
    ctx, d = fight(registry, cfg, "hard", 3)
    assert d.status == "clamped"
    assert refs_of(ctx) == ["g1", "g2"]


def test_setting_wins_over_a_high_config_in_start_combat(registry):
    ctx, d = fight(registry, high_cfg(), "normal", 2)
    assert d.status == "clamped"


def test_garbage_setting_uses_the_config_in_start_combat(registry, cfg):
    ctx, d = fight(registry, cfg, "epic", 2)
    assert d.status == "clamped"
    assert any("Бюджет боя: 75 ПО (ур. 1, умеренный)" in line for line in d.log)


def test_warn_danger_on_easy_still_lifts_the_clamp(registry, cfg):
    ctx = make_ctx(registry, cfg)
    ctx.bundle.world.settings["difficulty"] = "easy"
    ctx.bundle.world.dangers.append(DangerMark(location_id="vale", text="кости", at_s=0))
    d = apply(ctx, combat_request(
        enemies=[goblin("g1"), goblin("g2"), goblin("g3")], initiated_by="enemies"
    ))
    assert d.status == "accepted"
    assert ctx.bundle.session.active_combat.budget_override_reason == "warn_danger"
    assert len(refs_of(ctx)) == 3


def test_hero_initiative_on_easy_is_not_clamped(registry, cfg):
    ctx = make_ctx(registry, cfg)
    ctx.bundle.world.settings["difficulty"] = "easy"
    d = apply(ctx, combat_request(enemies=[goblin("g1"), goblin("g2")], initiated_by="hero"))
    assert d.status == "accepted"
    assert ctx.bundle.session.active_combat.budget_override_reason == "hero"


def test_higher_level_budget_follows_the_tier(registry, cfg):
    ctx = make_ctx(registry, cfg)
    ctx.hero.sheet.primary.level = 5
    ctx.bundle.world.settings["difficulty"] = "easy"
    rows = registry.get("table", "encounter_budget").rows
    d = apply(ctx, combat_request(enemies=[goblin("g1")], initiated_by="enemies"))
    assert any(f"Бюджет боя: {rows['5:low']} ПО (ур. 5, лёгкий)" in line for line in d.log)


def test_budget_text_unknown_tier_is_printed_as_is(registry):
    text = budget_text(1, 50, [Spec("goblin_warrior")], registry, "weird")
    assert "(ур. 1, weird)" in text


def test_budget_text_sums_kinds_and_lists_them_in_order(registry):
    enemies = [Spec("goblin_warrior"), Spec("goblin_boss"), Spec("goblin_warrior")]
    assert budget_text(1, 100, enemies, registry, "high") == (
        "Бюджет боя: 100 ПО (ур. 1, тяжёлый); "
        "враги: 300 ПО (Воин-гоблин 50 ×2, Босс гоблинов 200 ×1)"
    )
