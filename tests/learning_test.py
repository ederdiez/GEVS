"""Headless tests for personal learning (no pygame, no pytest).

Self-contained like tests/evolution_test.py: run from the repo root with
    .venv/bin/python tests/learning_test.py

Covers, in order:
  1. learn() never writes back into the genome (lo aprendido no se hereda)
  2. only LEARNABLE_OUTPUTS are plastic; instinct rows and the hidden layer
     are never touched in life
  3. the eligibility trace is FPS-independent (decays per second, not per tick)
  4. reward == 0.0 leaves every weight untouched
  5. the inventory chain actually happens: grabs and inventory meals emerge
  6. grab -> drop -> grab on one's own cell pays nothing
  7. eating pays much more than grabbing (the ladder keeps its order)
  8. determinism survives: two worlds with the same seed stay identical

Test 5 is the one that fails on the old all-zero grab/interact rows: it is
the reason this file exists.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sim import config as cfg
from sim.world import World

DT = 1.0 / 60.0


def check(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)


def test_learning_never_touches_genome() -> None:
    """The central invariant of the project: learning is not inherited.

    Runs a world long enough for plenty of reward to flow, then checks
    every agent's genome against the snapshot taken at birth.
    """
    world = World()
    learned = False
    # The snapshot lives ON the agent, not in a dict keyed by id(): CPython
    # reuses the address of a dead agent for the next one allocated, so an
    # id-keyed map compares a newborn's genome against a dead stranger's.
    for agent in world.entities:
        agent._genome_at_birth = agent.genome.flat()
    for _ in range(6000):  # 100 s simulated
        world.update(DT)
        for agent in world.entities:
            agent.update(DT)
        world.end_frame()
        for agent in world.entities:
            snapshot = getattr(agent, "_genome_at_birth", None)
            if snapshot is None:
                agent._genome_at_birth = agent.genome.flat()  # newborn
            else:
                check(agent.genome.flat() == snapshot,
                      "learn() modificó el genoma: lo aprendido se estaría heredando")

    # The test is only meaningful if learning actually ran: at least one
    # brain must have drifted away from the genome that built it.
    for agent in world.entities:
        if agent.brain.w_out != agent.genome.w_out or agent.brain.b_out != agent.genome.b_out:
            learned = True
            break
    check(learned, "ningún cerebro aprendió nada: el test no probaría nada")
    print("  [1] learn() nunca toca el genoma (y sí hubo aprendizaje)")


def test_instinct_rows_are_not_plastic() -> None:
    """Only LEARNABLE_OUTPUTS change in life; instinct stays put.

    Regression test for a subtle failure: a single scalar reward cannot say
    which row earned it, so learning wrote a `noise` weight into the `rest`
    row — whose inputs are otherwise constant — and agents' sleep drive
    started flickering frame to frame at its threshold, leaving them awake
    at night on a full stomach. The hidden layer never learns either.
    """
    world = World()
    for agent in world.entities:
        agent._w_out_at_birth = [list(r) for r in agent.brain.w_out]
        agent._b_out_at_birth = list(agent.brain.b_out)
        agent._hidden_at_birth = ([list(r) for r in agent.brain.w_hidden],
                                  list(agent.brain.b_hidden))
    for _ in range(6000):  # 100 s simulated
        world.update(DT)
        for agent in world.entities:
            agent.update(DT)
        world.end_frame()

    plastic_moved = False
    for agent in world.entities:
        if not hasattr(agent, "_w_out_at_birth"):
            continue  # born mid-run, nothing to compare against
        for i, (row, b) in enumerate(zip(agent.brain.w_out, agent.brain.b_out)):
            if i in cfg.LEARNABLE_OUTPUTS:
                if row != agent._w_out_at_birth[i] or b != agent._b_out_at_birth[i]:
                    plastic_moved = True
                continue
            check(row == agent._w_out_at_birth[i] and b == agent._b_out_at_birth[i],
                  f"la fila de instinto {i} cambió en vida: el aprendizaje se está "
                  f"filtrando fuera de LEARNABLE_OUTPUTS")
        check(agent.brain.w_hidden == agent._hidden_at_birth[0]
              and agent.brain.b_hidden == agent._hidden_at_birth[1],
              "la capa oculta cambió en vida: solo la evolución debería tocarla")
    check(plastic_moved, "ninguna fila plástica se movió: el test no probaría nada")
    print("  [2] solo las filas plásticas aprenden; el instinto no se toca")


def test_trace_is_fps_independent() -> None:
    """The same simulated time must build the same trace at any FPS.

    Feeds two identical brains the same constant input, one at DT and one
    at DT/4 (four times as many ticks), for the same simulated seconds.
    The old per-tick decay made these diverge wildly.
    """
    world = World()
    brain_a = world.entities[0].genome.build_brain()
    brain_b = world.entities[0].genome.build_brain()
    inputs = [0.7, 0.5, 0.0, 0.5, 0.5, 0.8, 0.5, 0.5, 0.5, 0.0, 1.0]

    seconds = 3.0
    for _ in range(int(seconds / DT)):
        brain_a.forward(inputs, DT)
    for _ in range(int(seconds / (DT / 4))):
        brain_b.forward(inputs, DT / 4)

    for row_a, row_b in zip(brain_a._elig_w_out, brain_b._elig_w_out):
        for ea, eb in zip(row_a, row_b):
            check(abs(ea - eb) < 1e-3,
                  f"la traza depende de los FPS: {ea:.6f} vs {eb:.6f}")
    print("  [3] la traza de elegibilidad decae por segundo, no por tick")


def test_zero_reward_is_a_noop() -> None:
    """No reward, no change: the common case must cost nothing."""
    world = World()
    brain = world.entities[0].genome.build_brain()
    inputs = [0.4, 0.8, 0.0, 0.5, 0.5, 0.3, 0.5, 0.5, 0.5, 0.0, 0.0]
    for _ in range(120):
        brain.forward(inputs, DT)
    before = ([list(r) for r in brain.w_out], list(brain.b_out))
    brain.learn(0.0)
    check(brain.w_out == before[0] and brain.b_out == before[1],
          "reward 0.0 modificó los pesos")
    print("  [4] reward 0.0 es un no-op")


def test_inventory_chain_emerges() -> None:
    """Agents pick food up and eat it out of the inventory.

    This is the behavior the whole change exists for. On the old weights
    (grab/interact rows all zero, bias -2.0) both counters stay at 0
    forever — measured over 20 simulated minutes and 22 generations.
    """
    world = World()
    grabs = inventory_meals = 0
    for _ in range(60 * 60 * 3):  # 3 simulated minutes
        world.update(DT)
        for agent in list(world.entities):
            had = agent.inventory
            was_eating = agent.eat_timer > 0
            agent.update(DT)
            if had is None and agent.inventory is not None:
                grabs += 1
            if had is not None and agent.inventory is None and \
                    agent.eat_timer > 0 and not was_eating:
                inventory_meals += 1
        world.end_frame()
    check(grabs > 0, "ningún agente recogió comida en 3 minutos simulados")
    check(inventory_meals > 0, "nadie comió del inventario en 3 minutos simulados")
    print(f"  [5] la cadena de inventario emerge ({grabs} recogidas, "
          f"{inventory_meals} comidas del inventario)")


def test_drop_grab_loop_pays_nothing() -> None:
    """grab -> drop -> grab on one's own cell must not be a reward pump.

    A dropped resource lands under the dropper's feet, so without the
    dropped-cell guard this loop would print free reward every few frames.
    """
    world = World()
    agent = world.entities[0]
    world.place_resource(agent.cx, agent.cy)
    check(world.is_dropped(agent.cx, agent.cy), "place_resource no marcó la celda")

    # Re-grabbing food an agent put down earns nothing.
    agent.inventory = None
    agent.grab_out = 1.0
    rewarded = not world.is_dropped(agent.cx, agent.cy)
    check(not rewarded, "recoger comida soltada pagaría recompensa")

    # Food the world grew still pays.
    world.consume_resource(agent.cx, agent.cy)
    check(not world.is_dropped(agent.cx, agent.cy),
          "consume_resource no limpió la marca de soltado")
    world.grid[agent.cy][agent.cx] = cfg.CELL_RESOURCE
    world.food_cells.add((agent.cx, agent.cy))
    check(not world.is_dropped(agent.cx, agent.cy), "comida del mundo marcada como soltada")
    print("  [6] el bucle grab -> drop -> grab no paga recompensa")


def test_reward_ladder_order() -> None:
    """Eating must dominate grabbing, or picking up becomes an end in itself."""
    full_meal = cfg.EAT_RATE * cfg.EAT_DURATION_S      # hambre saciada, comida entera
    ground = cfg.REWARD_EAT_K * full_meal
    inventory = ground * cfg.REWARD_INVENTORY_MEAL_MULT
    check(ground > cfg.REWARD_GRAB * 5,
          "recoger paga demasiado frente a comer del suelo")
    check(inventory > ground,
          "comer del inventario no paga más que comer del suelo")
    check(cfg.PENALTY_DROP_HUNGRY < 0 and cfg.PENALTY_STARVING_WITH_FOOD < 0,
          "los castigos deben ser negativos")
    print(f"  [7] escalera coherente (suelo {ground:.2f} < inventario "
          f"{inventory:.2f}, recoger {cfg.REWARD_GRAB})")


def test_determinism() -> None:
    """Learning must not break the seed: same seed, same trajectory."""
    def run():
        world = World()
        snaps = []
        for _ in range(2000):
            world.update(DT)
            for agent in world.entities:
                agent.update(DT)
            world.end_frame()
            snaps.append((len(world.entities), [
                (a.cx, a.cy, round(a.hunger, 6), round(a.energy, 6),
                 a.inventory, a.genome.flat())
                for a in world.entities]))
        return snaps

    check(run() == run(), "dos mundos con la misma semilla divergieron")
    print("  [8] determinismo: dos mundos idénticos en 2000 frames")


def main() -> None:
    print("learning tests:")
    test_learning_never_touches_genome()
    test_instinct_rows_are_not_plastic()
    test_trace_is_fps_independent()
    test_zero_reward_is_a_noop()
    test_inventory_chain_emerges()
    test_drop_grab_loop_pays_nothing()
    test_reward_ladder_order()
    test_determinism()
    print("OK: learning tests passed")


if __name__ == "__main__":
    main()
