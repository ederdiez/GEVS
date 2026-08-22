"""World: a grid of cells, a day/night clock, and the agents inside it.

Pure logic, no pygame (testable headless). Cells are ints, see
sim.config: CELL_EMPTY, CELL_RESOURCE, CELL_ROCK, CELL_WOOD, CELL_SPEAR.
The grid has no border: it wraps toroidally (see World.wrap), so a
"spherical" world. The clock advances in update(dt) and drives the
day/night cycle.

Food, wood and a dropped spear can all be picked up: the cell empties and
regrows on a per-type timer (see _REGROW_S; a spear never regrows, only
crafting or dropping puts one on the grid). Agents occupy cells
exclusively via claims (`occupied`), so two agents never share a cell.
Animals (sim.animal, predators) live in a separate list and don't claim
cells.
"""

import random

from sim import config as cfg
from sim.agent import Agent
from sim.animal import Animal

# Cell types agents can walk onto and pick up. Only food regrows on its
# own; wood regrows too (see _REGROW_S) but a spear never does — it only
# ever appears via crafting or a drop.
_COLLECTIBLE = (cfg.CELL_RESOURCE, cfg.CELL_WOOD, cfg.CELL_SPEAR)
_REGROW_S = {cfg.CELL_RESOURCE: cfg.RESOURCE_REGROW_S, cfg.CELL_WOOD: cfg.WOOD_REGROW_S}


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

        # --- collectible cells (food, wood: eaten/grabbed and regrow) ---
        self.regrow_timers = {}              # (x, y) -> (seconds left, cell_type)
        # An item an agent put down rather than one the world grew. Picking
        # it back up pays no reward (agent.py), which is what stops the
        # grab -> drop -> grab reward loop: a dropped item lands on the
        # dropper's own cell, so it is instantly re-grabbable.
        self.dropped_cells = set()
        self.stats_resource_eaten = 0
        self.stats_resource_regrown = 0

        # --- agent occupancy ---
        self.occupied = {}                   # (x, y) -> agent holding the claim

        # --- deferred entity changes (never mutate entities mid-loop) ---
        self.pending_deaths = []             # agents removed by end_frame
        self.pending_births = []             # (spot, parent_a, parent_b, genome)
        self.stats_deaths = 0
        self.stats_births = 0

        # --- animals (predators; scripted, no genome) ---
        self.animals = []
        self.pending_animal_deaths = []
        self._animal_respawn_timer = cfg.ANIMAL_RESPAWN_S

        self._spawn_agents()
        self._spawn_animals()

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
                 if self.is_walkable(x, y) and self.grid[y][x] not in _COLLECTIBLE]
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

    # -- animals (predators) --

    def _spawn_animals(self) -> None:
        """Place ANIMAL_SPAWN_COUNT animals on distinct walkable cells.
        Mirrors _spawn_agents; animals don't claim a cell in `occupied`."""
        spots = [(x, y) for y in range(self.rows) for x in range(self.cols)
                 if self.is_walkable(x, y)]
        self.rng.shuffle(spots)
        for cx, cy in spots[:cfg.ANIMAL_SPAWN_COUNT]:
            self.animals.append(Animal(self, cx, cy))

    def kill_animal(self, animal) -> None:
        """Mark an animal for removal; materializes in end_frame(). Mirrors
        kill(), minus the `occupied` release (animals never claim a cell)."""
        if not animal.alive:
            return
        animal.alive = False
        self.pending_animal_deaths.append(animal)

    # -- simulation clock --

    def update(self, dt: float) -> None:
        """Advance the simulated clock by dt real seconds."""
        self.time_sim += dt
        if self.time_sim >= cfg.DAY_LENGTH_S:
            self.day += 1
            self.time_sim %= cfg.DAY_LENGTH_S
        self._update_regrowth(dt)
        self._update_animal_respawn(dt)

    def _update_animal_respawn(self, dt: float) -> None:
        """Animals don't breed, so replace losses on a timer or predator
        pressure would only ever decay to zero."""
        if len(self.animals) >= cfg.ANIMAL_SPAWN_COUNT:
            self._animal_respawn_timer = cfg.ANIMAL_RESPAWN_S
            return
        self._animal_respawn_timer -= dt
        if self._animal_respawn_timer <= 0.0:
            self._animal_respawn_timer = cfg.ANIMAL_RESPAWN_S
            spots = [(x, y) for y in range(self.rows) for x in range(self.cols)
                     if self.is_walkable(x, y)]
            if spots:
                cx, cy = self.rng.choice(spots)
                self.animals.append(Animal(self, cx, cy))

    def _update_regrowth(self, dt: float) -> None:
        """Count down regrow timers; a timer reaching 0 restores the cell
        to whatever type it was (food or wood — a spear never regrows, it
        never gets a timer, see _REGROW_S)."""
        for (x, y), (left, cell) in list(self.regrow_timers.items()):
            left -= dt
            if left <= 0:
                del self.regrow_timers[(x, y)]
                self.grid[y][x] = cell
                if cell == cfg.CELL_RESOURCE:
                    self.food_cells.add((x, y))
                    self.stats_resource_regrown += 1
            else:
                self.regrow_timers[(x, y)] = (left, cell)

    # -- collectible cells and claims (used by agents) --

    def consume_cell(self, x: int, y: int) -> None:
        """Take whatever collectible is at (x, y) off the grid: the cell
        empties and, if its type regrows (see _REGROW_S), starts a timer.
        Eating off the ground, grabbing into the inventory, and picking up
        dropped wood/spear all come through here — this is about the
        *cell*, not about nutrition, so it does not touch the meal counter
        (see record_meal)."""
        x, y = self.wrap(x, y)
        cell = self.grid[y][x]
        self.grid[y][x] = cfg.CELL_EMPTY
        self.food_cells.discard((x, y))
        self.dropped_cells.discard((x, y))
        if cell in _REGROW_S:
            self.regrow_timers[(x, y)] = (_REGROW_S[cell], cell)
        else:
            self.regrow_timers.pop((x, y), None)

    def place_cell(self, x: int, y: int, cell_type: int) -> None:
        """Put cell_type at (x, y), e.g. an agent dropping its inventory.
        The inverse of consume_cell: no regrow timer, it's already there.
        The cell is marked as dropped so re-grabbing it pays no reward."""
        x, y = self.wrap(x, y)
        self.grid[y][x] = cell_type
        if cell_type == cfg.CELL_RESOURCE:
            self.food_cells.add((x, y))
        self.dropped_cells.add((x, y))
        self.regrow_timers.pop((x, y), None)

    def is_dropped(self, x: int, y: int) -> bool:
        """True if the item at (x, y) was put there by an agent, not grown
        or crafted in place."""
        return self.wrap(x, y) in self.dropped_cells

    def record_meal(self) -> None:
        """One agent started eating one resource. Counted here rather than
        in consume_cell so a grab (which empties a cell but feeds
        nobody) never inflates the stat."""
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
        """Walkable, unclaimed and empty (no food/wood/spear underfoot): a
        valid birth cell."""
        x, y = self.wrap(x, y)
        return (self.is_walkable(x, y) and (x, y) not in self.occupied
                and self.grid[y][x] not in _COLLECTIBLE)

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
        for animal in self.pending_animal_deaths:
            self.animals.remove(animal)
        self.pending_animal_deaths.clear()
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
        """True everywhere except rocks (food, wood, and a dropped spear
        are all walkable and collectible)."""
        x, y = self.wrap(x, y)
        return self.grid[y][x] != cfg.CELL_ROCK
