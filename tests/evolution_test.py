"""Headless tests for genetics and evolution (no pygame, no pytest).

Self-contained like tests/smoke_agents.py: run from the repo root with
    .venv/bin/python tests/evolution_test.py

Covers, in order:
  1. mutate() purity: the parent's genome is never touched
  2. crossover()/mutate() keep the config brain shapes
  3. mating flow: two adjacent eligible agents produce a child
  4. no free cell around the parents: mating fails, no cost, no cooldown
  5. death by hunger (hunger >= 1.0)
  6. death by age (age >= MAX_AGE_S)
  7. population cap: mate() refuses beyond MAX_POPULATION
  8. determinism: two worlds with the same seed stay identical
"""

import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sim import config as cfg
from sim.genetics import Genome, TRAIT_KEYS
from sim.world import World

DT = 1.0 / 60.0


def check(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)


def test_mutation_purity() -> None:
    """mutate() is pure: the parent's genes never change."""
    rng = random.Random(7)
    g = Genome.random_initial(rng)
    before = g.flat()
    for _ in range(50):
        child = g.mutate(rng)
        check(g.flat() == before, "mutate() corrompió el genoma padre")
        # The child is a valid, independent genome.
        check(len(child.w_hidden) == len(cfg.BRAIN_W_HIDDEN), "w_hidden shape rota")
    # A clone keeps the same genes but is a fresh object.
    clone = g.clone()
    check(clone.flat() == g.flat(), "clone() no preserva los genes")
    check(clone is not g, "clone() devuelve el mismo objeto")
    print("  [1] mutate() es puro y clone() es independiente")


def test_crossover_shapes() -> None:
    """crossover() keeps the config brain shapes and trait keys."""
    rng = random.Random(11)
    a = Genome.random_initial(rng)
    b = Genome.random_initial(rng)
    for _ in range(100):
        c = a.crossover(b, rng)
        check(len(c.w_hidden) == len(cfg.BRAIN_W_HIDDEN), "w_hidden filas")
        check(all(len(r) == len(cfg.BRAIN_W_HIDDEN[0]) for r in c.w_hidden), "w_hidden cols")
        check(len(c.b_hidden) == len(cfg.BRAIN_B_HIDDEN), "b_hidden")
        check(len(c.w_out) == len(cfg.BRAIN_W_OUT), "w_out filas")
        check(all(len(r) == len(cfg.BRAIN_W_OUT[0]) for r in c.w_out), "w_out cols")
        check(len(c.b_out) == len(cfg.BRAIN_B_OUT), "b_out")
        check(set(c.traits.keys()) == set(TRAIT_KEYS), "traits keys")
        check(all(cfg.TRAIT_MIN <= t <= cfg.TRAIT_MAX for t in c.traits.values()),
              "rasgos fuera de clamp")
    print("  [2] crossover() conserva formas y clamps")


def test_death_by_hunger() -> None:
    """hunger >= 1.0: agent dies, claim frees instantly, end_frame removes it."""
    world = World(8, 8, seed=3)
    agent = world.entities[0]
    check(agent.eat_timer == 0.0, "agente inicial no debería estar comiendo")
    agent.hunger = 1.0
    agent.update(DT)
    check(not agent.alive, "no murió con hunger >= 1.0")
    check((agent.cx, agent.cy) not in world.occupied, "claim no liberado al morir")
    check(agent in world.entities, "muerto debería seguir en entities hasta end_frame")
    world.end_frame()
    check(agent not in world.entities, "muerto sigue en entities tras end_frame")
    check(world.stats_deaths == 1, "stats_deaths != 1")
    print("  [5] muerte por hambre: claim liberado y baja en end_frame")


def test_death_by_age() -> None:
    """age >= MAX_AGE_S: agent dies the same way as starvation."""
    world = World(8, 8, seed=4)
    agent = world.entities[1]
    agent.age_s = cfg.MAX_AGE_S
    agent.update(DT)
    check(not agent.alive, "no murió por vejez")
    world.end_frame()
    check(agent not in world.entities, "el muerto por vejez sigue en entities")
    print("  [6] muerte por edad: baja tras end_frame")


def _find_adjacent_free_pair(world):
    """Two adjacent walkable, food-free cells for the mating tests."""
    for y in range(world.rows):
        for x in range(world.cols):
            if not world._cell_free_for_spawn(x, y):
                continue
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nx, ny = x + dx, y + dy
                if world._cell_free_for_spawn(nx, ny):
                    return (x, y), (nx, ny)
    raise RuntimeError("no adjacent free cells found")


def test_mating_flow() -> None:
    """Two adjacent eligible agents mate: both pay the cost, enter the
    mutual cooldown, and one child (gen 1) is born next to them."""
    world = World(8, 8, seed=5)
    world.entities.clear()
    world.occupied.clear()
    world.time_sim = cfg.DAY_LENGTH_S * 0.5  # noon: agents are awake and moving
    (ax, ay), (bx, by) = _find_adjacent_free_pair(world)
    a = world.spawn_agent(ax, ay, initial_hunger=0.2, initial_energy=0.8)
    b = world.spawn_agent(bx, by, initial_hunger=0.2, initial_energy=0.8)
    a.update(DT)
    b.update(DT)
    world.end_frame()
    check(world.stats_births == 1, f"stats_births == {world.stats_births}, esperado 1")
    check(len(world.entities) == 3, f"{len(world.entities)} entidades, esperado 3")
    child = [e for e in world.entities if e not in (a, b)][0]
    check(world.occupied.get((child.cx, child.cy)) is child, "hijo sin claim")
    check(0.53 <= a.energy <= 0.56 and 0.53 <= b.energy <= 0.56,
          f"padres sin coste: a={a.energy:.3f} b={b.energy:.3f}")
    # b's own update ticked its cooldown down by DT before it could
    # re-check eligibility, so allow a tolerance of 2 * DT.
    check(abs(a._mate_cooldown - cfg.MATE_COOLDOWN_S) < 2 * DT
          and abs(b._mate_cooldown - cfg.MATE_COOLDOWN_S) < 2 * DT,
          "cooldown mutuo no fijado")
    check(child.generation == 1, f"generación del hijo == {child.generation}")
    check(child.parents is not None, "hijo sin parents registrados")
    check(child._mate_cooldown == cfg.MATE_COOLDOWN_S, "hijo sin infancia")
    check(child.hunger == cfg.CHILD_INITIAL_HUNGER and child.energy == cfg.CHILD_INITIAL_ENERGY,
          "necesidades iniciales del hijo")
    print("  [3] flujo de apareamiento: coste, cooldown, hijo válido")


def test_no_free_cell() -> None:
    """Every cell around the parent is taken: mate() fails with no cost
    and no cooldown (the reflex retries while they stay adjacent)."""
    world = World(8, 8, seed=6)
    world.entities.clear()
    world.occupied.clear()
    (ax, ay), (bx, by) = _find_adjacent_free_pair(world)
    a = world.spawn_agent(ax, ay, initial_hunger=0.2, initial_energy=0.8)
    b = world.spawn_agent(bx, by, initial_hunger=0.2, initial_energy=0.8)
    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1),
                   (1, 1), (1, -1), (-1, 1), (-1, -1)):
        x, y = world.wrap(ax + dx, ay + dy)
        if world._cell_free_for_spawn(x, y):
            world.spawn_agent(x, y)  # dummy occupant
    check(world._find_child_spot(a) is None, "aún hay celda libre alrededor")
    result = world.mate(a, b)
    check(result is False, "mate() devolvió True sin celda libre")
    check(a.energy == 0.8 and b.energy == 0.8, "coste aplicado sin nacimiento")
    check(a._mate_cooldown == 0.0 and b._mate_cooldown == 0.0,
          "cooldown aplicado sin nacimiento")
    check(world.stats_births == 0, "nacimiento contabilizado sin celda")
    print("  [4] sin celda libre: mate() falla sin coste ni cooldown")


def test_population_cap() -> None:
    """MAX_POPULATION reached: mate() refuses, no cost, no cooldown."""
    world = World(8, 8, seed=7)
    world.entities.clear()
    world.occupied.clear()
    (ax, ay), (bx, by) = _find_adjacent_free_pair(world)
    a = world.spawn_agent(ax, ay, initial_hunger=0.2, initial_energy=0.8)
    b = world.spawn_agent(bx, by, initial_hunger=0.2, initial_energy=0.8)
    old_cap = cfg.MAX_POPULATION
    cfg.MAX_POPULATION = 2
    try:
        result = world.mate(a, b)
    finally:
        cfg.MAX_POPULATION = old_cap
    check(result is False, "mate() aceptó con población al tope")
    check(a.energy == 0.8 and a._mate_cooldown == 0.0,
          "coste/cooldown aplicados sin nacimiento")
    print("  [7] tope de población: mate() rechaza sin coste")


def test_determinism() -> None:
    """Two worlds with the same seed stay identical over 2000 frames
    (positions, needs and genomes)."""
    def run(seed):
        world = World(seed=seed)
        snapshots = []
        for _ in range(2000):
            world.update(DT)
            for agent in world.entities:
                agent.update(DT)
            world.end_frame()
            snapshots.append((
                len(world.entities),
                [(a.cx, a.cy, round(a.hunger, 6), round(a.energy, 6), a.genome.flat())
                 for a in world.entities],
            ))
        return snapshots
    a = run(42)
    b = run(42)
    check(a == b, "dos mundos con la misma semilla divergieron")
    print("  [8] determinismo: dos mundos idénticos en 2000 frames")


def main() -> None:
    print("evolution tests:")
    test_mutation_purity()
    test_crossover_shapes()
    test_mating_flow()
    test_no_free_cell()
    test_death_by_hunger()
    test_death_by_age()
    test_population_cap()
    test_determinism()
    print("OK: evolution tests passed")


if __name__ == "__main__":
    main()
