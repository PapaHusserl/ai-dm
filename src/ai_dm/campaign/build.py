from ai_dm.campaign.models import HeroPreset
from ai_dm.campaign.presets import PACK_TONE, apply_preset, load_presets
from ai_dm.campaign.uniqueness import collect_conflicts
from ai_dm.core.clock import DAY, GameClock
from ai_dm.core.rng import Rng
from ai_dm.persistence.migrations import CURRENT_SCHEMA_VERSION
from ai_dm.rules.builder import HeroSheet, ValidationErrors, build_character
from ai_dm.rules.inventory import add_catalog_item
from ai_dm.rules.progression import apply_level_choices, level_up, missing_choices
from ai_dm.rules.triggers_eval import KnownIds
from ai_dm.rules.uniqueness import check_hero, name_taken
from ai_dm.state.hero import LevelChoices
from ai_dm.state.memory import Chronicle, ChronicleEntry, Memory
from ai_dm.state.save import Manifest, SaveBundle
from ai_dm.state.session import ChapterState, SessionState
from ai_dm.state.world import Lore, WorldState

# id пресета героя, собранного на лету (в текстах StartRefused)
ON_THE_FLY_ID = "custom"


class StartRefused(Exception):
    def __init__(self, lines):
        super().__init__("\n".join(lines))
        self.lines = list(lines)


def make_clock(pack) -> GameClock:
    start = pack.manifest.start
    clock = GameClock.from_date(start.date, pack.manifest.calendar)
    hours, minutes = start.time.split(":")
    clock.advance(int(hours) * 3600 + int(minutes) * 60)
    return clock


def resolve_hero_preset(pack, hero) -> HeroPreset:
    # hero -- id пресета пака или лист героя на лету (старт в локации манифеста, деньги от набора)
    if isinstance(hero, HeroSheet):
        return HeroPreset(id=ON_THE_FLY_ID, choices=hero.choices, motive=hero.motive)
    preset = next((p for p in pack.heroes if p.id == hero), None)
    if preset is None:
        raise ValueError(f"неизвестный герой пака: {hero!r}")
    return preset


def apply_hooks(hero, sheet) -> None:
    # мотив, средства и возможности листа -- копиями; лист главнее пресета, пустое поле не затирает
    if sheet.motive:
        hero.motive = sheet.motive
    if sheet.means:
        hero.means = list(sheet.means)
    if sheet.opportunity:
        hero.opportunity = [t.model_copy(deep=True) for t in sheet.opportunity]


def known_ids(pack) -> KnownIds:
    # id пака, на которые можно ссылаться из возможностей героя
    return KnownIds(
        npcs={n.id for n in pack.npcs}, locations={x.id for x in pack.locations},
        pantheon={g.id for g in pack.pantheon},
    )


def taken_names(pack) -> list[str]:
    # имена, которые герою брать нельзя: именованные NPC, боги, фракции пака
    names = [n.name for n in pack.npcs if n.named]
    return names + [g.name for g in pack.pantheon] + [f.name for f in pack.factions]


def build_hero(pack, preset, registry):
    # штатная сборка героя, потом состояние пресета
    choices = preset.choices.model_copy(update={"hero_id": "hero"})
    hero = build_character(choices, registry)
    if isinstance(hero, ValidationErrors):
        raise StartRefused([f"героя {preset.id!r} не собрать: {m}" for m in hero.messages])
    for entry in preset.inventory_extra:
        add_catalog_item(hero, registry, entry.item_id, entry.qty)
    if preset.equipped is not None:
        hero.equipped = preset.equipped.model_copy()
    if preset.money_cp is not None:
        hero.money_cp = preset.money_cp
    hero.location_id = preset.location_id or pack.manifest.start.hero_location
    while hero.sheet.level < preset.level:
        level_up(hero, registry, hp_method="average")
        level = hero.sheet.level
        given = [c for c in preset.level_choices if c.level == level]
        chosen = given[0] if given else LevelChoices(level=level)
        problems = missing_choices(hero, registry, chosen)
        refused = apply_level_choices(hero, registry, chosen)
        if refused is not None:
            problems += refused.messages
        if problems:
            raise StartRefused([f"героя {preset.id!r}, уровень {level}: {m}" for m in problems])
    reached = range(2, preset.level + 1)
    lines = [
        f"героя {preset.id!r}: выборы уровня {c.level} вне 2..{preset.level}"
        for c in preset.level_choices if c.level not in reached
    ]
    if lines:
        raise StartRefused(lines)
    if preset.companion is not None:
        hero.companions = [preset.companion.model_copy()]
    hero.sheet.xp = preset.xp
    hero.motive = preset.motive
    hero.means = list(preset.means)
    hero.opportunity = [t.model_copy(deep=True) for t in preset.opportunity]
    hero.favor = dict(preset.favor)
    hero.deity_id = preset.deity_id
    if preset.birth_date is not None:
        hero.birth_s = GameClock.from_date(preset.birth_date, pack.manifest.calendar).now_s
    return hero


def refusal_lines(pack, preset, hero, world) -> list[str]:
    # старт отказан, если отброшена стартовая локация или нужное герою
    lines = []
    wanted = {pack.manifest.start.hero_location, hero.location_id}
    for location_id in sorted(wanted):
        if location_id not in world.locations:
            lines.append(f"стартовая локация {location_id!r} не загружена (конфликт)")
    gods = set(preset.favor)
    if preset.deity_id is not None:
        gods.add(preset.deity_id)
    for god_id in sorted(gods):
        if god_id not in world.pantheon:
            lines.append(f"бог {god_id!r} героя {preset.id!r} не загружен")
    for line in check_hero(world, hero, []):
        lines.append(f"герой {preset.id!r}: {line}")
    return lines


def pick_tone(manifest, preset_id):
    # возвращает (тон мира, запись хроники или None); пусто -- тон пака без наложения
    preset_id = preset_id or manifest.preset
    if not preset_id or preset_id == PACK_TONE:
        return manifest.tone.model_copy(deep=True), None
    preset = load_presets()[preset_id]
    return apply_preset(manifest.tone, preset), f"Пресет мира: {preset.name}"


def build_world(pack, cfg, registry, *, hero_id, seed, world_id, saved_at, preset_id=None):
    # возвращает (бандл без сцены, список конфликтов); отказ старта -- StartRefused
    preset = resolve_hero_preset(pack, hero_id)
    manifest = pack.manifest
    clock = make_clock(pack)
    hero = build_hero(pack, preset, registry)
    if isinstance(hero_id, HeroSheet):
        apply_hooks(hero, hero_id)
        if name_taken(hero.name, taken_names(pack)):
            line = f"имя {hero.name!r} уже занято (NPC, бог, фракция или герой)"
            raise StartRefused([f"герой {ON_THE_FLY_ID!r}: {line}"])
    tone, tone_note = pick_tone(manifest, preset_id)
    mortality = manifest.mortality
    per_day = mortality.per_day
    if per_day is None:
        per_day = cfg.world.mortality_presets[mortality.preset]
    world = WorldState(
        world_id=world_id,
        rng=Rng(seed).state,
        campaign_id=manifest.id,
        campaign_version=manifest.version,
        clock=clock,
        flags=dict(manifest.flags),
        tone=tone,
        lore=Lore(world_text=pack.world_text, truths=pack.truths),
        mortality_per_day=per_day,
        natural=manifest.natural_events.model_copy(deep=True),
        nudge_scenes=manifest.nudge.scenes,
    )
    accepted, conflicts = collect_conflicts(world, [hero], pack)
    for location in accepted.locations:
        world.locations[location.id] = location.model_copy(deep=True)
    for god in accepted.pantheon:
        world.pantheon[god.id] = god.model_copy(deep=True)
    for faction in accepted.factions:
        world.factions[faction.id] = faction.model_copy(deep=True)
    for npc in accepted.npcs:
        world.npcs[npc.id] = npc.model_copy(deep=True)
    world.events = [event.model_copy(deep=True) for event in accepted.events]
    world.sim.last_day = clock.now_s // DAY
    world.sim.last_season = clock.season()
    world.sim.last_year = clock.now_s // clock.calendar.seconds_in_year
    lines = refusal_lines(pack, preset, hero, world)
    if lines:
        raise StartRefused(lines)
    chapter = manifest.start.chapter
    session = SessionState(
        current_chapter=ChapterState(
            id=f"ch_{chapter.number}", number=chapter.number, title=chapter.title,
            started_at_s=clock.now_s, scene_count=1,
        )
    )
    memory = Memory(
        game_summary=pack.start_memory.game_summary,
        chapters=[c.model_copy(deep=True) for c in pack.start_memory.chapters],
        scenes=[s.model_copy(deep=True) for s in pack.start_memory.scenes],
    )
    chronicle = Chronicle(
        entries=[e.model_copy(deep=True) for e in pack.start_chronicle.entries]
    )
    if tone_note is not None:
        chronicle.entries.append(ChronicleEntry(at_s=clock.now_s, kind="tone", text=tone_note))
    save_manifest = Manifest(
        schema_version=CURRENT_SCHEMA_VERSION, engine_version="0.1.0", world_id=world_id,
        campaign_id=manifest.id, slot="auto", saved_at=saved_at, current_hero_id="hero",
        heroes=["hero"],
    )
    bundle = SaveBundle(
        manifest=save_manifest, world=world, chronicle=chronicle, memory=memory,
        heroes=[hero], session=session,
    )
    return bundle, conflicts
