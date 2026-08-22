"""Animal: a scripted predator, no brain or genome of its own.

Wanders when no agent is near; chases the nearest living agent within
ANIMAL_DETECT_RANGE and bites it on contact. Unlike Agent, this is plain
scripted behavior (see docs/arquitectura.md "Cómo añadir algo nuevo") —
the point of the entity is to give agents something to sense and learn
from (sim.agent's `animal_dir_x/y/close/danger` inputs), not to itself
evolve or learn.
"""

from sim import config as cfg


class Animal:
    """One predator. Position is in cell units, same convention as Agent:
    x, y are floats (smooth movement), cx, cy are the integer cell."""

    def __init__(self, world, cx: int, cy: int):
        self.world = world
        self.cx, self.cy = cx, cy
        self.x, self.y = float(cx) + 0.5, float(cy) + 0.5
        self.hp = cfg.ANIMAL_HP
        self.damage = cfg.ANIMAL_DAMAGE
        self.speed = cfg.ANIMAL_SPEED
        self.is_predator = cfg.ANIMAL_IS_PREDATOR
        self.alive = True
        self._attack_cooldown = 0.0

    def take_damage(self, amount: float) -> None:
        self.hp = max(0.0, self.hp - amount)

    def _nearest_agent(self):
        """Nearest living agent by Manhattan distance within
        ANIMAL_DETECT_RANGE; (agent, dx, dy, dist) or (None, None, None, None).
        Mirrors Agent._other_agent."""
        best = None
        for other in self.world.entities:
            if not other.alive:
                continue
            dist = abs(other.cx - self.cx) + abs(other.cy - self.cy)
            if dist > cfg.ANIMAL_DETECT_RANGE:
                continue
            if best is None or dist < best[3]:
                best = (other, other.cx - self.cx, other.cy - self.cy, dist)
        return best if best is not None else (None, None, None, None)

    def update(self, dt: float) -> None:
        self._attack_cooldown = max(0.0, self._attack_cooldown - dt)
        target, dx, dy, dist = self._nearest_agent()
        if target is not None and self.is_predator:
            if dist <= 1.0:
                if self._attack_cooldown <= 0.0:
                    target.take_damage(self.damage)
                    self._attack_cooldown = cfg.ATTACK_COOLDOWN_S
            else:
                step = self.speed * dt
                self.x += step if dx > 0 else (-step if dx < 0 else 0.0)
                self.y += step if dy > 0 else (-step if dy < 0 else 0.0)
        else:
            # ponytail: no is_walkable/rock avoidance for wandering or
            # chasing — animals only reason about Manhattan distance, never
            # claim a cell. Ceiling: if they need to respect rocks visually,
            # add is_walkable + world.occupied claims like Agent._move_axis.
            step = self.speed * dt
            self.x += (self.world.rng.random() - 0.5) * step
            self.y += (self.world.rng.random() - 0.5) * step
        self.x, self.y = self.world.wrap(self.x, self.y)
        self.cx, self.cy = int(self.x), int(self.y)


if __name__ == "__main__":
    import random

    class _FakeWorld:
        cols = 10
        rows = 10

        def __init__(self):
            self.entities = []
            self.rng = random.Random(0)

        def wrap(self, x, y):
            return x % self.cols, y % self.rows

    class _FakeAgent:
        def __init__(self, cx, cy):
            self.cx, self.cy = cx, cy
            self.alive = True
            self.hp = 100.0

        def take_damage(self, amount):
            self.hp -= amount

    world = _FakeWorld()
    target = _FakeAgent(5, 5)
    world.entities.append(target)
    animal = Animal(world, 5, 5)  # spawns adjacent (same cell) to the target
    hp_before = target.hp
    animal.update(0.1)
    assert target.hp < hp_before, "a predator standing on its target should deal damage"
    print("ok")
