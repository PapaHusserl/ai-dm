# К3б П4, решение 39 (docs/plan-k3b.md): рассказчик видит призванных героя теми же данными, что
# /sheet: «Скелет (HP N/M, до HH:MM)», «Ястреб (HP N/M)»; истёкший не виден. Точное имя ключа не
# фиксируется -- проверяется текст блока hero.
import json

from master_kit import app_cfg, make_bundle, make_ctx

from ai_dm.master.prompt import PromptBuilder
from ai_dm.state.hero import Minion

HOUR = 3600


def hero_text(registry, cfg, *minions):
    bundle = make_bundle(registry)
    bundle.heroes[0].minions = list(minions)
    ctx = make_ctx(registry, cfg, bundle=bundle)
    request = PromptBuilder(app_cfg()).build(ctx, "Осматриваюсь.", "explore")
    data = json.loads(request.messages[0].content[0].text)["hero"]
    return json.dumps(data, ensure_ascii=False), bundle.world.clock.now_s


def skeleton(until_s, hp=5):
    return Minion(monster_id="skeleton", spell_id="animate_dead", hp_current=hp, until_s=until_s)


def hawk():
    return Minion(monster_id="hawk", spell_id="find_familiar", hp_current=1, until_s=None)


def test_prompt_names_the_skeleton_with_hp(registry, cfg):
    now_s = make_bundle(registry).world.clock.now_s
    text, _ = hero_text(registry, cfg, skeleton(now_s + HOUR))
    assert "Скелет (HP 5/13" in text


def test_prompt_names_the_hawk_with_hp(registry, cfg):
    text, _ = hero_text(registry, cfg, hawk())
    assert "Ястреб (HP 1/1)" in text


def test_prompt_hides_an_expired_minion(registry, cfg):
    now_s = make_bundle(registry).world.clock.now_s
    text, _ = hero_text(registry, cfg, skeleton(now_s - 1))
    assert "Скелет" not in text


def test_prompt_hero_minions_key_is_a_list_of_lines(registry, cfg):
    from ai_dm.game.sheet_text import until_text

    bundle = make_bundle(registry)
    now_s = bundle.world.clock.now_s
    until = now_s + HOUR
    bundle.heroes[0].minions = [skeleton(until)]
    ctx = make_ctx(registry, cfg, bundle=bundle)
    request = PromptBuilder(app_cfg()).build(ctx, "Осматриваюсь.", "explore")
    data = json.loads(request.messages[0].content[0].text)["hero"]
    assert data["minions"] == [f"Скелет (HP 5/13, {until_text(until, now_s)})"]


def test_prompt_without_minions_has_no_summoned_word(registry, cfg):
    text, _ = hero_text(registry, cfg)
    assert "Призванные" not in text and "Скелет" not in text
