from typing import Protocol

from ai_dm.combat.zones import distance, drop_steps
from ai_dm.state.combat import DecisionPoint


class Controller(Protocol):
    def choose(self, options, ctx: DecisionPoint) -> str: ...


class ScriptedController:
    def __init__(self, script):
        self.script = list(script)
        # все полученные DecisionPoint
        self.seen = []

    def choose(self, options, ctx: DecisionPoint) -> str:
        self.seen.append(ctx)
        if not self.script:
            if ctx.kind == "turn_action":
                return "end_turn"
            return "keep"
        choice = self.script.pop(0)
        if choice not in ctx.options:
            raise ValueError(f"нет такого варианта: {choice!r}")
        return choice


class EngineTactics:
    # детерминированная тактика рядовых участников, броски не использует
    def __init__(self, engine):
        self.engine = engine

    def choose(self, options, ctx: DecisionPoint) -> str:
        if ctx.kind == "intent_reconsider":
            return "keep"
        return self.choose_turn(options, ctx.actor)

    def choose_turn(self, options, ref) -> str:
        ids = [o.id for o in options]
        chosen = self.pick_early(options, ref)
        if chosen is not None:
            return chosen
        if "multiattack" in ids:
            return "multiattack"
        attack = self.pick_attack(options, ref)
        if attack is not None:
            return attack
        return self.approach(options, ref)

    def approach(self, options, ref) -> str:
        ids = [o.id for o in options]
        target = self.nearest_enemy(ref)
        if target is None:
            return "end_turn"
        steps = distance(self.engine.state.zones, self.zone(ref), self.zone(target))
        if steps >= 2 and "dash" in ids:
            return "dash"
        if steps >= 1:
            step = self.step_towards(options, target)
            if step is not None:
                return step
        return "end_turn"

    def pick_early(self, options, ref):
        # что делается раньше атаки: особое, толчок вниз, шаг к своему оружию
        for pick in (self.pick_special, self.pick_shove, self.step_to_weapon):
            chosen = pick(options, ref)
            if chosen is not None:
                return chosen
        return None

    def pick_special(self, options, ref):
        # опутанный первым делом вырывается: атаковать с помехой и стоять на месте хуже;
        # обезоруженный монстр подбирает своё оружие, монстр с тегом disarmer обезоруживает
        kinds = ["escape"]
        if not self.engine.is_hero(ref):
            kinds += ["pickup", "disarm"]
        for kind in kinds:
            for option in options:
                if option.kind == kind:
                    return option.id
        return None

    def pick_shove(self, options, ref):
        # монстр сталкивает цель в зону ниже (большая разница высот лучше), раз за бой,
        # если группа убивает или гонит прочь; вровень и вверх не толкает
        group = self.engine.state.groups[self.engine.part(ref).group_id]
        flags = self.engine.creature(ref).active_effects
        if group.intent not in ("kill", "drive_off") or any(e.id == "shove_used" for e in flags):
            return None
        zones = self.engine.state.zones
        best, best_drop = None, 0
        for option in options:
            if option.kind != "shove":
                continue
            target_zone = self.zone(option.params["target"])
            drop = drop_steps(zones, target_zone, option.params["zone"])
            if drop > best_drop:
                best, best_drop = option.id, drop
        return best

    def step_to_weapon(self, options, ref):
        # своё выбитое оружие лежит в соседней зоне, а бить в своей некого: идём к нему
        # локальные импорты: цикл импортов
        from ai_dm.combat import disarm
        from ai_dm.combat.actions.attack import lost_weapons

        engine = self.engine
        if engine.is_hero(ref) or not lost_weapons(engine, ref)[1]:
            return None
        if [t for t in self.enemies(ref, "active") if self.zone(t) == self.zone(ref)]:
            return None
        moves = {o.params["zone"]: o.id for o in options if o.kind == "move"}
        for item in engine.state.ground_items:
            if item.owner_ref != ref or item.zone_id not in moves:
                continue
            if disarm.can_pick(engine, ref, item):
                return moves[item.zone_id]
        return None

    def zone(self, ref):
        return self.engine.part(ref).zone_id

    def uses_kill(self, ref) -> bool:
        group = self.engine.state.groups[self.engine.part(ref).group_id]
        return group.intent == "kill"

    def enemies(self, ref, status) -> list:
        # враги стороны: боеспособные ("active") или лежащие ("down")
        engine = self.engine
        side = engine.part(ref).side
        result = []
        for p in engine.state.participants:
            if p.side == side:
                continue
            if status == "active" and engine.is_capable(p.ref):
                result.append(p.ref)
            if status == "down" and p.status == "down":
                result.append(p.ref)
        return result

    def weakest(self, refs) -> str:
        # наименьшее hp, ничья -- меньший id
        engine = self.engine
        return sorted(refs, key=lambda r: (engine.creature(r).hp_current, r))[0]

    def pick_attack(self, options, ref):
        # импровизированное оружие рядовые участники не берут: подручное вместо шага не бросают
        attacks = [
            o for o in options if o.kind == "attack" and not o.params["nonlethal"]
            and not o.params["weapon"].startswith("improvised")
        ]
        own_zone = [t for t in self.enemies(ref, "active") if self.zone(t) == self.zone(ref)]
        if not own_zone and self.uses_kill(ref):
            own_zone = [t for t in self.enemies(ref, "down") if self.zone(t) == self.zone(ref)]
        # враг рядом: ближняя атака, а если её нет -- дальняя
        for mode in ("melee", "ranged"):
            near = [t for t in own_zone if self.has_attack(attacks, t, mode)]
            if near:
                return self.first_attack(attacks, self.weakest(near), mode)
        # врага рядом нет: стреляем по самому слабому боеспособному, при kill -- и по лежащему
        far = [t for t in self.enemies(ref, "active") if self.has_attack(attacks, t, "ranged")]
        if not far and self.uses_kill(ref):
            far = [t for t in self.enemies(ref, "down") if self.has_attack(attacks, t, "ranged")]
        if far:
            return self.first_attack(attacks, self.weakest(far), "ranged")
        return None

    def has_attack(self, attacks, target, mode) -> bool:
        return self.first_attack(attacks, target, mode) is not None

    def first_attack(self, attacks, target, mode):
        for option in attacks:
            if option.params["target"] == target and option.params["mode"] == mode:
                return option.id
        return None

    def nearest_enemy(self, ref):
        targets = self.enemies(ref, "active")
        if not targets and self.uses_kill(ref):
            targets = self.enemies(ref, "down")
        if not targets:
            return None
        zones = self.engine.state.zones
        return sorted(targets, key=lambda t: (distance(zones, self.zone(ref), self.zone(t)), t))[0]

    def step_towards(self, options, target):
        # соседняя зона с наименьшим расстоянием до цели (при равенстве -- первая в списке)
        zones = self.engine.state.zones
        moves = [o for o in options if o.kind == "move"]
        if not moves:
            return None
        best = sorted(moves, key=lambda o: distance(zones, o.params["zone"], self.zone(target)))[0]
        return best.id


class AutoHeroController(EngineTactics):
    # тактика + то, что делает сам герой без игрока
    def choose_turn(self, options, ref) -> str:
        ids = [o.id for o in options]
        creature = self.engine.creature(ref)
        if creature.hp_current <= creature.hp_max // 2 and "second_wind" in ids:
            return "second_wind"
        for option in options:
            if option.kind in ("stabilize", "horde_breaker"):
                return option.id
        if self.engine.heroes[ref].equipped.main_hand is None:
            for option in options:
                if option.kind == "pickup":
                    return option.id
        spell = self.pick_spell(options)
        if spell is not None:
            return spell
        return super().choose_turn(options, ref)

    def pick_spell(self, options):
        for spell_id in ("magic_missile", "fire_bolt"):
            casts = [o for o in options if o.kind == "cast" and o.params["spell"] == spell_id]
            if casts:
                target = self.weakest([o.params["target"] for o in casts])
                return [o.id for o in casts if o.params["target"] == target][0]
        return None
