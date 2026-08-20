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
from sim.brain import BRAIN


class Agent:
    """One individual. Position is in cell units: x, y are floats
    (smooth movement), cx, cy are the integer cell the agent occupies."""

    def __init__(self, world, cx: int, cy: int):
        self.world = world
        self.cx, self.cy = cx, cy
        self.x, self.y = float(cx) + 0.5, float(cy) + 0.5  # start at cell center

        # Needs (0-1). Initial values staggered so agents wake at different
        # times of the morning instead of all at once.
        self.hunger = world.rng.random() * 0.4
        self.energy = 0.6 + world.rng.random() * 0.4

        self.eat_timer = 0.0       # > 0 while eating (no movement)
        self.move_x = 0.0          # last brain output, kept for state/tests
        self.move_y = 0.0
        self.eat_out = 0.0
        self.rest_out = 0.0
        self.state = "active"      # derived: eating / resting / active

        # Per-axis sticky hold: axis -> [sign, timer]. While a cell is
        # blocked by another agent, the position freezes on that axis and
        # the cell is re-probed every BLOCKED_PROBE_S (polite wait: the
        # other agent will move).
        self._holds = {}

        # Detour: rocks and the map border never free, so instead of
        # holding, slide along the tangent axis for DETOUR_S to walk
        # around them (see _start_detour).
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
        """The 10 normalized inputs the brain reads (order matches config)."""
        world = self.world
        dx, dy, dist = self._food_dir()
        food_close = 1.0 - min(dist / cfg.FOOD_SENSE_RANGE, 1.0) if dist is not None else 0.0
        odx, ody, odist = self._other_agent()
        other_close = 1.0 - min(odist / cfg.AGENT_SENSE_RANGE, 1.0) if odist is not None else 0.0
        return [
            self.hunger,
            self.energy,
            1.0 - world.daylight_factor,
            (dx + 1.0) / 2.0 if dx is not None else 0.5,
            (dy + 1.0) / 2.0 if dy is not None else 0.5,
            food_close,
            world.rng.random(),  # noise: wandering without breaking the seed
            (odx + 1.0) / 2.0 if odx is not None else 0.5,
            (ody + 1.0) / 2.0 if ody is not None else 0.5,
            other_close,
        ]

    def _food_dir(self):
        """Nearest food cell by Manhattan distance; (dx, dy, dist) or (None, None, None)."""
        best = None
        for fx, fy in self.world.food_cells:
            dist = abs(fx - self.cx) + abs(fy - self.cy)
            if dist > cfg.FOOD_SENSE_RANGE:
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

    # -- body --

    def update(self, dt: float) -> None:
        """Think (brain) and act (body) for dt real seconds."""
        self.move_x, self.move_y, self.eat_out, self.rest_out = BRAIN.forward(self._inputs())

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

        # Eating takes precedence over resting.
        if self.eat_timer > 0:
            self.eat_timer -= dt
            self.hunger = max(0.0, self.hunger - cfg.EAT_RATE * dt)
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
            self.energy = min(1.0, self.energy + cfg.ENERGY_REST_RATE * dt)
        else:
            self.hunger = min(1.0, self.hunger + cfg.HUNGER_RATE * dt)
            self.energy = max(0.0, self.energy - cfg.ENERGY_DRAIN_RATE * dt)

        # Movement (suppressed while eating or resting). An active detour
        # overrides the brain's direction with a slide along the tangent
        # axis (or a retreat) for DETOUR_S.
        if not resting and self.eat_timer <= 0:
            dx = 2.0 * self.move_x - 1.0
            dy = 2.0 * self.move_y - 1.0
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
                self._move_axis(dx * step * cfg.AGENT_SPEED, 0.0, step)
                self._move_axis(0.0, dy * step * cfg.AGENT_SPEED, step)
                dt_left -= step

        # Derived state for drawing and tests.
        if self.eat_timer > 0:
            self.state = "eating"
        elif resting:
            self.state = "resting"
        else:
            self.state = "active"

    def _move_axis(self, dx_units: float, dy_units: float, dt_step: float) -> None:
        """Move dx/dy cell units on one axis, claiming the new cell or
        reacting to a blocked crossing. One boundary crossing at most per
        call (AGENT_STEP_S * AGENT_SPEED < 1 cell).

        A failed crossing clamps the position to the *blocked* side of the
        cell (cx + 0.99 pushing right — not the far edge, which caused the
        old snap-back jitter) and then:
        - another agent owns the cell -> sticky hold: the position stays
          frozen on this axis and the cell is re-probed every
          BLOCKED_PROBE_S (polite wait; the other agent will move);
        - a rock or the map border -> it will never free, so start a
          DETOUR_S slide along the tangent axis to walk around it.
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
                        # cell center, or the agent would teleport.
                        self.cx, self.cy = nx, ny
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
                self.cx, self.x = nx, new_x
            else:
                self.x = float(self.cx) + 0.5 + (0.49 if dx_units > 0 else -0.49)
                if self.world.is_walkable(nx, self.cy):
                    self._holds[axis] = [sign, 0.0]  # another agent: polite wait
                elif self._detour_timer <= 0.0:
                    self._start_detour(axis, sign)   # rock or border: walk around
        elif ny != self.cy:  # crossing a y boundary
            if self.world.try_claim(self.cx, ny, self):
                self.world.release(self.cx, self.cy, self)
                self.cy, self.y = ny, new_y
            else:
                self.y = float(self.cy) + 0.5 + (0.49 if dy_units > 0 else -0.49)
                if self.world.is_walkable(self.cx, ny):
                    self._holds[axis] = [sign, 0.0]
                elif self._detour_timer <= 0.0:
                    self._start_detour(axis, sign)
        else:
            self.x, self.y = new_x, new_y

    def _start_detour(self, axis: str, sign: int) -> None:
        """Walk around a rock or the map border (a cell that will never
        free — holding would freeze the agent forever).

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
