from collections.abc import Sequence
from pathlib import Path

import yaml
from pydantic import ValidationError

from ai_dm.content import handlers
from ai_dm.content.models.backgrounds import Background
from ai_dm.content.models.classes import CharacterClass, Subclass
from ai_dm.content.models.common import DAMAGE_TYPE_WORDS
from ai_dm.content.models.conditions import Condition
from ai_dm.content.models.feats import Feat
from ai_dm.content.models.features import Feature
from ai_dm.content.models.items import Armor, Item, Mastery, Weapon
from ai_dm.content.models.monsters import Monster
from ai_dm.content.models.species import Species
from ai_dm.content.models.spells import Spell
from ai_dm.content.models.tables import Table
from ai_dm.content.monster_checks import check_monster_actions
from ai_dm.content.registry import ContentRegistry

SRD_DIR = Path(__file__).parent.parent / "srd" / "data"

# вид -> (папка слоя, модель)
KINDS = {
    "weapon": ("weapons", Weapon),
    "armor": ("armor", Armor),
    "class": ("classes", CharacterClass),
    "subclass": ("subclasses", Subclass),
    "species": ("species", Species),
    "background": ("backgrounds", Background),
    "feat": ("feats", Feat),
    "feature": ("features", Feature),
    "item": ("items", Item),
    "spell": ("spells", Spell),
    "condition": ("conditions", Condition),
    "monster": ("monsters", Monster),
    "mastery": ("masteries", Mastery),
    "table": ("tables", Table),
}


class ContentError(Exception):
    pass


class ContentConflictError(ContentError):
    def __init__(self, message, conflicts):
        super().__init__(message)
        self.conflicts = conflicts


def read_file(path, model):
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as err:
        raise ContentError(f"{path}: некорректный YAML: {err}") from err
    if not isinstance(data, dict):
        raise ContentError(f"{path}: ожидался один объект (mapping) на файл")
    try:
        return model.model_validate(data)
    except ValidationError as err:
        lines = []
        for e in err.errors():
            field = ".".join(str(part) for part in e["loc"])
            text = e["msg"]
            if e["type"] == "literal_error":
                text += f" (получено: {e['input']!r})"
            lines.append(f"{path}: поле {field or '-'}: {text}")
        raise ContentError("\n".join(lines)) from err


def layer_files(layer_dir, kind, folder):
    if kind == "subclass":
        return sorted((layer_dir / folder).glob("*/*.yaml"))
    return sorted((layer_dir / folder).glob("*.yaml"))


def check_monster_gear(monster, id, has, bad, items) -> None:
    # типы урона, состояния, доспех и щит монстра
    fields = ("damage_immunities", "damage_resistances", "damage_vulnerabilities")
    for field in fields:
        for damage_type in getattr(monster, field):
            if damage_type not in DAMAGE_TYPE_WORDS:
                bad("monster", id, field, f"неизвестный тип урона '{damage_type}'")
    for condition in monster.condition_immunities:
        if not has("condition", condition):
            bad("monster", id, "condition_immunities", f"неизвестное состояние '{condition}'")
    if monster.armor is not None and not (
        has("armor", monster.armor) and items["armor"][monster.armor].category != "shield"
    ):
        bad("monster", id, "armor", f"'{monster.armor}' не доспех")
    if monster.shield is not None and not (
        has("armor", monster.shield) and items["armor"][monster.shield].category == "shield"
    ):
        bad("monster", id, "shield", f"'{monster.shield}' не щит")


def check_refs(items, paths):
    errors = []

    def has(kind, id):
        return id in items[kind]

    def bad(kind, id, field, text):
        errors.append(f"{paths[(kind, id)]}: {kind} '{id}', поле {field}: {text}")

    for kind in items:
        for id, obj in items[kind].items():
            handler = getattr(obj, "handler", None)
            if handler is not None and not handlers.is_known_handler(handler.name):
                bad(kind, id, "handler.name", f"неизвестный обработчик '{handler.name}'")
    for id, weapon in items["weapon"].items():
        if weapon.mastery is not None and not has("mastery", weapon.mastery):
            bad("weapon", id, "mastery", f"неизвестное мастерство '{weapon.mastery}'")
    for kind in ("class", "subclass"):
        for id, obj in items[kind].items():
            for ref in obj.features:
                if not has("feature", ref.feature):
                    bad(kind, id, "features", f"неизвестное умение '{ref.feature}'")
    for id, feature in items["feature"].items():
        for option in feature.options:
            if not has("feature", option):
                bad("feature", id, "options", f"неизвестное умение '{option}'")
    for id, sub in items["subclass"].items():
        if not has("class", sub.class_id):
            bad("subclass", id, "class_id", f"неизвестный класс '{sub.class_id}'")
    for id, species in items["species"].items():
        for trait in species.traits:
            if not has("feature", trait):
                bad("species", id, "traits", f"неизвестное умение '{trait}'")
    for kind in items:
        for id, obj in items[kind].items():
            for effect in getattr(obj, "effects", []):
                if effect.condition is not None and not has("condition", effect.condition):
                    bad(
                        kind, id, "effects.condition", f"неизвестное состояние '{effect.condition}'"
                    )
                if effect.class_id is not None and not has("class", effect.class_id):
                    bad(kind, id, "effects.class_id", f"неизвестный класс '{effect.class_id}'")
                if effect.spell is not None and not has("spell", effect.spell):
                    bad(kind, id, "effects.spell", f"неизвестное заклинание '{effect.spell}'")
    for id, background in items["background"].items():
        if not has("feat", background.feat):
            bad("background", id, "feat", f"неизвестная черта '{background.feat}'")
        elif items["feat"][background.feat].category != "origin":
            bad("background", id, "feat", f"черта '{background.feat}' не категории origin")
        if background.tool is not None and not (
            has("item", background.tool) and items["item"][background.tool].tool
        ):
            bad("background", id, "tool", f"'{background.tool}' не инструмент")
        for item_id in background.equipment:
            if not any(has(k, item_id) for k in ("weapon", "armor", "item")):
                bad("background", id, "equipment", f"неизвестный предмет '{item_id}'")
    for id, spell in items["spell"].items():
        for class_id in spell.classes:
            if not has("class", class_id):
                bad("spell", id, "classes", f"неизвестный класс '{class_id}'")
    for id, monster in items["monster"].items():
        for trait in monster.traits:
            if not has("feature", trait):
                bad("monster", id, "traits", f"неизвестное умение '{trait}'")
        check_monster_gear(monster, id, has, bad, items)
        check_monster_actions(monster, id, has, bad)
    return errors


def load_registry(content_dirs: Sequence[Path] = (), *, include_srd: bool = True):
    layers = []
    if include_srd:
        layers.append(SRD_DIR)
    layers.extend(Path(d) for d in content_dirs)

    items = {kind: {} for kind in KINDS}
    paths = {}
    conflicts = []
    conflict_lines = []
    read_errors = []
    for layer in layers:
        for kind, (folder, model) in KINDS.items():
            for path in layer_files(layer, kind, folder):
                try:
                    obj = read_file(path, model)
                except ContentError as err:
                    read_errors.append(str(err))
                    continue
                key = (kind, obj.id)
                if key in paths:
                    conflicts.append(key)
                    conflict_lines.append(
                        f"{kind} '{obj.id}': {paths[key]} и {path}"
                    )
                    continue
                items[kind][obj.id] = obj
                paths[key] = path
    if conflicts and not read_errors:
        text = "Конфликт id контента:\n" + "\n".join(conflict_lines)
        raise ContentConflictError(text, conflicts)

    errors = read_errors + check_refs(items, paths)
    if errors:
        raise ContentError("\n".join(errors + conflict_lines))
    return ContentRegistry(items)
