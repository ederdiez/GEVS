"""Agent: the body that executes what the brain proposes.

The agent has needs (hunger, energy) and a position in the grid. Each
frame its brain (sim.brain, the neural network) receives signals about
the agent and the world, and returns intentions (direction, eat, rest).
This module is the *body*: it enforces what is inviolable (no rocks, no
shared cells, eat only on food, no movement while resting) and applies
the need rates. All behavior emerges from the brain's outputs; there
are no programmed behaviors here.
"""

import math

from sim import config as cfg
from sim.genetics import Genome


def _nearest_in_window(world, cx, cy, radius, index, accept=None):
    """Nearest match to (cx, cy) within `radius` (Manhattan), searching only
    the (2r+1)x(2r+1) window around it instead of every entry in `index` —
    turns a per-agent O(entities)/O(food_cells) scan into O(radius^2),
    independent of population or world size.

    `index` is a set of (x, y) positions (e.g. world.food_cells) or a dict
    keyed by (x, y) (e.g. world.occupied); every cell is wrapped through
    world.wrap, so the search respects the toroidal map. `accept(x, y,
    value)` may reject a candidate — value is index[(x, y)] for a dict
    index, else None.

    Ties (equal distance) break by ascending (dy, dx) — a fixed, arbitrary
    but deterministic order, not the same as the entities list order the
    old linear scan used.

    Returns (dx, dy, dist, value) or None.
    """
    r = int(math.ceil(radius))
    is_dict = isinstance(index, dict)
    best = None
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            dist = abs(dx) + abs(dy)
            if dist > radius or (best is not None and dist >= best[2]):
                continue
            x, y = world.wrap(cx + dx, cy + dy)
            if is_dict:
                value = index.get((x, y))
                if value is None:
                    continue
            else:
                if (x, y) not in index:
                    continue
                value = None
            if accept is not None and not accept(x, y, value):
                continue
            best = (dx, dy, dist, value)
    return best


def _sleep_recovery_rate(t: float) -> float:
    """Energy recovered per second at *t* seconds continuously asleep.

    Skewed-gaussian bump centered on SLEEP_RECOVERY_PEAK_TIME: a steep
    climb (light sleep) into the deep-sleep peak, then a slow ease back
    down to a plateau above the base rate (see config.py). A nap that
    ends before the climb barely recovered anything.
    """
    sigma = (cfg.SLEEP_RECOVERY_SIGMA_RISE if t < cfg.SLEEP_RECOVERY_PEAK_TIME
             else cfg.SLEEP_RECOVERY_SIGMA_FALL)
    bump = math.exp(-0.5 * ((t - cfg.SLEEP_RECOVERY_PEAK_TIME) / sigma) ** 2)
    return cfg.SLEEP_RECOVERY_BASE_RATE + \
        (cfg.SLEEP_RECOVERY_PEAK_RATE - cfg.SLEEP_RECOVERY_BASE_RATE) * bump


def _interact_resource(agent) -> bool:
    """Eat the carried food: hands off to the same eat_timer state
    machine used for eating straight off the ground (Agent.update), just
    without needing to stand on a food cell."""

    # MAS ADELANTE DEBE SER CAMBIADO PARA INTERACTUAR CON CUALQUIER OBJETO, NO SOLLO COMIDA.
    # ESTA FUCION AHORA SOLO PERMITE COMER.
    #
    # The inventory meal only counts as foresight — and only earns the
    # reward multiplier — if the food was actually carried for a while.
    # grab and interact are evaluated in the same tick, so without the
    # minimum an agent could pick up and eat in one frame and collect the
    # planning bonus without having planned anything (see config.py).
    # Eating it right away is still allowed: that is just eating off the
    # ground by another route, and it earns the plain meal reward.
    agent._meal_from_inventory = agent._carry_time >= cfg.CARRY_MIN_S
    agent.inventory = None
    agent._carry_time = 0.0
    agent.eat_timer = cfg.EAT_DURATION_S
    agent.world.record_meal()
    return True


def _drop_resource(agent) -> bool:
    """Drop the carried food onto the ground, if the cell under the
    agent is empty. True if the item actually left the inventory."""
    if agent._carry_time < cfg.CARRY_MIN_S:
        return False  # can't put down what you just picked up (see config.py)
    if agent.world.cell_type(agent.cx, agent.cy) != cfg.CELL_EMPTY:
        return False
    agent.world.place_cell(agent.cx, agent.cy, cfg.CELL_RESOURCE)
    agent.inventory = None
    agent._carry_time = 0.0
    return True


def _drop_meat(agent) -> bool:
    """Mirrors _drop_resource: drop the carried meat onto an empty cell
    under the agent."""
    if agent._carry_time < cfg.CARRY_MIN_S:
        return False
    if agent.world.cell_type(agent.cx, agent.cy) != cfg.CELL_EMPTY:
        return False
    agent.world.place_cell(agent.cx, agent.cy, cfg.CELL_MEAT)
    agent.inventory = None
    agent._carry_time = 0.0
    return True


def _interact_wood(agent) -> bool:
    """Work the carried wood toward a spear: WOOD_CRAFT_INTERACTIONS valid
    interactions turn it into a spear in place. The wood never actually
    "leaves" the inventory (it just changes type), so this always returns
    False — the interact_fn return value is unused by the dispatcher
    anyway (only drop_fn's is). Progress is lost if the wood ever leaves
    the slot (see the grab path in update())."""
    agent._wood_craft_progress += 1
    if agent._wood_craft_progress >= cfg.WOOD_CRAFT_INTERACTIONS:
        agent.inventory = cfg.CELL_SPEAR
        agent._wood_craft_progress = 0
    return False


def _drop_wood(agent) -> bool:
    """Mirrors _drop_resource: drop the carried wood, whatever its craft
    progress, onto an empty cell under the agent."""
    if agent._carry_time < cfg.CARRY_MIN_S:
        return False
    if agent.world.cell_type(agent.cx, agent.cy) != cfg.CELL_EMPTY:
        return False
    agent.world.place_cell(agent.cx, agent.cy, cfg.CELL_WOOD)
    agent.inventory = None
    agent._carry_time = 0.0
    agent._wood_craft_progress = 0
    return True


def _interact_spear(agent) -> bool:
    """The spear's damage boost is passive (see the attack block in
    update()) — interacting with an equipped spear does nothing."""
    return False


def _drop_spear(agent) -> bool:
    """Mirrors _drop_resource: drop the equipped spear onto an empty cell
    under the agent."""
    if agent._carry_time < cfg.CARRY_MIN_S:
        return False
    if agent.world.cell_type(agent.cx, agent.cy) != cfg.CELL_EMPTY:
        return False
    agent.world.place_cell(agent.cx, agent.cy, cfg.CELL_SPEAR)
    agent.inventory = None
    agent._carry_time = 0.0
    return True


# Inventory item type -> (interact fn, drop fn). Every carryable type
# (cfg.CELL_*) registers both under this same shape — both return True if
# the item left the inventory — so the dispatch in Agent.update() never
# special-cases food: adding a new carryable item only means adding one
# entry here. Wood and a crafted spear are the first real use of that
# extension point. Meat reuses _interact_resource: eating it from the
# inventory is identical to eating carried food, it just came from a
# killed animal instead of the ground.
_INVENTORY_ACTIONS = {
    cfg.CELL_RESOURCE: (_interact_resource, _drop_resource),
    cfg.CELL_WOOD: (_interact_wood, _drop_wood),
    cfg.CELL_SPEAR: (_interact_spear, _drop_spear),
    cfg.CELL_MEAT: (_interact_resource, _drop_meat),
}


class Agent:
    """One individual. Position is in cell units: x, y are floats
    (smooth movement), cx, cy are the integer cell the agent occupies."""

    def __init__(self, world, cx: int, cy: int, genome=None, generation=0,
                 parents=None):
        self.world = world
        self.cx, self.cy = cx, cy
        self.x, self.y = float(cx) + 0.5, float(cy) + 0.5  # start at cell center

        # Genome: brain weight tables + body traits. The initial population
        # is born from the hand-tuned config tables with small noise.
        self.genome = genome if genome is not None else Genome.random_initial(world.rng)
        self.brain = self.genome.build_brain()
        self.generation = generation
        self.parents = parents            # (genome_a, genome_b) or None (initial pop)

        # Body traits: multipliers ~1.0 over the config base rates, resolved
        # to plain attributes here (no dynamic setattr; base values come from
        # config — no magic numbers).
        t = self.genome.traits
        self.speed = cfg.AGENT_SPEED * t["speed"]
        self.food_sense_range = cfg.FOOD_SENSE_RANGE * t["food_sense"]
        self.hunger_rate = cfg.HUNGER_RATE * t["hunger_rate"]
        self.energy_drain_rate = cfg.ENERGY_DRAIN_RATE * t["energy_drain"]
        self.eat_rate = cfg.EAT_RATE * t["eat_rate"]
        self.rest_rate_mult = t["rest_rate"]  # scales the sleep recovery curve, not a flat rate
        self.hp_max = cfg.BASE_AGENT_HP * t["hp"]
        self.hp = self.hp_max
        self.damage = cfg.BASE_AGENT_DAMAGE * t["damage"]
        self.age_s = 0.0
        self.alive = True
        self._mate_cooldown = 0.0
        self._attack_cooldown = 0.0
        self._hp_lost_this_tick = 0.0  # accumulated by take_damage(), consumed by the reward ladder

        # Needs (0-1). Initial values staggered so agents wake at different
        # times of the morning instead of all at once.
        self.hunger = world.rng.random() * 0.4
        self.energy = 0.6 + world.rng.random() * 0.4

        self.eat_timer = 0.0       # > 0 while eating (no movement)
        self.move_x = 0.0          # last brain output, kept for state/tests
        self.move_y = 0.0
        self.eat_out = 0.0
        self.rest_out = 0.0
        self.grab_out = 0.0
        self.interact_out = 0.0
        self.drop_out = 0.0
        self.attack_out = 0.0
        self.target_animal_out = 0.0
        self.target_agent_out = 0.0
        self.state = "active"      # derived: eating / resting / active
        # Carried resource (one slot; None or a cfg.CELL_* int). Filled by
        # the grab output, emptied by interact (use it) or drop (put it
        # down) — see _INVENTORY_ACTIONS.
        self.inventory = None
        self._carry_time = 0.0     # s the current inventory item has been held
        self._wood_craft_progress = 0  # valid interacts toward a spear while carrying wood
        self._meal_from_inventory = False  # did the meal being chewed come from the slot?
        self._last_inputs = None   # this tick's brain inputs, kept for the inspector

        # Per-axis sticky hold: axis -> [sign, timer]. While a cell is
        # blocked by another agent, the position freezes on that axis and
        # the cell is re-probed every BLOCKED_PROBE_S (polite wait: the
        # other agent will move).
        self._holds = {}

        # Detour: rocks never free, so instead of holding, slide along the
        # tangent axis for DETOUR_S to walk around them (see _start_detour).
        # The map itself has no border — edges wrap.
        self._detour_axis = None
        self._detour_sign = 0
        self._detour_timer = 0.0
        self._detour_retreat = False  # True: push back, not slide sideways
        self._detour_last = None      # (axis, sign) of the previous detour
        self._detour_attempts = 0     # consecutive detours on the same (axis, sign)

        # Rest latch: once down, stay down until refilled or starving.
        self._resting = False
        self._sleep_timer = 0.0    # seconds continuously resting; drives the recovery curve

    # -- brain signals --

    def _inputs(self) -> list:
        """The 19 normalized inputs the brain reads (order matches config)."""
        world = self.world
        dx, dy, dist = self._food_dir()
        food_close = 1.0 - min(dist / self.food_sense_range, 1.0) if dist is not None else 0.0
        other, odx, ody, odist = self._other_agent()
        other_close = 1.0 - min(odist / cfg.AGENT_SENSE_RANGE, 1.0) if odist is not None else 0.0
        agent_has_spear = 1.0 if (other is not None and other.inventory == cfg.CELL_SPEAR) else 0.0
        agent_has_food = 1.0 if (
            other is not None and other.inventory in (cfg.CELL_RESOURCE, cfg.CELL_MEAT)
        ) else 0.0
        _animal, adx, ady, adist = self._animal_dir()
        animal_close = 1.0 - min(adist / cfg.ANIMAL_SENSE_RANGE, 1.0) if adist is not None else 0.0
        animal_danger = 1.0 if (_animal is not None and _animal.is_predator) else 0.0
        return [
            self.hunger,
            self.energy,
            1.0 - world.daylight_factor,
            # Direction sensors saturate to [-1, 1] before the (dx+1)/2
            # normalization: a food cell up to FOOD_SENSE_RANGE away makes
            # dx as large as ±8, which would push the input to ±4.5 and
            # amplify any genetic weight noise out of proportion (the
            # night-sleep margin broke under initial noise without this).
            (max(-1.0, min(1.0, dx)) + 1.0) / 2.0 if dx is not None else 0.5,
            (max(-1.0, min(1.0, dy)) + 1.0) / 2.0 if dy is not None else 0.5,
            food_close,
            world.rng.random(),  # noise: wandering without breaking the seed
            (odx + 1.0) / 2.0 if odx is not None else 0.5,
            (ody + 1.0) / 2.0 if ody is not None else 0.5,
            other_close,
            # has_food: 1.0 while the one-slot inventory is full (carrying a
            # resource), 0.0 when empty. Pure state, no new randomness.
            1.0 if self.inventory is not None else 0.0,
            # Absolute world position, normalized to [0,1] by grid size.
            # Not wired to any behavior yet (all-zero weights, config.py).
            self.x / world.cols,
            self.y / world.rows,
            # Direction/closeness to the nearest animal, same shape as the
            # other-agent sensor above. animal_danger is ground truth (the
            # world says whether it's a predator); the weight on all 4 of
            # these columns in move_x/move_y/attack is learned in life, not
            # hand-tuned (LEARNABLE_CELLS, config.py).
            (max(-1.0, min(1.0, adx)) + 1.0) / 2.0 if adx is not None else 0.5,
            (max(-1.0, min(1.0, ady)) + 1.0) / 2.0 if ady is not None else 0.5,
            animal_close,
            animal_danger,
            # Ground truth like animal_danger: whether the nearest other
            # agent is carrying a spear. Reacting to it (avoid, target) is
            # learned in life, not hand-tuned (LEARNABLE_CELLS, config.py).
            agent_has_spear,
            # Ground truth like agent_has_spear: whether the nearest other
            # agent is carrying food (CELL_RESOURCE or CELL_MEAT) in its
            # inventory. Reacting to it is learned in life, not hand-tuned
            # (LEARNABLE_CELLS, config.py).
            agent_has_food,
        ]

    def _food_dir(self):
        """Nearest food cell by Manhattan distance; (dx, dy, dist) or (None, None, None).

        A food cell already claimed by another agent is skipped: when two
        agents race for the same food, whoever reaches the cell first keeps
        it as a target, and the other re-targets the next nearest food
        instead of piling up next to it in a polite hold. The agent's own
        claim is kept, so standing on food still counts as eating it.
        """
        best = _nearest_in_window(
            self.world, self.cx, self.cy, self.food_sense_range,
            self.world.food_cells,
            accept=lambda x, y, _v: self.world.occupied.get((x, y)) in (None, self),
        )
        if best is None:
            return (None, None, None)
        dx, dy, dist, _value = best
        return (dx, dy, dist)

    def _other_agent(self):
        """Nearest other agent by Manhattan; (other, dx, dy, dist) or
        (None, None, None, None).

        Mirrors `_animal_dir`: returns the agent object too (not just the
        delta), since the attack action needs to know who to hit. A pure
        function of positions, no new randomness, so determinism is
        preserved. Only senses within AGENT_SENSE_RANGE — "personal space" —
        so the avoidance signal engages near contact only.
        """
        best = _nearest_in_window(
            self.world, self.cx, self.cy, cfg.AGENT_SENSE_RANGE,
            self.world.occupied,
            accept=lambda x, y, other: other is not self,
        )
        if best is None:
            return (None, None, None, None)
        dx, dy, dist, other = best
        return (other, dx, dy, dist)

    def _animal_dir(self):
        """Nearest animal by Manhattan; (animal, dx, dy, dist) or
        (None, None, None, None).

        Mirrors `_other_agent`, but returns the animal object too (not just
        the delta) — the attack action needs to know who to hit, the same
        reason `_mate_dir` returns the partner. Only senses within
        ANIMAL_SENSE_RANGE.

        # ponytail: linear scan over world.animals, not a window scan like
        # _food_dir/_other_agent/_mate_dir. ANIMAL_SPAWN_COUNT is tiny (a
        # handful), so a window scan (dozens of cell lookups) would cost
        # more than just checking every animal directly. Switch to a window
        # if the animal population ever grows to matter.
        """
        best = None
        for animal in self.world.animals:
            if not animal.alive:
                continue
            dist = abs(animal.cx - self.cx) + abs(animal.cy - self.cy)
            if dist > cfg.ANIMAL_SENSE_RANGE:
                continue
            if best is None or dist < best[3]:
                best = (animal, animal.cx - self.cx, animal.cy - self.cy, dist)
        return best if best is not None else (None, None, None, None)

    def take_damage(self, amount: float) -> None:
        """Called by Animal.update() when a predator lands a hit. Accumulated
        hp loss feeds the reward ladder this same tick (see update())."""
        self.hp = max(0.0, self.hp - amount)
        self._hp_lost_this_tick += amount

    def _mate_eligible(self) -> bool:
        """Eligible to mate: alive, off cooldown, fed and rested enough.

        This drive lives in the body, not the brain: adding mate inputs
        would break the 19->8->10 topology and the hand-tuned weights
        (input 9 stays RESERVED, config.py).
        """
        return (self.alive and self._mate_cooldown <= 0.0
                and self.energy >= cfg.MATE_ENERGY_THRESHOLD
                and self.hunger <= cfg.MATE_HUNGER_MAX
                and self.eat_timer <= 0.0 and not self._resting)

    def _mate_dir(self):
        """Nearest eligible partner (Manhattan) within MATE_RANGE.

        Returns (other, dx, dy, dist) or (None, None, None, None). A pure
        function of positions and attributes, like _other_agent: no new
        randomness, so determinism is preserved. Filters on
        other._mate_eligible().
        """
        best = _nearest_in_window(
            self.world, self.cx, self.cy, cfg.MATE_RANGE,
            self.world.occupied,
            accept=lambda x, y, other: other is not self and other._mate_eligible(),
        )
        if best is None:
            return (None, None, None, None)
        dx, dy, dist, other = best
        return (other, dx, dy, dist)

    # -- body --

    def update(self, dt: float) -> None:
        """Think (brain) and act (body) for dt real seconds."""
        self.age_s += dt
        self._mate_cooldown = max(0.0, self._mate_cooldown - dt)
        self._attack_cooldown = max(0.0, self._attack_cooldown - dt)
        # Hunger at the top of the tick: the reward at the bottom is the
        # need actually satisfied, not the action taken (see config.py
        # `# --- Reinforcement learning ---`).
        hunger_before = self.hunger
        self._last_inputs = self._inputs()
        (self.move_x, self.move_y, self.eat_out, self.rest_out, self.grab_out,
         self.interact_out, self.drop_out, self.attack_out, self.target_animal_out,
         self.target_agent_out) = self.brain.forward(self._last_inputs, dt)

        # Attack: strike whichever target the brain locked onto — the
        # nearest predator (target_animal) or the nearest other agent
        # (target_agent), within 1 cell. If both cross their threshold the
        # stronger raw output wins. No instinct or reward for landing a hit
        # (config.py) — only the penalty for being hurt shapes this, same
        # as the flee response, for either kind of target.
        if self._attack_cooldown <= 0.0 and self.attack_out > cfg.ATTACK_OUTPUT_THRESHOLD:
            want_animal = self.target_animal_out > cfg.TARGET_ANIMAL_OUTPUT_THRESHOLD
            want_agent = self.target_agent_out > cfg.TARGET_AGENT_OUTPUT_THRESHOLD
            target_animal = want_animal and (not want_agent or self.target_animal_out >= self.target_agent_out)
            target_agent = want_agent and not target_animal

            victim = None
            if target_animal:
                animal, _, _, adist = self._animal_dir()
                if animal is not None and animal.is_predator and adist <= 1.0:
                    victim = animal
            elif target_agent:
                other, _, _, odist = self._other_agent()
                if other is not None and odist <= 1.0:
                    victim = other

            if victim is not None:
                dmg = (self.damage * cfg.SPEAR_DAMAGE_MULT
                       if self.inventory == cfg.CELL_SPEAR else self.damage)
                victim.take_damage(dmg)
                self._attack_cooldown = cfg.ATTACK_COOLDOWN_S
                if victim.hp <= 0.0:
                    (self.world.kill_animal if target_animal else self.world.kill)(victim)

        # Survival reflex (below the brain, like biology): starving agents
        # never stop to rest — keep searching for food.
        starving = self.hunger > cfg.HUNGER_CRITICAL

        # Rest latch: the rest output hovers right at the threshold while
        # energy refills, so without a latch a nap would last one frame and
        # energy would park at the crossing instead of rising. Once down,
        # stay down until the brain stops demanding rest with energy back
        # above REST_WAKE_ENERGY — starvation breaks the sleep first.
        # Falling asleep also needs a minimum energy reserve (MIN_ENERGY_TO_REST):
        # an already-resting agent never drops below it, since energy only
        # rises while asleep — so this only gates the start of a nap.
        demands_rest = self.rest_out > cfg.REST_OUTPUT_THRESHOLD
        was_resting = self._resting
        can_start_rest = self.energy >= cfg.MIN_ENERGY_TO_REST
        resting = self._resting or (demands_rest and not starving and can_start_rest)
        if resting and (starving or (not demands_rest and self.energy >= cfg.REST_WAKE_ENERGY)):
            resting = False
        self._resting = resting

        # Grab (pick up): the brain's grab output takes whatever collectible
        # is under the agent into its one-slot inventory (food, wood, or a
        # dropped spear — any cfg.CELL_* type registered in
        # _INVENTORY_ACTIONS) — the cell empties (like eating, same regrow
        # timer where it applies) but the item is carried, not consumed.
        # The body enforces the single slot: while the inventory is full,
        # grab is ignored no matter what the brain demands.
        grabbed = False
        grab_rewarded = False
        cell = self.world.cell_type(self.cx, self.cy)
        if (self.inventory is None
                and self.grab_out > cfg.GRAB_OUTPUT_THRESHOLD
                and cell in _INVENTORY_ACTIONS):
            # An item an agent dropped is still there, but picking it back
            # up earns nothing — otherwise grab -> drop -> grab on one's
            # own cell would be an infinite reward loop (world.dropped_cells).
            grab_rewarded = not self.world.is_dropped(self.cx, self.cy)
            self.world.consume_cell(self.cx, self.cy)
            self.inventory = cell
            self._carry_time = 0.0
            self._wood_craft_progress = 0
            grabbed = True

        # Inventory actions: interact (use what's carried — dispatched by
        # item type, see _INVENTORY_ACTIONS) or drop it. Interact is
        # skipped while already eating, so it can't restart the eat_timer
        # mid-meal.
        dropped = False
        was_food = self.inventory in (cfg.CELL_RESOURCE, cfg.CELL_MEAT)
        if self.inventory is not None:
            interact_fn, drop_fn = _INVENTORY_ACTIONS[self.inventory]
            if self.interact_out > cfg.INTERACT_OUTPUT_THRESHOLD and self.eat_timer <= 0:
                interact_fn(self)
            elif self.drop_out > cfg.DROP_OUTPUT_THRESHOLD:
                dropped = drop_fn(self)
        if self.inventory is not None:
            self._carry_time += dt

        # Eating takes precedence over resting.
        if self.eat_timer > 0:
            self.eat_timer -= dt
            self.hunger = max(0.0, self.hunger - self.eat_rate * dt)
        elif self.eat_out > cfg.EAT_OUTPUT_THRESHOLD and \
                self.world.cell_type(self.cx, self.cy) in (cfg.CELL_RESOURCE, cfg.CELL_MEAT):
            self.world.consume_cell(self.cx, self.cy)
            self.eat_timer = cfg.EAT_DURATION_S
            self._meal_from_inventory = False
            self.world.record_meal()

        # Need rates are exclusive — one regime at a time:
        #   eating:  hunger falls (EAT_RATE above); energy is frozen
        #            (the meal is the replenishment: no gain and no drain)
        #   resting: energy recovers; hunger frozen (sleep freezes need)
        #   awake:   hunger rises, energy drains
        if self.eat_timer > 0:
            pass  # energy frozen while eating
        elif resting:
            # Interrupted-by-eating naps resume the timer instead of
            # restarting it (was_resting stays True across the eating
            # frames above, since the latch itself is untouched by eating).
            self._sleep_timer = self._sleep_timer + dt if was_resting else dt
            rate = _sleep_recovery_rate(self._sleep_timer) * self.rest_rate_mult
            self.energy = min(1.0, self.energy + rate * dt)
        else:
            self._sleep_timer = 0.0
            self.hunger = min(1.0, self.hunger + self.hunger_rate * dt)
            self.energy = max(0.0, self.energy - self.energy_drain_rate * dt)

        # Movement (suppressed while eating or resting). An active detour
        # overrides the brain's direction with a slide along the tangent
        # axis (or a retreat) for DETOUR_S.
        if not resting and self.eat_timer <= 0:
            dx = 2.0 * self.move_x - 1.0
            dy = 2.0 * self.move_y - 1.0
            # Food rush: the nearest food is one cell away, free, and the
            # agent is actually hungry — go for it. The brain's
            # other-agent avoidance (negative weight on other_dir) repels
            # two agents racing for the same food before either reaches
            # it, so without this they oscillate forever around the cell.
            # The racer wins the cell claim; the loser (its food now
            # occupied) re-targets next frame. Gated by hunger so a
            # satiated agent doesn't get dragged onto food it doesn't
            # want, blocking it from a neighbor who does (see h0/h1
            # hunger gates in config.py — same threshold as elsewhere in
            # this file for "agent cares about food").
            if self.hunger > cfg.HUNGER_WARNING:
                fd_dx, fd_dy, fdist = self._food_dir()
                if fdist == 1:
                    # _food_dir already returns deltas (food - cell), so
                    # the rush direction is just that delta.
                    dx, dy = float(fd_dx), float(fd_dy)
            # Mate reflex (see _mate_eligible/_mate_dir): an eligible
            # partner in MATE_RANGE overrides the brain's movement, the
            # same "inviolable body" pattern as the food rush. The
            # direction is NORMALIZED by Manhattan distance so no single
            # sub-step crosses more than one cell boundary (a raw delta
            # of 2 would skip a claim at AGENT_STEP_S * speed > 1).
            if self._mate_eligible():
                mate, mdx, mdy, mdist = self._mate_dir()
                if mate is not None and mdist <= 1.0:
                    self.world.mate(self, mate)      # adjacent: mate now
                elif mate is not None and mdist <= cfg.MATE_RANGE:
                    dx, dy = mdx / mdist, mdy / mdist
            if self._detour_timer > 0.0:
                self._detour_timer = max(0.0, self._detour_timer - dt)
                if self._detour_retreat:
                    # Backing away: push the blocked axis the other way.
                    if self._detour_axis == 'x':
                        dx, dy = float(self._detour_sign), 0.0
                    else:
                        dx, dy = 0.0, float(self._detour_sign)
                else:
                    # Sliding around: push the tangent (other) axis.
                    if self._detour_axis == 'x':
                        dx, dy = 0.0, float(self._detour_sign)
                    else:
                        dx, dy = float(self._detour_sign), 0.0
            dt_left = dt
            while dt_left > 1e-9:
                step = min(dt_left, cfg.AGENT_STEP_S)
                self._move_axis(dx * step * self.speed, 0.0, step)
                self._move_axis(0.0, dy * step * self.speed, step)
                dt_left -= step

        # Derived state for drawing and tests.
        if self.eat_timer > 0:
            self.state = "eating"
        elif resting:
            self.state = "resting"
        else:
            self.state = "active"

        # Personal learning (RL, not genetic). The ladder rewards the
        # RESULT, not the act: the eligibility trace (brain.py) is what
        # carries the credit back to the grab that made a later meal
        # possible. Mutates this agent's own brain only — self.genome
        # (what reproduction reads) is never touched here. Every constant
        # and the reasoning behind it live in config.py.
        reward = 0.0
        # 1. The need actually satisfied this tick, wherever the food came from.
        relieved = hunger_before - self.hunger
        if relieved > 0.0:
            mult = cfg.REWARD_INVENTORY_MEAL_MULT if self._meal_from_inventory else 1.0
            reward += cfg.REWARD_EAT_K * relieved * mult
        # 2. Picking food up is an investment, not a payout — and only for
        #    food the world grew (see grab_rewarded above). Also only if it
        #    is still in the inventory: grab+interact landing in the same
        #    tick means it was eaten immediately, i.e. eating off the
        #    ground by another route (see _interact_resource), which must
        #    not stack the grab reward on top of the plain meal reward.
        if grabbed and grab_rewarded and self.inventory is not None:
            reward += cfg.REWARD_GRAB
        # 3. Throwing away food you need (wood/spear aren't food, so
        #    dropping those never triggers this).
        if dropped and was_food and self.hunger > cfg.HUNGER_WARNING:
            reward += cfg.PENALTY_DROP_HUNGRY
        # 4. Starving with the solution in hand. Not the old blanket hunger
        #    punishment: this needs a full inventory *of food*, so an agent
        #    carrying wood/a spear (which can't be eaten) never pays it, and
        #    the agent still on its way to food — the case that broke that
        #    attempt — never pays it either.
        if self.inventory in (cfg.CELL_RESOURCE, cfg.CELL_MEAT) and self.hunger > cfg.HUNGER_CRITICAL:
            reward += cfg.PENALTY_STARVING_WITH_FOOD * dt
        # 5. Damage taken from a predator this tick, relative to hp_max so
        #    the `hp` trait doesn't rescale the reward (see config.py).
        if self._hp_lost_this_tick > 0.0:
            reward += cfg.PENALTY_ANIMAL_DAMAGE_K * (self._hp_lost_this_tick / self.hp_max)
            self._hp_lost_this_tick = 0.0
        self.brain.learn(reward)

        # Death: starvation (hunger >= 1.0), exhaustion (energy <= 0), old
        # age, or killed by a predator. Deferred: world.kill only marks the
        # agent; the removal happens in world.end_frame() after the agent loop.
        if (self.hunger >= 1.0 or self.energy <= 0.0
                or self.age_s >= cfg.MAX_AGE_S or self.hp <= 0.0):
            self.world.kill(self)

    def _move_axis(self, dx_units: float, dy_units: float, dt_step: float) -> None:
        """Move dx/dy cell units on one axis, claiming the new cell or
        reacting to a blocked crossing. One boundary crossing at most per
        call (AGENT_STEP_S * AGENT_SPEED < 1 cell).

        The map has no border: crossing an edge wraps onto the opposite
        side of the grid (world.wrap), a toroidal ("spherical") world.

        A failed crossing clamps the position to the *blocked* side of the
        cell (cx + 0.99 pushing right — not the far edge, which caused the
        old snap-back jitter) and then:
        - another agent owns the cell -> sticky hold: the position stays
          frozen on this axis and the cell is re-probed every
          BLOCKED_PROBE_S (polite wait; the other agent will move);
        - a rock -> it will never free, so start a DETOUR_S slide along
          the tangent axis to walk around it.
        Sliding on the other axis is untouched (each axis is its own call).
        """
        # Zero push (the other axis is doing the work): must not touch the
        # holds — the old single-hold entered with a spurious -1 sign.
        if dx_units == 0.0 and dy_units == 0.0:
            return
        axis = 'x' if dx_units else 'y'
        sign = 1 if (dx_units + dy_units) > 0 else -1

        hold = self._holds.get(axis)
        if hold is not None:
            # A direction flip on a held axis frees the hold so the agent
            # can walk away; the same direction keeps the position frozen
            # and re-probes the cell every BLOCKED_PROBE_S in case the
            # agent that owned it moved away.
            if sign != hold[0]:
                del self._holds[axis]
            else:
                hold[1] += dt_step
                nx = self.cx + sign if axis == 'x' else self.cx
                ny = self.cy if axis == 'x' else self.cy + sign
                if hold[1] >= cfg.BLOCKED_PROBE_S:
                    hold[1] = 0.0
                    if self.world.try_claim(nx, ny, self):
                        self.world.release(self.cx, self.cy, self)
                        # Position is already at the blocked boundary
                        # (clamped when the hold was set): no snap to the
                        # cell center, or the agent would teleport. Wrapped
                        # in case the hold was released across the map edge.
                        self.cx, self.cy = nx % self.world.cols, ny % self.world.rows
                        del self._holds[axis]
            return

        new_x = self.x + dx_units
        new_y = self.y + dy_units
        # floor() instead of int(): int() truncates toward zero, so a
        # leftward/upward crossing out of cell 0 went undetected and the
        # agent leaked out of bounds (int(-0.04) == 0 == cx).
        nx, ny = math.floor(new_x), math.floor(new_y)
        if nx != self.cx:  # crossing an x boundary
            if self.world.try_claim(nx, self.cy, self):
                self.world.release(self.cx, self.cy, self)
                # Wrapped: crossing off the left/right edge of the grid
                # lands on the opposite side (toroidal world, no border).
                self.cx, self.x = nx % self.world.cols, new_x % self.world.cols
            else:
                self.x = float(self.cx) + 0.5 + (0.49 if dx_units > 0 else -0.49)
                if self.world.is_walkable(nx, self.cy):
                    self._holds[axis] = [sign, 0.0]  # another agent: polite wait
                elif self._detour_timer <= 0.0:
                    self._start_detour(axis, sign)   # rock: walk around
        elif ny != self.cy:  # crossing a y boundary
            if self.world.try_claim(self.cx, ny, self):
                self.world.release(self.cx, self.cy, self)
                self.cy, self.y = ny % self.world.rows, new_y % self.world.rows
            else:
                self.y = float(self.cy) + 0.5 + (0.49 if dy_units > 0 else -0.49)
                if self.world.is_walkable(self.cx, ny):
                    self._holds[axis] = [sign, 0.0]
                elif self._detour_timer <= 0.0:
                    self._start_detour(axis, sign)
        else:
            self.x, self.y = new_x, new_y

    def _start_detour(self, axis: str, sign: int) -> None:
        """Walk around a rock (a cell that will never free — holding would
        freeze the agent forever). The map border no longer blocks: edges
        wrap onto the opposite side of the grid.

        First slide along the tangent axis, on the side that reduces
        Manhattan distance to the nearest food (arbitrary side if food is
        exactly on the blocked line). Consecutive detours on the same
        blocked direction alternate the side (zigzag), so rock clusters
        get walked around instead of hugged; after both sides failed,
        give up and back away, letting the brain re-orient. The tangent
        axis must be free to slide: drop any polite hold there.
        """
        self._detour_axis = axis
        self._detour_timer = cfg.DETOUR_S
        if (axis, sign) == self._detour_last:
            self._detour_attempts += 1
        else:
            self._detour_last = (axis, sign)
            self._detour_attempts = 0
        if self._detour_attempts >= 2:
            # Both tangent sides already failed: back away and let the
            # brain re-orient instead of hugging the obstacle forever.
            self._detour_retreat = True
            self._detour_sign = -sign
            return
        self._detour_retreat = False
        if axis == 'x':
            _, food_dy, _ = self._food_dir()
            tangent = 1 if food_dy and food_dy > 0 else (-1 if food_dy and food_dy < 0 else 1)
        else:
            food_dx, _, _ = self._food_dir()
            tangent = 1 if food_dx and food_dx > 0 else (-1 if food_dx and food_dx < 0 else 1)
        if self._detour_attempts == 1:
            tangent = -tangent  # zigzag: try the other flank of the cluster
        self._detour_sign = tangent
        self._holds.pop('y' if axis == 'x' else 'x', None)


def _selfcheck() -> None:
    """Minimal check for the wood -> spear crafting path: grab, craft,
    drop/re-pickup, and the attack damage boost. Exercises the helper
    functions directly (not the brain) so it doesn't depend on any output
    crossing threshold."""
    from sim.world import World

    world = World(cols=20, rows=20, seed=1)
    agent = world.entities[0]
    x, y = agent.cx, agent.cy

    # grab: force a wood cell under the agent, mirror the grab dispatch.
    world.grid[y][x] = cfg.CELL_WOOD
    world.consume_cell(x, y)
    agent.inventory = cfg.CELL_WOOD
    agent._wood_craft_progress = 0
    assert agent.inventory == cfg.CELL_WOOD

    # craft: WOOD_CRAFT_INTERACTIONS interactions turn wood into a spear.
    for _ in range(cfg.WOOD_CRAFT_INTERACTIONS):
        _interact_wood(agent)
    assert agent.inventory == cfg.CELL_SPEAR
    assert agent._wood_craft_progress == 0

    # drop the spear, then grab a fresh wood item and drop that too.
    agent._carry_time = cfg.CARRY_MIN_S
    assert _drop_spear(agent) is True
    assert world.grid[y][x] == cfg.CELL_SPEAR
    assert world.is_dropped(x, y)

    world.grid[y][x] = cfg.CELL_EMPTY
    agent.inventory = cfg.CELL_WOOD
    agent._carry_time = cfg.CARRY_MIN_S
    assert _drop_wood(agent) is True
    assert world.grid[y][x] == cfg.CELL_WOOD
    assert world.is_dropped(x, y)

    # a spear equipped in the inventory boosts attack damage.
    damage_bare = agent.damage
    damage_speared = agent.damage * cfg.SPEAR_DAMAGE_MULT
    assert damage_speared > damage_bare

    # killing an animal drops meat on its cell; it can be grabbed, carried
    # (dropping and re-grabbing it), and eaten from the inventory.
    animal = world.animals[0]
    world.grid[animal.cy][animal.cx] = cfg.CELL_EMPTY
    world.kill_animal(animal)
    assert world.grid[animal.cy][animal.cx] == cfg.CELL_MEAT
    assert not world.is_dropped(animal.cx, animal.cy)  # a found resource, not a self-drop

    agent.inventory = cfg.CELL_MEAT
    agent._carry_time = cfg.CARRY_MIN_S
    agent.hunger = 0.5
    _interact_resource(agent)
    assert agent.inventory is None
    assert agent.eat_timer > 0.0

    print("agent self-check OK")


if __name__ == "__main__":
    _selfcheck()
