import re
from dataclasses import dataclass

# Строка меню боя и её подпись: общая основа combat_menu и подгрупп вариантов (menu_variants).
BACK_LABEL = "← Назад"
# чем меньше, тем позже строку вытесняют в «Ещё…» при нехватке места; оружие вытесняется последним
RANK_BY_KIND = {
    "escape": -2,
    "end_turn": -1,
    **dict.fromkeys(("attack", "stabilize", "multiattack"), 0),
    **dict.fromkeys(("offhand_attack", "horde_breaker", "cleave"), 0),
    **dict.fromkeys(("summon_attack", "summon_move"), 0),
    "move": 1,
    **dict.fromkeys(("dodge", "second_wind", "action_surge", "steady_aim"), 2),
    **dict.fromkeys(("dash", "disengage", "hide_bonus", "cast", "transfer_mark"), 3),
    **dict.fromkeys(("parley", "disarm"), 5),
}
TARGET_PARAM_KINDS = (
    "attack", "cast", "transfer_mark", "parley", "disarm", "offhand_attack", "horde_breaker",
    "cleave", "summon_attack",
)
SUFFIX = re.compile(r" \(ещё (\d+) из 2\)$")
NAME = re.compile(r" → [^()]*?(?= \(|$)")


@dataclass
class MenuRow:
    # kind: option (option_id), expand (group), back, more
    label: str
    option_id: str | None = None
    kind: str = "option"
    group: str | None = None
    rank: int = 0
    block: str = "target"
    key: str = ""


def target_of(option):
    # ref цели варианта или None; для cast это может быть и зона/союзник -- решает build_view
    if option.kind == "help":
        return option.params.get("enemy")
    if option.kind in TARGET_PARAM_KINDS:
        return option.params.get("target")
    return None


def short_label(option, target=None):
    label = SUFFIX.sub("", option.label)
    if target is not None and target_of(option) == target:
        label = NAME.sub("", label)
    return label


def option_row(option, block, target=None, label=None):
    label = label or short_label(option, target)
    rank = RANK_BY_KIND.get(option.kind, 6)
    return MenuRow(label, option.id, rank=rank, block=block)
