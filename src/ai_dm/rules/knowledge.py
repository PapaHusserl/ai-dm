import re

from ai_dm.state.knowledge import KNOWLEDGE_KINDS, KNOWLEDGE_TEXT_MAX, KnowledgeEntry

# тексты записей движка: по префиксу их узнают и промпт (не показывает), и тесты
MET = "Знакомство: "
VISITED = "Место: "
FOUGHT = "Бой: "
ENGINE_PREFIXES = (MET, VISITED)
FIGHT_WORDS = {"victory": "победа", "fled": "бегство", "ended_by_master": "прерван"}
FIGHT_LOST = "поражение"
# имя не длиннее этого ищется в тексте только целым словом
SHORT_NAME = 3
# значимые слова секрета и доля их попадания в текст заметки, с которой это пересказ секрета
SECRET_WORD_MIN = 4
SPOIL_SHARE = 0.6


def normalize(text) -> str:
    return " ".join(text.lower().split())


def fact(kind, ref, text, source, at_s) -> KnowledgeEntry:
    return KnowledgeEntry(kind=kind, ref=ref, text=text, source=source, at_s=at_s)


def current_hero(bundle):
    return next(h for h in bundle.heroes if h.id == bundle.manifest.current_hero_id)


def is_engine(entry) -> bool:
    # запись движка о знакомстве или месте (seen с префиксом текста)
    return entry.source == "seen" and entry.text.startswith(ENGINE_PREFIXES)


def has_entry(hero, kind, ref, prefix="") -> bool:
    # есть ли запись сущности с текстом на prefix (движка: MET или VISITED)
    return any(
        e.kind == kind and e.ref == ref and e.text.startswith(prefix) for e in hero.knowledge
    )


def entries_for(hero, kind, ref) -> list[KnowledgeEntry]:
    return [e for e in hero.knowledge if e.kind == kind and e.ref == ref]


def evict_oldest(hero, kind, ref) -> None:
    # старейшая по at_s запись сущности; при равенстве -- ранняя в журнале; запись движка о
    # знакомстве или месте уходит, только если других записей нет (иначе её пишут заново по кругу)
    entries = entries_for(hero, kind, ref)
    victims = [e for e in entries if not is_engine(e)] or entries
    hero.knowledge.remove(min(victims, key=lambda e: e.at_s))


def mentions(name, text) -> bool:
    # имя с начала слова (русские окончания допустимы: «Олдрику»); короткое имя -- только целым
    # словом, иначе «Ян» найдётся в «Яндексе» (оба в нижнем регистре)
    tail = r"(?!\w)" if len(name) <= SHORT_NAME else ""
    return re.search(rf"(?<!\w){re.escape(name)}{tail}", text) is not None


def remember_fact(hero, entry, cfg) -> bool:
    # False -- дубль (та же сущность и тот же текст); при полном лимите уходит старейшая запись
    same = entries_for(hero, entry.kind, entry.ref)
    if any(normalize(e.text) == normalize(entry.text) for e in same):
        return False
    if len(same) >= cfg.max_per_ref:
        evict_oldest(hero, entry.kind, entry.ref)
    hero.knowledge.append(entry)
    return True


def shorten_text(text, limit) -> str:
    # по последнему пробелу до предела с «…» (итог <= предела); без пробела -- жёсткий срез
    if len(text) <= limit:
        return text
    head = text[: limit - 1]
    cut = head.rfind(" ")
    return (head[:cut] if cut > 0 else head).rstrip() + "…"


def note_presence(hero, world, text, cfg) -> list[str]:
    # первое посещение локации героя и первая встреча NPC (живой, в локации героя или идущий с ним,
    # имя в тексте хода); возвращает строки лога
    now_s = world.clock.now_s
    low = text.lower()
    log = []
    place = world.locations.get(hero.location_id)
    if place is not None and not has_entry(hero, "location", place.id, VISITED):
        remember_fact(hero, fact("location", place.id, VISITED + place.name, "seen", now_s), cfg)
        log.append(f"Журнал: место {place.name}")
    for npc in sorted(world.npcs.values(), key=lambda n: n.id):
        near = npc.location_id == hero.location_id or npc.follows == hero.id
        if npc.status != "alive" or not near or not mentions(npc.name.lower(), low):
            continue
        if not has_entry(hero, "npc", npc.id, MET):
            remember_fact(hero, fact("npc", npc.id, MET + npc.name, "seen", now_s), cfg)
            log.append(f"Журнал: знакомство {npc.name}")
    return log


def note_combat(hero, world, state, registry, cfg) -> None:
    # бестиарий: безымянные враги боя (не NPC мира); state -- завершённый бой
    word = FIGHT_WORDS.get(state.outcome, FIGHT_LOST)
    for p in state.participants:
        if p.side != "enemies" or p.monster_id is None or p.ref in world.npcs:
            continue
        text = f"{FOUGHT}{registry.get('monster', p.monster_id).name} — {word}"
        remember_fact(hero, fact("creature", p.monster_id, text, "seen", world.clock.now_s), cfg)


def note_favor(hero, god, detail, now_s, cfg) -> None:
    text = shorten_text(f"{god.name}: {detail}", KNOWLEDGE_TEXT_MAX)
    remember_fact(hero, fact("god", god.id, text, "deduced", now_s), cfg)


def note_secret(hero, npc, secret, now_s, cfg) -> None:
    text = shorten_text(secret.text, KNOWLEDGE_TEXT_MAX)
    remember_fact(hero, fact("npc", npc.id, text, "deduced", now_s), cfg)


def mentioned_text(bundle) -> str:
    # ввод и рассказ последних ходов, выжимки сцен и глав и сводка игры одним текстом, без регистра
    memory = bundle.memory
    parts = [memory.game_summary]
    for turn in memory.recent_turns:
        parts += [turn.player_input, turn.narration]
    parts += [s.summary for s in memory.scenes] + [c.summary for c in memory.chapters]
    return "\n".join(parts).lower()


def is_met(npc, hero_id, text) -> bool:
    signs = (
        npc.known_to_player, npc.memory, npc.follows == hero_id, npc.attitude != 0,
        npc.named and mentions(npc.name.lower(), text),
    )
    return any(signs)


def met_npc_ids(bundle) -> list[str]:
    # живые и мёртвые NPC, с которыми герой встречался (по данным сейва), по id
    hero_id = bundle.manifest.current_hero_id
    text = mentioned_text(bundle)
    return [i for i, npc in sorted(bundle.world.npcs.items()) if is_met(npc, hero_id, text)]


def backfill(bundle, cfg) -> int:
    # достройка журнала старого мира; идемпотентна; время записей -- начало текущей сцены
    hero = current_hero(bundle)
    world = bundle.world
    scene = bundle.session.current_scene
    at_s = world.clock.now_s if scene is None else scene.started_at_s
    added = 0
    for npc_id in met_npc_ids(bundle):
        npc = world.npcs[npc_id]
        added += remember_fact(hero, fact("npc", npc.id, MET + npc.name, "seen", at_s), cfg)
        for secret in npc.secrets:
            if secret.id in npc.known_to_player:
                added += remember_fact(
                    hero, fact("npc", npc.id, secret.text, "deduced", at_s), cfg
                )
    for place in sorted(world.locations.values(), key=lambda p: p.id):
        if place.visited:
            added += remember_fact(
                hero, fact("location", place.id, VISITED + place.name, "seen", at_s), cfg
            )
    return added


def ensure_journal(bundle, cfg) -> int:
    # достройка только у пустого журнала (старый мир): дальше журнал ведёт сама игра, а повторная
    # достройка на загрузке, в т.ч. при replay отчёта, меняла бы состояние до хода
    if current_hero(bundle).knowledge:
        return 0
    return backfill(bundle, cfg)


def significant(text) -> set[str]:
    return {w for w in re.findall(r"\w+", text.lower()) if len(w) >= SECRET_WORD_MIN}


def spoils(text, secrets) -> bool:
    # заметка пересказывает один из нераскрытых секретов (secrets -- их тексты)
    words = significant(text)
    for secret in secrets:
        key = significant(secret)
        if key and len(key & words) / len(key) >= SPOIL_SHARE:
            return True
    return False


def wanted(entry, refs_by_kind) -> bool:
    # запись для промпта: вид выбран, ref в отборе (None -- все), запись о знакомстве и месте -- нет
    if entry.kind not in refs_by_kind:
        return False
    if is_engine(entry):
        return False
    refs = refs_by_kind[entry.kind]
    return refs is None or entry.ref in refs


def entry_line(entry) -> str:
    who = entry.source if entry.from_ref is None else f"{entry.source}: {entry.from_ref}"
    return f"{entry.text} ({who})"


def prompt_entries(hero, refs_by_kind, limit) -> dict:
    # журнал для рассказчика: вид -> ref -> строки; новейшие limit записей по (at_s, порядок
    # журнала), в итоге -- в порядке журнала, виды по KNOWLEDGE_KINDS, ref по алфавиту
    chosen = [(i, e) for i, e in enumerate(hero.knowledge) if wanted(e, refs_by_kind)]
    newest = sorted(chosen, key=lambda pair: (pair[1].at_s, pair[0]))[max(0, len(chosen) - limit):]
    grouped = {}
    for _, entry in sorted(newest, key=lambda pair: pair[0]):
        grouped.setdefault(entry.kind, {}).setdefault(entry.ref, []).append(entry_line(entry))
    return {
        kind: {ref: grouped[kind][ref] for ref in sorted(grouped[kind])}
        for kind in KNOWLEDGE_KINDS if kind in grouped
    }
