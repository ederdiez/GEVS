"""Agent: the body that executes what the brain proposes.

The agent has needs (hunger, energy) and a position in the grid. Each
frame its brain (sim.brain, the neural network) receives signals about
the agent and the world, and returns intentions (direction, eat, rest).
This module is the *body*: it enforces what is inviolable (no rocks, no
shared cells, eat only on food, no movement while resting) and applies
the need rates. All behavior emerges from the brain's outputs; there
are no programmed behaviors here.
"""

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

    # -- brain signals --

    def _inputs(self) -> list:
        """The 7 normalized inputs the brain reads (order matches config)."""
        world = self.world
        dx, dy, dist = self._food_dir()
        food_close = 1.0 - min(dist / cfg.FOOD_SENSE_RANGE, 1.0) if dist is not None else 0.0
        return [
            self.hunger,
            self.energy,
            1.0 - world.daylight_factor,
            (dx + 1.0) / 2.0 if dx is not None else 0.5,
            (dy + 1.0) / 2.0 if dy is not None else 0.5,
            food_close,
            world.rng.random(),  # noise: wandering without breaking the seed
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

    # -- body --

    def update(self, dt: float) -> None:
        """Think (brain) and act (body) for dt real seconds."""
        self.move_x, self.move_y, self.eat_out, self.rest_out = BRAIN.forward(self._inputs())

        # Survival reflex (below the brain, like biology): starving agents
        # never stop to rest — keep searching for food.
        starving = self.hunger > cfg.HUNGER_CRITICAL
        resting = self.rest_out > cfg.REST_OUTPUT_THRESHOLD and not starving

        # Eating takes precedence over resting.
        if self.eat_timer > 0:
            self.eat_timer -= dt
            self.hunger = max(0.0, self.hunger - cfg.EAT_RATE * dt)
        elif self.eat_out > cfg.EAT_OUTPUT_THRESHOLD and \
                self.world.cell_type(self.cx, self.cy) == cfg.CELL_RESOURCE:
            self.world.consume_resource(self.cx, self.cy)
            self.eat_timer = cfg.EAT_DURATION_S

        # Needs rates (hunger rises only while awake; sleep freezes it).
        if resting:
            self.energy = min(1.0, self.energy + cfg.ENERGY_REST_RATE * dt)
        else:
            self.hunger = min(1.0, self.hunger + cfg.HUNGER_RATE * dt)
            self.energy = max(0.0, self.energy - cfg.ENERGY_DRAIN_RATE * dt)

        # Movement (suppressed while eating or resting).
        if not resting and self.eat_timer <= 0:
            dx = 2.0 * self.move_x - 1.0
            dy = 2.0 * self.move_y - 1.0
            dt_left = dt
            while dt_left > 1e-9:
                step = min(dt_left, cfg.AGENT_STEP_S)
                self._move_axis(dx * step * cfg.AGENT_SPEED, 0.0)
                self._move_axis(0.0, dy * step * cfg.AGENT_SPEED)
                dt_left -= step

        # Derived state for drawing and tests.
        if self.eat_timer > 0:
            self.state = "eating"
        elif resting:
            self.state = "resting"
        else:
            self.state = "active"

    def _move_axis(self, dx_units: float, dy_units: float) -> None:
        """Move dx/dy cell units on one axis, claiming the new cell or sliding.

        The move is clamped to at most one cell boundary per axis per step
        (AGENT_STEP_S * AGENT_SPEED < 1 cell), so a single transition here
        always lands on the neighboring cell.
        """
        new_x = self.x + dx_units
        new_y = self.y + dy_units
        nx, ny = int(new_x), int(new_y)
        if nx != self.cx:  # crossing an x boundary
            if self.world.try_claim(nx, self.cy, self):
                self.world.release(self.cx, self.cy, self)
                self.cx, self.x = nx, new_x
            else:
                self.x = float(self.cx) + 0.5 - (0.49 if dx_units > 0 else -0.49)
        elif ny != self.cy:  # crossing a y boundary
            if self.world.try_claim(self.cx, ny, self):
                self.world.release(self.cx, self.cy, self)
                self.cy, self.y = ny, new_y
            else:
                self.y = float(self.cy) + 0.5 - (0.49 if dy_units > 0 else -0.49)
        else:
            self.x, self.y = new_x, new_y
