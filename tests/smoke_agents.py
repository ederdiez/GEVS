"""Headless smoke test for the v1 agents (no pygame needed).

Runs the simulation for 9000 frames (150 simulated seconds = 2.5 days)
and checks, every 30 frames:
  - occupied claims are 1:1 with agents (never two agents in one cell)
  - every agent is on a walkable, in-bounds cell, needs in [0, 1]
  - food_cells is in sync with the grid
Plus global checks:
  - spawn is deterministic (same seed -> same positions)
  - no agent freezes: every agent accumulated >= MIN_MOVED cells of
    movement over the whole run (rocks and corners never trap)
  - food was eaten AND regrew (stats > 0)
  - NN behavior is sane: at full night every agent rests (or is
    critically hungry and still searching), and mean energy at night
    is higher than mean energy at day

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


def check(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)


def main() -> None:
    world = World()

    # --- spawn determinism: same seed -> same spawn cells ---
    other = World()
    spawns = [(a.cx, a.cy) for a in world.entities]
    other_spawns = [(a.cx, a.cy) for a in other.entities]
    check(spawns == other_spawns, "spawn no determinista (mismo seed -> posiciones distintas)")

    moved = [0.0] * len(world.entities)      # per-agent accumulated movement
    prev = [(a.x, a.y) for a in world.entities]

    night_energy, night_n = 0.0, 0
    day_energy, day_n = 0.0, 0

    for frame in range(FRAMES):
        world.update(DT)
        for agent in world.entities:
            agent.update(DT)

        # --- per-frame: accumulate movement (the no-freeze invariant) ---
        for i, agent in enumerate(world.entities):
            moved[i] += abs(agent.x - prev[i][0]) + abs(agent.y - prev[i][1])
            prev[i] = (agent.x, agent.y)

        # --- structural invariants, sampled ---
        if frame % CHECK_EVERY == 0:
            check(len(world.occupied) == len(world.entities),
                  f"frame {frame}: occupied ({len(world.occupied)}) != entities ({len(world.entities)})")
            for agent in world.entities:
                check(world.occupied.get((agent.cx, agent.cy)) is agent,
                      f"frame {frame}: agente en ({agent.cx},{agent.cy}) sin su claim")
                check(world.in_bounds(agent.cx, agent.cy),
                      f"frame {frame}: agente fuera del mapa en ({agent.cx},{agent.cy})")
                check(world.is_walkable(agent.cx, agent.cy),
                      f"frame {frame}: agente sobre celda no caminable")
                check(0.0 <= agent.hunger <= 1.0 and 0.0 <= agent.energy <= 1.0,
                      f"frame {frame}: necesidades fuera de rango")
            check(len(world.food_cells) == sum(row.count(cfg.CELL_RESOURCE) for row in world.grid),
                  f"frame {frame}: food_cells fuera de sync con el grid")
            for x, y in world.food_cells:
                check(world.grid[y][x] == cfg.CELL_RESOURCE,
                      f"frame {frame}: food_cells contiene una celda sin comida")

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
    for i, dist in enumerate(moved):
        check(dist >= MIN_MOVED,
              f"agente {i} congelado: solo {dist:.1f} celdas de movimiento en 150 s")

    night_mean = night_energy / night_n
    day_mean = day_energy / day_n
    check(night_mean > day_mean,
          f"energía media de noche ({night_mean:.2f}) <= media de día ({day_mean:.2f})")

    print(f"OK: all agent invariants held over {FRAMES} frames "
          f"({world.stats_resource_eaten} eaten, {world.stats_resource_regrown} regrown)")
    for i, dist in enumerate(moved):
        print(f"  agent {i:2d}: moved {dist:6.1f} cells, hunger {world.entities[i].hunger:.2f}, "
              f"energy {world.entities[i].energy:.2f}")


if __name__ == "__main__":
    main()
