import re
from dataclasses import dataclass, field, replace

from ai_dm.combat.available import HIDDEN_KINDS

# Меню хода героя: цель + действия против неё, короткий блок бесцелевых, остальное в «Ещё…».
# Слой отображения поверх плоского списка вариантов: движок и нумерация протокола не меняются.
# Особые стрелы лука (≥ 2 вида) сворачиваются в «Стрелы ▸» под строкой лука.
MAX_ROWS = 10
SPELLS_INLINE = 2
BACK_LABEL = "← Назад"
MORE_LABEL = "Ещё…"
MOVE_LABEL = "Идти ▸"
SPELLS_TARGET_LABEL = "Заклинания на цель ▸"
SPELLS_FREE_LABEL = "Заклинания без цели ▸"
AMMO_LABEL = "Стрелы ▸"
AMMO_INLINE = 1
AMMO_GROUP = "ammo:"
NO_STUN_NOTE = " (дальнобойным — не оглушить)"
# новый kind без записи уезжает в «Ещё…»
CATEGORY_BY_KIND = {
    **dict.fromkeys(("attack", "parley", "disarm"), "target"),
    **dict.fromkeys(("cast", "transfer_mark"), "spell"),
    "move": "move",
    **dict.fromkeys(("dash", "disengage", "dodge", "second_wind", "stabilize"), "free"),
    **dict.fromkeys(("multiattack", "end_turn", "escape"), "free"),
}
# чем меньше, тем позже строку вытесняют в «Ещё…» при нехватке места; оружие вытесняется последним
RANK_BY_KIND = {
    "escape": -2,
    "end_turn": -1,
    **dict.fromkeys(("attack", "stabilize", "multiattack"), 0),
    "move": 1,
    **dict.fromkeys(("dodge", "second_wind"), 2),
    **dict.fromkeys(("dash", "disengage", "cast", "transfer_mark"), 3),
    **dict.fromkeys(("parley", "disarm"), 5),
}
SPECIAL_FREE = ("end_turn", "escape")
TARGET_PARAM_KINDS = ("attack", "cast", "transfer_mark", "parley", "disarm")
SUFFIX = re.compile(r" \(ещё (\d+) из 2\)$")
NAME = re.compile(r" → [^()]*?(?= \(|$)")
AMMO_PREFIX = re.compile(r"^Атака: .*? — ")


@dataclass
class TargetChip:
    # враг-цель: ref, имя, HP «7/7»; rank: 0 -- своя зона, 1 -- соседняя, 2 -- дальше
    ref: str
    name: str
    hp_text: str
    rank: int = 0


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


@dataclass
class MenuView:
    target: str | None
    targets: list
    header: str = ""
    target_rows: list = field(default_factory=list)
    free_rows: list = field(default_factory=list)
    more: list = field(default_factory=list)

    @property
    def rows(self):
        return self.target_rows + self.free_rows


def target_of(option):
    # ref цели варианта или None; для cast это может быть и зона/союзник -- решает build_view
    if option.kind == "help":
        return option.params.get("enemy")
    if option.kind in TARGET_PARAM_KINDS:
        return option.params.get("target")
    return None


def targets(options, roster):
    refs = {target_of(option) for option in options}
    return sorted([chip for chip in roster if chip.ref in refs], key=lambda chip: chip.rank)


def default_target(chips, last_target):
    refs = [chip.ref for chip in chips]
    if last_target in refs:
        return last_target
    return refs[0] if refs else None


def short_label(option, target=None):
    label = SUFFIX.sub("", option.label)
    if target is not None and target_of(option) == target:
        label = NAME.sub("", label)
    return label


def header_of(options):
    for option in options:
        found = SUFFIX.search(option.label)
        if option.kind == "attack" and found:
            return f"ещё {found.group(1)} из 2 атак"
    return ""


def clip(text, width):
    if len(text) <= width:
        return text
    return text[: width - 1] + "…"


def fit(rows, limit):
    # лишнее вытесняется: сначала самое «дешёвое» (большой rank), среди равных -- последнее
    rows = list(rows)
    while len(rows) > limit:
        worst = max(row.rank for row in rows)
        last = max(i for i, row in enumerate(rows) if row.rank == worst)
        del rows[last]
    return rows


def option_row(option, block, target=None, label=None):
    label = label or short_label(option, target)
    rank = RANK_BY_KIND.get(option.kind, 6)
    return MenuRow(label, option.id, rank=rank, block=block)


def attack_row(option, options, target, nonlethal):
    stun = [o for o in options if o.id == option.id + ":nonlethal"]
    if nonlethal and stun:
        return option_row(stun[0], "target", target)
    label = short_label(option, target)
    if nonlethal:
        label += NO_STUN_NOTE
    return option_row(option, "target", target, label)


def is_target_spell(option, target):
    return CATEGORY_BY_KIND.get(option.kind) == "spell" and target_of(option) == target


def is_free_spell(option, enemies):
    return option.kind == "cast" and target_of(option) not in enemies


def ammo_after(bow, options, target, nonlethal):
    # строки после атаки луком: группа «Стрелы ▸» или, если вид один, сама стрела;
    # id стрелы -- «attack:<лук>:<цель>:ammo:<стрела>»
    group = [MenuRow(AMMO_LABEL, kind="expand", group=f"{AMMO_GROUP}{bow.params['weapon']}")]
    ammo = [
        attack_row(o, options, target, nonlethal)
        for o in options
        if o.id.startswith(f"{bow.id}:ammo:")
    ]
    return group if len(ammo) > AMMO_INLINE else ammo


def target_block(options, target, nonlethal):
    if target is None:
        return []
    rows = []
    spells = []
    # стрелы -- после атаки своим луком (ammo_after), оглушающие версии -- через attack_row
    for option in [o for o in options if "ammo" not in o.params and not o.params.get("nonlethal")]:
        if is_target_spell(option, target):
            spells.append(option)
        elif CATEGORY_BY_KIND.get(option.kind) == "target" and target_of(option) == target:
            if option.kind == "attack":
                rows.append(attack_row(option, options, target, nonlethal))
                rows += ammo_after(option, options, target, nonlethal)
            else:
                rows.append(option_row(option, "target", target))
    if len(spells) <= SPELLS_INLINE:
        return rows + [option_row(option, "target", target) for option in spells]
    return rows + [MenuRow(SPELLS_TARGET_LABEL, kind="expand", group="spells_target", rank=3)]


def free_block(options, enemies):
    rows = [option_row(option, "free") for option in options if option.kind == "escape"]
    moves = [option for option in options if option.kind == "move"]
    if len(moves) > 1:
        rows.append(MenuRow(MOVE_LABEL, kind="expand", group="move", rank=1, block="free"))
    else:
        rows += [option_row(option, "free") for option in moves]
    for option in options:
        if CATEGORY_BY_KIND.get(option.kind) == "free" and option.kind not in SPECIAL_FREE:
            rows.append(option_row(option, "free"))
    if any(is_free_spell(option, enemies) for option in options):
        rows.append(
            MenuRow(SPELLS_FREE_LABEL, kind="expand", group="spells_free", rank=4, block="free")
        )
    return rows + [option_row(o, "free") for o in options if o.kind == "end_turn"]


def group_rows(options, target, enemies, group, nonlethal=False):
    if group.startswith(AMMO_GROUP):
        prefix = f"attack:{group[len(AMMO_GROUP) :]}:{target}:ammo:"
        ammo = [o for o in options if o.id.startswith(prefix)]
        rows = [attack_row(o, options, target, nonlethal) for o in ammo]
        # «Атака: лук — стрела (осталось 9)» -> «Стрела (осталось 9)»: в группе лук известен
        rows = [replace(row, label=AMMO_PREFIX.sub("", row.label).capitalize()) for row in rows]
        return [MenuRow(BACK_LABEL, kind="back")] + rows
    if group == "move":
        chosen = [option for option in options if option.kind == "move"]
    elif group == "spells_target":
        chosen = [option for option in options if is_target_spell(option, target)]
    else:
        chosen = [option for option in options if is_free_spell(option, enemies)]
    return [MenuRow(BACK_LABEL, kind="back")] + [option_row(o, "target", target) for o in chosen]


def number(rows):
    for index, row in enumerate(rows):
        row.key = str((index + 1) % 10) if index < MAX_ROWS else ""


def build_view(options, roster, target, nonlethal=False, expanded=None):
    options = [option for option in options if option.kind not in HIDDEN_KINDS]
    view = MenuView(target, targets(options, roster), header_of(options), more=list(options))
    enemies = {chip.ref for chip in roster}
    if expanded is not None:
        rows = group_rows(options, target, enemies, expanded, nonlethal)
        if len(rows) > MAX_ROWS:
            # длинная группа: хвост уходит в «Ещё…» (там полный список)
            rows = rows[: MAX_ROWS - 1] + [MenuRow(MORE_LABEL, kind="more", block="free")]
        view.target_rows = rows
        number(view.rows)
        return view
    rows = target_block(options, target, nonlethal) + free_block(options, enemies)
    kept = fit(rows, MAX_ROWS - 1)
    view.target_rows = [row for row in kept if row.block == "target"]
    view.free_rows = [row for row in kept if row.block == "free"]
    view.free_rows.append(MenuRow(MORE_LABEL, kind="more", block="free"))
    number(view.rows)
    return view


class MenuState:
    # состояние меню боя в TUI: варианты хода, цель (помнится между шагами боя), оглушающий,
    # раскрытая группа
    def __init__(self):
        self.active = False
        self.options = []
        self.roster = ()
        self.chips = []
        self.target = None
        self.nonlethal = False
        self.expanded = None
        self.combat_id = None

    def load(self, combat_id, options, roster):
        if combat_id != self.combat_id:
            self.combat_id = combat_id
            self.target = None
            self.nonlethal = False
        self.active = True
        self.options = list(options)
        self.roster = roster
        self.expanded = None
        self.chips = targets(self.options, roster)
        self.target = default_target(self.chips, self.target)

    def view(self):
        return build_view(self.options, self.roster, self.target, self.nonlethal, self.expanded)

    def row(self, row_number):
        rows = self.view().rows
        return rows[row_number - 1] if 1 <= row_number <= len(rows) else None

    def set_target(self, ref):
        if ref in [chip.ref for chip in self.chips]:
            self.target = ref
            self.expanded = None

    def shift(self, step):
        refs = [chip.ref for chip in self.chips]
        if refs:
            self.set_target(refs[(refs.index(self.target) + step) % len(refs)])

    def find(self, option_id):
        # (плоский номер варианта, вариант) или None, если такого уже нет
        for index, option in enumerate(self.options, start=1):
            if option.id == option_id:
                return index, option
        return None
