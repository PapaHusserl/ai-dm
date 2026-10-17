# К0а (docs/plan-k0.md, A7): снимки героя v4_dragon (Грей, 3 ур. следопыт / Повелитель зверей),
# снятые движком main ДО партии (tests/golden/k0_*): лист /sheet, sheet_data промпта + ячейки +
# пулы,
# меню уровня 3 -> 4. Те же функции дают снимки на движке v9 -- они обязаны совпасть.
# Ключ пула костей хитов приводится к старому виду ("hit_dice:d10" -> "hit_dice"): сравниваются
# числа.
import json
import shutil
from pathlib import Path

from game_kit import ReactiveAdapter, make_app
from llm_kit import app_cfg
from persist_kit import load_slot

from ai_dm.content.loader import load_registry
from ai_dm.master.prompt import PromptBuilder
from ai_dm.rules.derived import resource_maxes, spell_slots

TESTS = Path(__file__).resolve().parents[2]
FIXTURE_V4_DRAGON = TESTS / "fixtures" / "saves" / "v4_dragon"
GOLDEN = TESTS / "golden"
BACKUP_TS = "20260101T000000Z"
DRAGON_CONTENT = TESTS.parent / "campaigns" / "drunk_dragon" / "content"


def dragon_registry():
    # у Грея предметы пака drunk_dragon (мифриловая рубашка и др.)
    return load_registry([DRAGON_CONTENT])


def load_dragon(saves):
    target = saves / "dd" / "slots" / "auto"
    shutil.copytree(FIXTURE_V4_DRAGON, target)
    return load_slot(saves, "dd", "auto", backup_ts=BACKUP_TS)


def old_pool_key(key):
    if key.startswith("hit_dice:"):
        return "hit_dice"
    return key


def old_pools(pools):
    return {old_pool_key(key): value for key, value in pools.items()}


def sheet_snapshot(registry, tmp_path, bundle):
    app = make_app(registry, tmp_path, ReactiveAdapter(), bundle=bundle)
    return "\n".join(app.handle("/sheet").lines) + "\n"


def sheet_data_snapshot(registry, bundle):
    hero = bundle.heroes[0]
    builder = PromptBuilder(app_cfg())
    resources = {
        key: {"current": pool.current, "max": pool.max}
        for key, pool in hero.creature.resources.items()
    }
    data = {
        "sheet_data": builder.sheet_data(hero, registry),
        "spell_slots": {str(k): v for k, v in spell_slots(hero, registry).items()},
        "resource_maxes": old_pools(resource_maxes(hero, registry)),
        "resources": old_pools(resources),
    }
    return json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def menu_snapshot(registry, hero):
    # то же, что сняли на main через level_up + next_choice, но через меню v9 (pending_level)
    from ai_dm.rules.level_up import begin_level_up, current_step, preview_hero, step_options

    copy = hero.model_copy(deep=True)
    pending = begin_level_up(copy, registry, hp_method="average")
    steps = []
    while True:
        step = current_step(copy, registry)
        if step is None:
            break
        options = step_options(copy, registry)
        steps.append({"step": step, "options": options})
        draft = copy.pending_level.draft
        if step == "asi_or_feat":
            first, _, second = options[0].partition("+")
            draft.asi = {first: 2} if second == "2" else {first: 1, second: 1}
        elif step == "spells":
            draft.spells_add.append(options[0])
        else:
            raise AssertionError("неожиданный шаг " + step)
    out = {"hp_gain": pending.hp_gain, "level": preview_hero(copy, registry).sheet.level,
        "steps": steps}
    return json.dumps(out, ensure_ascii=False, indent=2) + "\n"
