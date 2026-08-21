"""World: a grid of cells, a day/night clock, and the agents inside it.

Pure logic, no pygame (testable headless). Cells are ints, see
sim.config: CELL_EMPTY, CELL_RESOURCE, CELL_ROCK, CELL_WOOD. The grid has
no border: it wraps toroidally (see World.wrap), so a "spherical" world.
The clock advances in update(dt) and drives the day/night cycle.

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
        self.time_sim = 30.0     # seconds since midnight, always in [0, DAY_LENGTH_S)
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

        # --- deferred entity changes (never mutate entities mid-loop) ---
        self.pending_deaths = []             # agents removed by end_frame
        self.pending_births = []             # (spot, parent_a, parent_b, genome)
        self.stats_deaths = 0
        self.stats_births = 0

        self._spawn_agents()

    # -- generation (deterministic for a given seed) --

    def _generate_grid(self) -> list:
        grid = [[cfg.CELL_EMPTY for _ in range(self.cols)] for _ in range(self.rows)]
        for y in range(self.rows):
            for x in range(self.cols):
                if self.rng.random() < cfg.ROCK_DENSITY:
                    grid[y][x] = cfg.CELL_ROCK
        # second pass: wood only on empty cells
        for y in range(self.rows):
            for x in range(self.cols):
                if grid[y][x] == cfg.CELL_EMPTY and self.rng.random() < cfg.WOOD_DENSITY:
                    grid[y][x] = cfg.CELL_WOOD
        # third pass: resources only on empty cells
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
            self.spawn_agent(cx, cy)

    def spawn_agent(self, cx, cy, genome=None, generation=0, parents=None,
                    initial_hunger=None, initial_energy=None) -> Agent:
        """Create the agent, claim its cell, append it to entities.

        Shared by the initial spawn (_spawn_agents) and births.
        initial_hunger/initial_energy: None = staggered by the rng
        (initial population); a child passes CHILD_INITIAL_HUNGER /
        CHILD_INITIAL_ENERGY.
        """
        agent = Agent(self, cx, cy, genome=genome, generation=generation,
                      parents=parents)
        if initial_hunger is not None:
            agent.hunger = initial_hunger
        if initial_energy is not None:
            agent.energy = initial_energy
        self.entities.append(agent)
        self.occupied[(cx, cy)] = agent
        return agent

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
        """Try to occupy cell (x, y), wrapped onto the grid. True if the
        cell is walkable and free."""
        x, y = self.wrap(x, y)
        if (x, y) in self.occupied:
            return False
        if not self.is_walkable(x, y):
            return False
        self.occupied[(x, y)] = agent
        return True

    def release(self, x: int, y: int, agent) -> None:
        """Give up the claim on (x, y); only the owner may release it."""
        x, y = self.wrap(x, y)
        if self.occupied.get((x, y)) is agent:
            del self.occupied[(x, y)]

    # -- deferred entity changes --

    def kill(self, agent) -> None:
        """Mark an agent for removal; the claim frees instantly (safe:
        `occupied` is only read by the food/mate scans). The removal from
        `entities` materializes in end_frame()."""
        if not agent.alive:
            return
        agent.alive = False
        self.release(agent.cx, agent.cy, agent)
        self.pending_deaths.append(agent)
        self.stats_deaths += 1

    def _cell_free_for_spawn(self, x: int, y: int) -> bool:
        """Walkable, unclaimed and food-free: a valid birth cell."""
        x, y = self.wrap(x, y)
        return (self.is_walkable(x, y) and (x, y) not in self.occupied
                and self.grid[y][x] != cfg.CELL_RESOURCE)

    def _find_child_spot(self, anchor) -> tuple | None:
        """First free cell around anchor, in a fixed deterministic order
        (no rng): 4-neighborhood first, then diagonals. A child spawns
        next to its parents."""
        cx, cy = anchor.cx, anchor.cy
        for dx, dy in [(1, 0), (-1, 0), (0, 1), (0, -1),
                       (1, 1), (1, -1), (-1, 1), (-1, -1)]:
            x, y = self.wrap(cx + dx, cy + dy)
            if self._cell_free_for_spawn(x, y):
                return x, y
        return None

    def mate(self, a, b) -> bool:
        """a and b are adjacent and mutually eligible (their callers
        verify this). Both pay MATE_ENERGY_COST and enter the mutual
        cooldown (the first mating in a frame locks both, so a pair never
        doubles up); the child genome is crossover + mutation.

        Returns False with NO cost and NO cooldown if the population is
        at MAX_POPULATION or no free cell exists — the mate reflex simply
        retries next frame while they stay adjacent.
        """
        if len(self.entities) >= cfg.MAX_POPULATION:
            return False
        spot = self._find_child_spot(a)
        if spot is None:
            return False
        a.energy -= cfg.MATE_ENERGY_COST
        b.energy -= cfg.MATE_ENERGY_COST
        a._mate_cooldown = b._mate_cooldown = cfg.MATE_COOLDOWN_S
        child_genome = a.genome.crossover(b.genome, self.rng).mutate(self.rng)
        self.pending_births.append((spot, a, b, child_genome))
        return True

    def end_frame(self) -> None:
        """After the agent loop: first removals, then births.

        Called by loop.py and the tests. Never mutates `entities` while
        the agent loop is iterating it. Removal is by identity
        (deterministic). A birth spot that was taken between mate() and
        here is re-searched; if none is left the birth is dropped (rare).
        """
        for agent in self.pending_deaths:
            self.entities.remove(agent)
        self.pending_deaths.clear()
        for spot, a, b, genome in self.pending_births:
            if not self._cell_free_for_spawn(*spot):
                spot = self._find_child_spot(a)   # spot got away: re-search
                if spot is None:
                    continue                      # rare: birth dropped
            child = self.spawn_agent(*spot, genome,
                                     generation=max(a.generation, b.generation) + 1,
                                     parents=(a.genome, b.genome),
                                     initial_hunger=cfg.CHILD_INITIAL_HUNGER,
                                     initial_energy=cfg.CHILD_INITIAL_ENERGY)
            # Childhood: a newborn cannot mate immediately (also a cheap
            # parent-child incest mitigation; full genealogy is future work).
            child._mate_cooldown = cfg.MATE_COOLDOWN_S
            self.stats_births += 1
        self.pending_births.clear()

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

    def wrap(self, x, y):
        """Wrap a coordinate onto the toroidal grid: the world has no edge,
        crossing one side lands on the opposite one (a "spherical" map).
        Works for both int cell coordinates and float positions."""
        return x % self.cols, y % self.rows

    def in_bounds(self, x: int, y: int) -> bool:
        return 0 <= x < self.cols and 0 <= y < self.rows

    def cell_type(self, x: int, y: int) -> int:
        """Cell type at (x, y), wrapped onto the grid (no border)."""
        x, y = self.wrap(x, y)
        return self.grid[y][x]

    def is_walkable(self, x: int, y: int) -> bool:
        """True on empty cells and food; rocks and wood are collidable."""
        x, y = self.wrap(x, y)
        return (self.grid[y][x] != cfg.CELL_ROCK
                and self.grid[y][x] != cfg.CELL_WOOD)
