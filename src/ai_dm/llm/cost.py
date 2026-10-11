import json
from dataclasses import dataclass, field


def cost_nano(usage, price):
    # цены в микро-долларах за 1М токенов -> нано-доллары
    total = (
        usage.input * price.input
        + usage.output * price.output
        + usage.cache_write * price.cache_write
        + usage.cache_write_1h * price.cache_write_1h
        + usage.cache_read * price.cache_read
        + usage.cache_storage_min * price.cache_storage_hour // 60
    )
    return total // 1000


def pick_price(prices, requested_model, actual_model):
    # цена по фактической модели; нет цены -- по запрошенной и метка
    if actual_model in prices:
        return actual_model, prices[actual_model], None
    note = f"нет цены модели {actual_model}, взята цена запрошенной {requested_model}"
    return requested_model, prices[requested_model], note


@dataclass
class Totals:
    total_nano: int = 0
    by_role: dict = field(default_factory=dict)
    by_model: dict = field(default_factory=dict)
    by_role_model: dict = field(default_factory=dict)

    def add(self, role, model, cost):
        self.total_nano += cost
        self.by_role[role] = self.by_role.get(role, 0) + cost
        self.by_model[model] = self.by_model.get(model, 0) + cost
        self.by_role_model[(role, model)] = self.by_role_model.get((role, model), 0) + cost


@dataclass
class CostReport:
    session: Totals
    day: Totals
    world: Totals


class CostLedger:
    def __init__(self, saves_root, world_id):
        self.saves_root = saves_root
        self.path = saves_root / world_id / "meta" / "costs.jsonl"
        self.session_lines = []

    def add(self, *, call_id, role, model, usage, cost_nano, day, aborted=False, note=None):
        line = {
            "call_id": call_id, "role": role, "model": model, "usage": usage.model_dump(),
            "cost_nano": cost_nano, "day": day.isoformat(), "aborted": aborted, "note": note,
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(line, ensure_ascii=False) + "\n")
        self.session_lines.append(line)

    def report(self, today):
        report = CostReport(session=Totals(), day=Totals(), world=Totals())
        for line in self.session_lines:
            report.session.add(line["role"], line["model"], line["cost_nano"])
        # день -- по всем мирам; мир -- только этот
        for path in sorted(self.saves_root.glob("*/meta/costs.jsonl")):
            for text in path.read_text(encoding="utf-8").splitlines():
                line = json.loads(text)
                if path == self.path:
                    report.world.add(line["role"], line["model"], line["cost_nano"])
                if line["day"] == today.isoformat():
                    report.day.add(line["role"], line["model"], line["cost_nano"])
        return report


def check_limit(cfg, spent_nano, limit_micro):
    # лимит в конфиге -- микро-доллары (как цены), траты -- нано-доллары
    limit_nano = limit_micro * 1000
    if not cfg.enabled or not limit_nano:
        return "ok"
    if spent_nano >= limit_nano:
        return "pause"
    if spent_nano * 100 >= limit_nano * cfg.warn_percent:
        return "warn"
    return "ok"
