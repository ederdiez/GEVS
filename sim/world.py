"""World: a grid of cells, a day/night clock, and the agents inside it.

Pure logic, no pygame (testable headless). Cells are ints, see
sim.config: CELL_EMPTY, CELL_OBSTACLE, CELL_RESOURCE. The clock
advances in update(dt) and drives the day/night cycle.

Food (resources) can be eaten: the cell empties and regrows after
RESOURCE_REGROW_S. Agents occupy cells exclusively via claims
(`occupied`), so two agents never share a cell.
"""

import random

from sim import config as cfg
from sim.agent import Agent


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
        self.food_cells = set()              # (x, y) of every cell holding food
        self.grid = self._generate_grid()
        self.entities = []

        # --- food (resources that can be eaten and regrow) ---
        self.regrow_timers = {}              # (x, y) -> seconds until regrowth
        self.stats_resource_eaten = 0
        self.stats_resource_regrown = 0

        # --- agent occupancy ---
        self.occupied = {}                   # (x, y) -> agent holding the claim
        self._spawn_agents()

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
                    self.food_cells.add((x, y))
        return grid

    # -- agents --

    def _spawn_agents(self) -> None:
        """Place AGENT_COUNT agents on distinct walkable, food-free cells.

        Deterministic: draws from the world rng, so the same seed always
        produces the same spawn points.
        """
        spots = [(x, y) for y in range(self.rows) for x in range(self.cols)
                 if self.is_walkable(x, y) and self.grid[y][x] != cfg.CELL_RESOURCE]
        self.rng.shuffle(spots)
        for cx, cy in spots[:cfg.AGENT_COUNT]:
            agent = Agent(self, cx, cy)
            self.entities.append(agent)
            self.occupied[(cx, cy)] = agent

    # -- simulation clock --

    def update(self, dt: float) -> None:
        """Advance the simulated clock by dt real seconds."""
        self.time_sim += dt
        if self.time_sim >= cfg.DAY_LENGTH_S:
            self.day += 1
            self.time_sim %= cfg.DAY_LENGTH_S
        self._update_regrowth(dt)

    def _update_regrowth(self, dt: float) -> None:
        """Count down regrow timers; a timer reaching 0 restores the food."""
        for (x, y), left in list(self.regrow_timers.items()):
            left -= dt
            if left <= 0:
                del self.regrow_timers[(x, y)]
                self.grid[y][x] = cfg.CELL_RESOURCE
                self.food_cells.add((x, y))
                self.stats_resource_regrown += 1
            else:
                self.regrow_timers[(x, y)] = left

    # -- food and claims (used by agents) --

    def consume_resource(self, x: int, y: int) -> None:
        """Eat the food at (x, y): the cell empties and starts regrowing."""
        self.grid[y][x] = cfg.CELL_EMPTY
        self.food_cells.discard((x, y))
        self.regrow_timers[(x, y)] = cfg.RESOURCE_REGROW_S
        self.stats_resource_eaten += 1

    def try_claim(self, x: int, y: int, agent) -> bool:
        """Try to occupy cell (x, y). True if the cell is walkable and free."""
        if (x, y) in self.occupied:
            return False
        if not self.is_walkable(x, y):
            return False
        self.occupied[(x, y)] = agent
        return True

    def release(self, x: int, y: int, agent) -> None:
        """Give up the claim on (x, y); only the owner may release it."""
        if self.occupied.get((x, y)) is agent:
            del self.occupied[(x, y)]

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
