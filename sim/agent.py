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
        self.rest_rate = cfg.ENERGY_REST_RATE * t["rest_rate"]
        self.age_s = 0.0
        self.alive = True
        self._mate_cooldown = 0.0

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
        self.state = "active"      # derived: eating / resting / active
        # Carried resource (one slot; None or a cfg.CELL_* int). Set by the
        # grab output; deposit/consume of the inventory is future work, so
        # once full the slot stays taken until death.
        self.inventory = None

        # Per-axis sticky hold: axis -> [sign, timer]. While a cell is
        # blocked by another agent, the position freezes on that axis and
        # the cell is re-probed every BLOCKED_PROBE_S (polite wait: the
        # other agent will move).
        self._holds = {}

        # Detour: rocks and wood never free, so instead of holding, slide
        # along the tangent axis for DETOUR_S to walk around them (see
        # _start_detour). The map itself has no border — edges wrap.
        self._detour_axis = None
        self._detour_sign = 0
        self._detour_timer = 0.0
        self._detour_retreat = False  # True: push back, not slide sideways
        self._detour_last = None      # (axis, sign) of the previous detour
        self._detour_attempts = 0     # consecutive detours on the same (axis, sign)

        # Rest latch: once down, stay down until refilled or starving.
        self._resting = False

    # -- brain signals --

    def _inputs(self) -> list:
        """The 11 normalized inputs the brain reads (order matches config)."""
        world = self.world
        dx, dy, dist = self._food_dir()
        food_close = 1.0 - min(dist / self.food_sense_range, 1.0) if dist is not None else 0.0
        odx, ody, odist = self._other_agent()
        other_close = 1.0 - min(odist / cfg.AGENT_SENSE_RANGE, 1.0) if odist is not None else 0.0
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
        ]

    def _food_dir(self):
        """Nearest food cell by Manhattan distance; (dx, dy, dist) or (None, None, None).

        A food cell already claimed by another agent is skipped: when two
        agents race for the same food, whoever reaches the cell first keeps
        it as a target, and the other re-targets the next nearest food
        instead of piling up next to it in a polite hold. The agent's own
        claim is kept, so standing on food still counts as eating it.
        """
        best = None
        for fx, fy in self.world.food_cells:
            owner = self.world.occupied.get((fx, fy))
            if owner is not None and owner is not self:
                continue
            dist = abs(fx - self.cx) + abs(fy - self.cy)
            if dist > self.food_sense_range:
                continue
            if best is None or dist < best[2]:
                best = (fx - self.cx, fy - self.cy, dist)
        return best if best is not None else (None, None, None)

    def _other_agent(self):
        """Nearest other agent by Manhattan; (dx, dy, dist) or (None, None, None).

        Mirrors `_food_dir`: a pure function of positions, no new randomness,
        so determinism is preserved. Only senses within AGENT_SENSE_RANGE —
        "personal space" — so the avoidance signal engages near contact only.
        """
        best = None
        for other in self.world.entities:
            if other is self:
                continue
            dist = abs(other.cx - self.cx) + abs(other.cy - self.cy)
            if dist > cfg.AGENT_SENSE_RANGE:
                continue
            if best is None or dist < best[2]:
                best = (other.cx - self.cx, other.cy - self.cy, dist)
        return best if best is not None else (None, None, None)

    def _mate_eligible(self) -> bool:
        """Eligible to mate: alive, off cooldown, fed and rested enough.

        This drive lives in the body, not the brain: adding mate inputs
        would break the 11->6->5 topology and the hand-tuned weights
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
        best = None
        for other in self.world.entities:
            if other is self or not other._mate_eligible():
                continue
            dist = abs(other.cx - self.cx) + abs(other.cy - self.cy)
            if dist > cfg.MATE_RANGE:
                continue
            if best is None or dist < best[2]:
                best = (other, other.cx - self.cx, other.cy - self.cy, dist)
        return best if best is not None else (None, None, None, None)

    # -- body --

    def update(self, dt: float) -> None:
        """Think (brain) and act (body) for dt real seconds."""
        self.age_s += dt
        self._mate_cooldown = max(0.0, self._mate_cooldown - dt)
        self.move_x, self.move_y, self.eat_out, self.rest_out, self.grab_out = self.brain.forward(self._inputs())

        # Survival reflex (below the brain, like biology): starving agents
        # never stop to rest — keep searching for food.
        starving = self.hunger > cfg.HUNGER_CRITICAL

        # Rest latch: the rest output hovers right at the threshold while
        # energy refills, so without a latch a nap would last one frame and
        # energy would park at the crossing instead of rising. Once down,
        # stay down until the brain stops demanding rest with energy back
        # above REST_WAKE_ENERGY — starvation breaks the sleep first.
        demands_rest = self.rest_out > cfg.REST_OUTPUT_THRESHOLD
        resting = self._resting or (demands_rest and not starving)
        if resting and (starving or (not demands_rest and self.energy >= cfg.REST_WAKE_ENERGY)):
            resting = False
        self._resting = resting

        # Grab (pick up): the brain's grab output takes the food under the
        # agent into its one-slot inventory — the cell empties (like
        # eating, same regrow timer) but the food is carried, not consumed.
        # The body enforces the single slot: while the inventory is full,
        # grab is ignored no matter what the brain demands. Depositing or
        # consuming the carried resource is future work.
        grabbed = False
        if (self.inventory is None
                and self.grab_out > cfg.GRAB_OUTPUT_THRESHOLD
                and self.world.cell_type(self.cx, self.cy) == cfg.CELL_RESOURCE):
            self.world.consume_resource(self.cx, self.cy)
            self.inventory = cfg.CELL_RESOURCE
            grabbed = True

        # Eating takes precedence over resting.
        if self.eat_timer > 0:
            self.eat_timer -= dt
            self.hunger = max(0.0, self.hunger - self.eat_rate * dt)
        elif self.eat_out > cfg.EAT_OUTPUT_THRESHOLD and \
                self.world.cell_type(self.cx, self.cy) == cfg.CELL_RESOURCE:
            self.world.consume_resource(self.cx, self.cy)
            self.eat_timer = cfg.EAT_DURATION_S

        # Need rates are exclusive — one regime at a time:
        #   eating:  hunger falls (EAT_RATE above); energy is frozen
        #            (the meal is the replenishment: no gain and no drain)
        #   resting: energy recovers; hunger frozen (sleep freezes need)
        #   awake:   hunger rises, energy drains
        if self.eat_timer > 0:
            pass  # energy frozen while eating
        elif resting:
            self.energy = min(1.0, self.energy + self.rest_rate * dt)
        else:
            self.hunger = min(1.0, self.hunger + self.hunger_rate * dt)
            self.energy = max(0.0, self.energy - self.energy_drain_rate * dt)

        # Movement (suppressed while eating or resting). An active detour
        # overrides the brain's direction with a slide along the tangent
        # axis (or a retreat) for DETOUR_S.
        if not resting and self.eat_timer <= 0:
            dx = 2.0 * self.move_x - 1.0
            dy = 2.0 * self.move_y - 1.0
            # Food rush: the nearest food is one cell away and free — go
            # for it. The brain's other-agent avoidance (negative weight
            # on other_dir) repels two agents racing for the same food
            # before either reaches it, so without this they oscillate
            # forever around the cell. The racer wins the cell claim; the
            # loser (its food now occupied) re-targets next frame.
            fd_dx, fd_dy, fdist = self._food_dir()
            if fdist == 1:
                # _food_dir already returns deltas (food - cell), so the
                # rush direction is just that delta.
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

        # Personal learning (RL, not genetic): reward grabbing food only.
        # No hunger punishment: an agent that was approaching food but
        # hadn't reached it yet would get its weights pushed away from
        # the very behavior that was working. Mutates this agent's own
        # brain only — self.genome (what reproduction reads) is never
        # touched here.
        reward = cfg.REWARD_GRAB_SUCCESS if grabbed else 0.0
        self.brain.learn(reward)

        # Death: starvation (hunger >= 1.0), exhaustion (energy <= 0), or
        # old age. Deferred: world.kill only marks the agent; the removal
        # happens in world.end_frame() after the agent loop.
        if self.hunger >= 1.0 or self.energy <= 0.0 or self.age_s >= cfg.MAX_AGE_S:
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
        - a rock or wood -> it will never free, so start a DETOUR_S slide
          along the tangent axis to walk around it.
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
        """Walk around a rock or wood cell (one that will never free —
        holding would freeze the agent forever). The map border no longer
        blocks: edges wrap onto the opposite side of the grid.

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
