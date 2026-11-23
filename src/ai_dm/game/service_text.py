from ai_dm.rules.money import format_cp
from ai_dm.rules.services import is_free, quote, service_entries

UNIT_WORDS = {"night": "ночь", "meal": "порция", "hour": "час", "once": "раз"}
FREE_WORD = "даром"


def service_price_text(kind, kind_id, npc, world, cfg):
    # цена услуги в строке /shop и окна TUI: «даром» у друга, иначе «<цена> / <единица>»
    if is_free(kind_id, kind, npc, world, cfg):
        return FREE_WORD
    return f"{format_cp(quote(kind, npc, world, cfg, kind_id))} / {UNIT_WORDS[kind.unit]}"


def service_lines(npc, world, cfg):
    # блок «Услуги:» NPC; пусто, если услуг нет
    entries = service_entries(npc, world, cfg)
    if not entries:
        return []
    lines = ["  Услуги:"]
    for name, kind_id, kind in entries:
        lines.append(f"    {name} — {service_price_text(kind, kind_id, npc, world, cfg)}")
    return lines
