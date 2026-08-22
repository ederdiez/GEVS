"""Genome: the heritable unit of an agent — brain weight tables + body traits.

Pure logic, no pygame. Every random draw takes the world's rng, so a
fixed seed reproduces the same population and the same evolution.

The Genome owns the weights; the Brain (sim.brain) deep-copies them and
may learn from them in-life (reward-modulated Hebbian RL), so it never
writes back into the Genome. crossover()/mutate() are PURE: they return
a new Genome and never touch self.

Traits are multipliers ~1.0 over the base body rates in sim.config
(speed, food_sense, hunger_rate, energy_drain, eat_rate, rest_rate,
damage, hp), clamped to [TRAIT_MIN, TRAIT_MAX] (see config.py
`# --- Genetics ---`).
"""

import math

from sim import config as cfg
from sim.brain import Brain

# Order of the body traits inside a Genome (dict keys and flat() repr).
TRAIT_KEYS = ("speed", "food_sense", "hunger_rate", "energy_drain", "eat_rate", "rest_rate", "damage", "hp")


def _clamp_weight(w: float) -> float:
    return max(-cfg.WEIGHT_CLAMP, min(cfg.WEIGHT_CLAMP, w))


def _clamp_trait(t: float) -> float:
    return max(cfg.TRAIT_MIN, min(cfg.TRAIT_MAX, t))


def _mutate_weight(w: float, rng) -> float:
    """Additive gaussian mutation, clamped to the weight bounds."""
    if rng.random() < cfg.WEIGHT_MUTATION_RATE:
        w += rng.gauss(0.0, cfg.WEIGHT_MUTATION_SIGMA)
    return _clamp_weight(w)


def _mutate_trait(t: float, rng) -> float:
    """Multiplicative (log-normal) mutation: keeps the trait positive."""
    if rng.random() < cfg.TRAIT_MUTATION_RATE:
        t *= math.exp(rng.gauss(0.0, cfg.TRAIT_MUTATION_SIGMA))
    return _clamp_trait(t)


class Genome:
    """Weight tables + body traits. The only unit of inheritance:
    crossover/mutation/clone operate here and nowhere else."""

    def __init__(self, w_hidden, b_hidden, w_out, b_out, traits):
        """Validates shapes against cfg.BRAIN_* and trait keys against
        TRAIT_KEYS, so no malformed genome ever reaches a brain."""
        if (len(w_hidden) != len(cfg.BRAIN_W_HIDDEN)
                or any(len(row) != len(cfg.BRAIN_W_HIDDEN[0]) for row in w_hidden)):
            raise ValueError(f"w_hidden shape {len(w_hidden)}x{len(w_hidden[0]) if w_hidden else 0}"
                             f" != {len(cfg.BRAIN_W_HIDDEN)}x{len(cfg.BRAIN_W_HIDDEN[0])}")
        if len(b_hidden) != len(cfg.BRAIN_B_HIDDEN):
            raise ValueError(f"b_hidden len {len(b_hidden)} != {len(cfg.BRAIN_B_HIDDEN)}")
        if (len(w_out) != len(cfg.BRAIN_W_OUT)
                or any(len(row) != len(cfg.BRAIN_W_OUT[0]) for row in w_out)):
            raise ValueError(f"w_out shape {len(w_out)}x{len(w_out[0]) if w_out else 0}"
                             f" != {len(cfg.BRAIN_W_OUT)}x{len(cfg.BRAIN_W_OUT[0])}")
        if len(b_out) != len(cfg.BRAIN_B_OUT):
            raise ValueError(f"b_out len {len(b_out)} != {len(cfg.BRAIN_B_OUT)}")
        if set(traits.keys()) != set(TRAIT_KEYS):
            raise ValueError(f"traits keys {sorted(traits)} != {sorted(TRAIT_KEYS)}")
        self.w_hidden = w_hidden
        self.b_hidden = b_hidden
        self.w_out = w_out
        self.b_out = b_out
        self.traits = traits

    def build_brain(self) -> Brain:
        """A Brain seeded from these tables. Brain.__init__ deep-copies
        them, so the Brain can learn (personal, in-life RL) without ever
        mutating this Genome — the only thing crossover()/mutate() see."""
        return Brain(self.w_hidden, self.b_hidden, self.w_out, self.b_out)

    def clone(self) -> "Genome":
        """Independent copy (fresh lists; nothing is shared)."""
        return Genome([list(row) for row in self.w_hidden], list(self.b_hidden),
                      [list(row) for row in self.w_out], list(self.b_out),
                      dict(self.traits))

    def flat(self) -> tuple:
        """Hashable, deterministic representation (tests, HUD, determinism)."""
        return (tuple(tuple(row) for row in self.w_hidden), tuple(self.b_hidden),
                tuple(tuple(row) for row in self.w_out), tuple(self.b_out),
                tuple(self.traits[k] for k in TRAIT_KEYS))

    def crossover(self, other, rng) -> "Genome":
        """Uniform per-gene crossover: each gene from self or other with
        p = 0.5 (the standard in weight evolution, e.g. NEAT)."""
        w_hidden = [[wa if rng.random() < 0.5 else wb
                     for wa, wb in zip(row_a, row_b)]
                    for row_a, row_b in zip(self.w_hidden, other.w_hidden)]
        b_hidden = [a if rng.random() < 0.5 else b
                    for a, b in zip(self.b_hidden, other.b_hidden)]
        w_out = [[wa if rng.random() < 0.5 else wb
                  for wa, wb in zip(row_a, row_b)]
                 for row_a, row_b in zip(self.w_out, other.w_out)]
        b_out = [a if rng.random() < 0.5 else b
                 for a, b in zip(self.b_out, other.b_out)]
        traits = {k: (self.traits[k] if rng.random() < 0.5 else other.traits[k])
                  for k in TRAIT_KEYS}
        return Genome(w_hidden, b_hidden, w_out, b_out, traits)

    def mutate(self, rng) -> "Genome":
        """PURE: returns a new Genome with mutated genes; never touches self."""
        w_hidden = [[_mutate_weight(w, rng) for w in row] for row in self.w_hidden]
        b_hidden = [_mutate_weight(b, rng) for b in self.b_hidden]
        w_out = [[_mutate_weight(w, rng) for w in row] for row in self.w_out]
        b_out = [_mutate_weight(b, rng) for b in self.b_out]
        traits = {k: _mutate_trait(self.traits[k], rng) for k in TRAIT_KEYS}
        return Genome(w_hidden, b_hidden, w_out, b_out, traits)

    @staticmethod
    def random_initial(rng) -> "Genome":
        """The initial population: config tables ± small gaussian noise
        (weights) and 1.0 ± noise (traits), all clamped."""
        def w_noise(v: float) -> float:
            return _clamp_weight(v + rng.gauss(0.0, cfg.INITIAL_WEIGHT_NOISE))

        def t_noise(v: float) -> float:
            return _clamp_trait(v + rng.gauss(0.0, cfg.INITIAL_TRAIT_NOISE))

        w_hidden = [[w_noise(w) for w in row] for row in cfg.BRAIN_W_HIDDEN]
        b_hidden = [w_noise(b) for b in cfg.BRAIN_B_HIDDEN]
        w_out = [[w_noise(w) for w in row] for row in cfg.BRAIN_W_OUT]
        b_out = [w_noise(b) for b in cfg.BRAIN_B_OUT]
        traits = {k: t_noise(1.0) for k in TRAIT_KEYS}
        return Genome(w_hidden, b_hidden, w_out, b_out, traits)
