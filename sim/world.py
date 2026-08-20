"""World: a grid of cells plus a day/night clock.

Pure logic, no pygame (testable headless). Cells are ints, see
sim.config: CELL_EMPTY, CELL_OBSTACLE, CELL_RESOURCE. The clock
advances in update(dt) and drives the day/night cycle.
"""

import random

from sim import config as cfg


class World:
    """A 2D grid of static cells with a simulated day/night clock."""

    def __init__(self, cols=None, rows=None, seed=None):
        self.cols = cols if cols is not None else cfg.GRID_COLS
        self.rows = rows if rows is not None else cfg.GRID_ROWS
        self.cell_size = cfg.CELL_SIZE
        self.rng = random.Random(seed if seed is not None else cfg.WORLD_SEED)

        # --- simulation clock ---
        self.time_sim = 0.0     # seconds since midnight, always in [0, DAY_LENGTH_S)
        self.day = 1

        # --- world content ---
        self.grid = self._generate_grid()
        self.entities = []                   # future agents will live here

    # -- generation (deterministic for a given seed) --

    def _generate_grid(self) -> list:
        grid = [[cfg.CELL_EMPTY for _ in range(self.cols)] for _ in range(self.rows)]
        for y in range(self.rows):
            for x in range(self.cols):
                if self.rng.random() < cfg.OBSTACLE_DENSITY:
                    grid[y][x] = cfg.CELL_OBSTACLE
        # second pass: resources only on empty cells
        for y in range(self.rows):
            for x in range(self.cols):
                if grid[y][x] == cfg.CELL_EMPTY and self.rng.random() < cfg.RESOURCE_DENSITY:
                    grid[y][x] = cfg.CELL_RESOURCE
        return grid

    # -- simulation clock --

    def update(self, dt: float) -> None:
        """Advance the simulated clock by dt real seconds."""
        self.time_sim += dt
        if self.time_sim >= cfg.DAY_LENGTH_S:
            self.day += 1
            self.time_sim %= cfg.DAY_LENGTH_S

    @property
    def hour(self) -> float:
        """Current simulated hour (0.0-24.0)."""
        return self.time_sim / cfg.DAY_LENGTH_S * 24.0

    @property
    def daylight_factor(self) -> float:
        """0.0 = full night, 1.0 = full daylight (piecewise linear)."""
        h = self.hour
        if h < cfg.DAWN_START or h >= cfg.DUSK_END:
            return 0.0
        if h < cfg.DAWN_END:
            return (h - cfg.DAWN_START) / (cfg.DAWN_END - cfg.DAWN_START)
        if h < cfg.DUSK_START:
            return 1.0
        return 1.0 - (h - cfg.DUSK_START) / (cfg.DUSK_END - cfg.DUSK_START)

    # -- query API (what future agents will use) --

    def in_bounds(self, x: int, y: int) -> bool:
        return 0 <= x < self.cols and 0 <= y < self.rows

    def cell_type(self, x: int, y: int) -> int:
        """Cell type at (x, y); out of bounds counts as an obstacle."""
        if not self.in_bounds(x, y):
            return cfg.CELL_OBSTACLE
        return self.grid[y][x]

    def is_walkable(self, x: int, y: int) -> bool:
        return self.in_bounds(x, y) and self.grid[y][x] != cfg.CELL_OBSTACLE
