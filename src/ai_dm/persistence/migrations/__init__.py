import copy
from dataclasses import dataclass, field

from ai_dm.persistence.migrations.m0001_v0_to_v1 import migrate_v0_to_v1
from ai_dm.persistence.migrations.m0002_v1_to_v2 import migrate_v1_to_v2
from ai_dm.persistence.migrations.m0003_v2_to_v3 import migrate_v2_to_v3
from ai_dm.persistence.migrations.m0004_v3_to_v4 import migrate_v3_to_v4
from ai_dm.persistence.migrations.m0005_v4_to_v5 import migrate_v4_to_v5
from ai_dm.persistence.migrations.m0006_v5_to_v6 import migrate_v5_to_v6
from ai_dm.persistence.migrations.m0007_v6_to_v7 import migrate_v6_to_v7
from ai_dm.persistence.migrations.m0008_v7_to_v8 import migrate_v7_to_v8
from ai_dm.persistence.migrations.m0009_v8_to_v9 import migrate_v8_to_v9
from ai_dm.persistence.migrations.m0010_v9_to_v10 import migrate_v9_to_v10
from ai_dm.persistence.migrations.m0011_v10_to_v11 import migrate_v10_to_v11
from ai_dm.persistence.migrations.m0012_v11_to_v12 import migrate_v11_to_v12

CURRENT_SCHEMA_VERSION = 12

# {from_version: fn(bundle_dict, context) -> bundle_dict}
MIGRATIONS = {
    0: migrate_v0_to_v1,
    1: migrate_v1_to_v2,
    2: migrate_v2_to_v3,
    3: migrate_v3_to_v4,
    4: migrate_v4_to_v5,
    5: migrate_v5_to_v6,
    6: migrate_v6_to_v7,
    7: migrate_v7_to_v8,
    8: migrate_v8_to_v9,
    9: migrate_v9_to_v10,
    10: migrate_v10_to_v11,
    11: migrate_v11_to_v12,
}

@dataclass
class MigrationContext:
    # внешние данные для миграций (миграции не импортируют реестр и модели state)
    item_cost: dict[str, int] = field(default_factory=dict)
    # id NPC пака -> пресет торговца (kind) из npcs.yaml пака; None -- пак не загрузился
    npc_trade: dict[str, str] | None = field(default_factory=dict)
    # id класса -> кость хитов; id заклинания -> круг (для миграции v9)
    class_hit_die: dict[str, int] = field(default_factory=dict)
    spell_level: dict[str, int] = field(default_factory=dict)
    # что миграции не смогли сделать точно (неизвестный предмет и т. п.)
    report: list[str] = field(default_factory=list)

    def warning(self):
        return "Предупреждение: миграция сейва — " + "; ".join(self.report)

    @classmethod
    def from_registry(cls, registry, npc_trade=None):
        costs = {}
        for kind in ("weapon", "armor", "item"):
            for model in registry.all(kind):
                costs[model.id] = model.cost_cp
        hit_dice = {model.id: model.hit_die for model in registry.all("class")}
        circles = {model.id: model.level for model in registry.all("spell")}
        return cls(
            item_cost=costs, npc_trade=npc_trade or {}, class_hit_die=hit_dice, spell_level=circles
        )


class SaveTooNew(Exception):
    pass


class MigrationMissing(Exception):
    pass


class MigrationContextRequired(Exception):
    pass


def migrate(data: dict, *, registry=None, current_version=None, context=None) -> dict:
    if registry is None:
        registry = MIGRATIONS
    if current_version is None:
        current_version = CURRENT_SCHEMA_VERSION
    version = data["manifest"].get("schema_version", 0)
    if version > current_version:
        raise SaveTooNew(f"сейв версии {version}, движок знает до {current_version}")
    data = copy.deepcopy(data)
    while version < current_version:
        if version not in registry:
            raise MigrationMissing(f"нет миграции с версии {version}")
        needs_context = (migrate_v5_to_v6, migrate_v6_to_v7, migrate_v8_to_v9)
        if context is None and registry[version] in needs_context:
            raise MigrationContextRequired(f"нужен MigrationContext (версия {version})")
        data = registry[version](data, context)
        version += 1
        data["manifest"]["schema_version"] = version
    return data
