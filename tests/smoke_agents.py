"""Headless smoke test for the agents (no pygame needed).

Runs the simulation for 9000 frames (150 simulated seconds = 2.5 days)
and checks, every 30 frames:
  - occupied claims are 1:1 with agents (never two agents in one cell)
  - every agent is on a walkable, in-bounds cell, needs in [0, 1]
  - food_cells is in sync with the grid
  - the living population stays in [1, MAX_POPULATION]
Plus global checks:
  - spawn is deterministic (same seed -> same positions)
  - the whole trajectory is deterministic: a second world with the same
    seed, stepped side by side, stays identical (positions, needs,
    genomes) every 300 frames
  - no agent freezes: every agent that lived >= 60 s accumulated >=
    MIN_MOVED cells of movement (rocks and corners never trap; agents
    born late are skipped)
  - food was eaten AND regrew (stats > 0)
  - NN behavior is sane: at full night every agent rests (or is
    critically hungry and still searching), and mean energy at night
    is higher than mean energy at day
  - genetic invariants: trait multipliers within their clamps and all
    brain weights within the weight clamp

If the NN-behavior checks fail, the default weights in config.py are
badly tuned — that is the signal to tune them.

Run from the repo root:
    .venv/bin/python tests/smoke_agents.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sim import config as cfg
from sim.world import World

FRAMES = 9000          # 150 s at 60 fps = 2.5 simulated days
DT = 1.0 / 60.0
CHECK_EVERY = 30
MIN_MOVED = 10.0       # min total movement (cells) per agent over the whole run
MIN_AGE_MOVED = 60.0   # movement is only required for agents that lived this long


def check(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)


def main() -> None:
    world = World()
    world_b = World()  # determinism: same seed, stepped side by side

    # --- spawn determinism: same seed -> same spawn cells ---
    spawns = [(a.cx, a.cy) for a in world.entities]
    other_spawns = [(a.cx, a.cy) for a in world_b.entities]
    check(spawns == other_spawns, "spawn no determinista (mismo seed -> posiciones distintas)")

    # Per-agent accumulated movement, tracked by identity (indices break
    # when agents die): id -> [agent, dist, age_s, prev_x, prev_y].
    moved = {}
    for agent in world.entities:
        moved[id(agent)] = [agent, 0.0, agent.age_s, agent.x, agent.y]

    night_energy, night_n = 0.0, 0
    day_energy, day_n = 0.0, 0

    for frame in range(FRAMES):
        world.update(DT)
        for agent in world.entities:
            agent.update(DT)
        world.end_frame()
        # Determinism twin, stepped identically.
        world_b.update(DT)
        for agent in world_b.entities:
            agent.update(DT)
        world_b.end_frame()

        # --- per-frame: accumulate movement (the no-freeze invariant) ---
        for agent in world.entities:
            entry = moved.get(id(agent))
            if entry is None:  # born after frame 0 (reproduction)
                moved[id(agent)] = [agent, 0.0, agent.age_s, agent.x, agent.y]
                continue
            entry[1] += abs(agent.x - entry[3]) + abs(agent.y - entry[4])
            entry[2] = agent.age_s
            entry[3], entry[4] = agent.x, agent.y

        # --- structural invariants, sampled ---
        if frame % CHECK_EVERY == 0:
            check(len(world.occupied) == len(world.entities),
                  f"frame {frame}: occupied ({len(world.occupied)}) != entities ({len(world.entities)})")
            check(1 <= len(world.entities) <= cfg.MAX_POPULATION,
                  f"frame {frame}: población {len(world.entities)} fuera de [1, MAX_POPULATION]")
            for agent in world.entities:
                check(world.occupied.get((agent.cx, agent.cy)) is agent,
                      f"frame {frame}: agente en ({agent.cx},{agent.cy}) sin su claim")
                check(world.in_bounds(agent.cx, agent.cy),
                      f"frame {frame}: agente fuera del mapa en ({agent.cx},{agent.cy})")
                check(world.is_walkable(agent.cx, agent.cy),
                      f"frame {frame}: agente sobre celda no caminable")
                check(0.0 <= agent.hunger <= 1.0 and 0.0 <= agent.energy <= 1.0,
                      f"frame {frame}: necesidades fuera de rango")
                # genetic invariants (clamps are applied at creation and
                # mutation; this guards against future code paths)
                for t in agent.genome.traits.values():
                    check(cfg.TRAIT_MIN <= t <= cfg.TRAIT_MAX,
                          f"frame {frame}: rasgo fuera de clamp")
                for row in agent.genome.w_hidden + agent.genome.w_out:
                    for w in row:
                        check(-cfg.WEIGHT_CLAMP <= w <= cfg.WEIGHT_CLAMP,
                              f"frame {frame}: peso fuera de clamp")
            check(len(world.food_cells) == sum(row.count(cfg.CELL_RESOURCE) for row in world.grid),
                  f"frame {frame}: food_cells fuera de sync con el grid")
            for x, y in world.food_cells:
                check(world.grid[y][x] == cfg.CELL_RESOURCE,
                      f"frame {frame}: food_cells contiene una celda sin comida")

        # --- trajectory determinism, sampled ---
        if frame % 300 == 0:
            check(len(world.entities) == len(world_b.entities),
                  f"frame {frame}: los mundos divergieron en tamaño")
            for a, b in zip(world.entities, world_b.entities):
                check((a.cx, a.cy) == (b.cx, b.cy)
                      and round(a.hunger, 6) == round(b.hunger, 6)
                      and round(a.energy, 6) == round(b.energy, 6)
                      and a.genome.flat() == b.genome.flat(),
                      f"frame {frame}: los mundos divergieron (trayectoria no determinista)")

        # --- NN behavior, sampled on fully-night / fully-day frames ---
        if world.daylight_factor == 0.0:
            for agent in world.entities:
                sleeping = agent.rest_out > cfg.REST_OUTPUT_THRESHOLD
                check(sleeping or agent.hunger > cfg.HUNGER_CRITICAL,
                      f"frame {frame}: agente despierto de noche sin hambre crítica")
            night_energy += sum(a.energy for a in world.entities)
            night_n += len(world.entities)
        elif world.daylight_factor == 1.0:
            day_energy += sum(a.energy for a in world.entities)
            day_n += len(world.entities)

    # --- global checks ---
    check(world.stats_resource_eaten > 0, "ninguna comida consumida en 150 s")
    check(world.stats_resource_regrown > 0, "ninguna comida reapareció en 150 s")
    check(night_n > 0 and day_n > 0, "no hubo frames plenamente de día o de noche")
    for entry in moved.values():
        agent, dist, age = entry[0], entry[1], entry[2]
        if age >= MIN_AGE_MOVED:
            check(dist >= MIN_MOVED,
                  f"agente ({agent.cx},{agent.cy}) congelado: solo {dist:.1f} celdas en 150 s")

    night_mean = night_energy / night_n
    day_mean = day_energy / day_n
    check(night_mean > day_mean,
          f"energía media de noche ({night_mean:.2f}) <= media de día ({day_mean:.2f})")

    print(f"OK: all agent invariants held over {FRAMES} frames "
          f"({world.stats_resource_eaten} eaten, {world.stats_resource_regrown} regrown, "
          f"{world.stats_deaths} deaths, {len(world.entities)} alive)")
    for entry in sorted(moved.values(), key=lambda e: -e[1]):
        agent, dist, age = entry[0], entry[1], entry[2]
        print(f"  agent ({agent.cx:2d},{agent.cy:2d}) gen {agent.generation}: "
              f"moved {dist:6.1f} cells, age {age:5.1f}s, hunger {agent.hunger:.2f}, "
              f"energy {agent.energy:.2f}")


if __name__ == "__main__":
    main()
