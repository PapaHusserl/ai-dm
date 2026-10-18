from ai_dm.protocol.handlers.knowledge import WORLD_REFS
from ai_dm.rules.npc_names import shown_name
from ai_dm.state.knowledge import KNOWLEDGE_KINDS

LORE_EMPTY = "Журнал пуст: герой ещё ничего не узнал."
LORE_HINT = "Подробнее: /lore <имя>"
KIND_TITLES = {
    "npc": "Люди", "location": "Места", "faction": "Фракции", "god": "Боги",
    "creature": "Бестиарий", "situation": "Ситуации",
}
SOURCE_WORDS = {
    "seen": "видел сам", "told": "рассказали", "rumor": "слух", "read": "прочитал",
    "deduced": "понял сам",
}


def entity_name(kind, ref, world, registry) -> str:
    # имя сущности журнала; ситуация и неизвестный id -- сам ref
    if kind in WORLD_REFS:
        obj = getattr(world, WORLD_REFS[kind]).get(ref)
        if obj is None:
            return ref
        return shown_name(obj) if kind == "npc" else obj.name
    if kind == "creature" and registry.has("monster", ref):
        return registry.get("monster", ref).name
    return ref


def lore_groups(hero, world, registry) -> list:
    # [(вид, [(ref, имя, записи)])]: виды по KNOWLEDGE_KINDS, сущности по имени, пустые виды опущены
    groups = []
    for kind in KNOWLEDGE_KINDS:
        by_ref = {}
        for entry in hero.knowledge:
            if entry.kind == kind:
                by_ref.setdefault(entry.ref, []).append(entry)
        items = [
            (ref, entity_name(kind, ref, world, registry), entries)
            for ref, entries in by_ref.items()
        ]
        if items:
            groups.append((kind, sorted(items, key=lambda item: item[1].lower())))
    return groups


def find_entity(groups, query):
    # (вид, ref, имя, записи) по подстроке имени или ref без регистра; точное совпадение первым
    low = query.strip().lower()
    found = [
        (kind, *item) for kind, items in groups for item in items
        if low in item[1].lower() or low in item[0].lower()
    ]
    exact = [f for f in found if low in (f[1].lower(), f[2].lower())]
    return next(iter(exact or found), None)


def date_of(clock, at_s) -> str:
    return clock.model_copy(update={"now_s": at_s}).to_date()


def entry_line(entry, world) -> str:
    who = SOURCE_WORDS.get(entry.source, entry.source)
    if entry.from_ref is not None:
        teller = world.npcs.get(entry.from_ref)
        who += f": {entry.from_ref if teller is None else shown_name(teller)}"
    return f"— {entry.text} ({who}, {date_of(world.clock, entry.at_s)})"


def entry_lines(entries, world) -> list[str]:
    return [entry_line(entry, world) for entry in entries]


def lore_lines(hero, world, registry, arg) -> list[str]:
    groups = lore_groups(hero, world, registry)
    if not groups:
        return [LORE_EMPTY]
    if arg.strip():
        hit = find_entity(groups, arg)
        if hit is None:
            return [f"Не найдено: {arg.strip()}.", LORE_HINT]
        kind, _, name, entries = hit
        return [f"{name} ({KIND_TITLES[kind]}):"] + [
            f"  {line}" for line in entry_lines(entries, world)
        ]
    lines = []
    for kind, items in groups:
        lines.append(f"{KIND_TITLES[kind]}:")
        lines += [f"  {name} — {len(entries)} зап." for _, name, entries in items]
    return lines + ["", LORE_HINT]
