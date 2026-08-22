"""Brain: a small multilayer perceptron, vectorized with numpy.

The MLP is the agent's brain: it receives 17 signals and emits 8
intentions (move_x, move_y, eat, rest, grab, interact, drop, attack). All weights
live in sim.config (hand-tuned, readable tables); this module only does
the forward pass. See config.py `# --- Brain ---` for the meaning of
every unit and every weight.

Each agent builds its own Brain from its Genome's weight tables
(sim.genetics, still plain Python lists — crossover/mutation are rare
events compared to forward()/learn(), so vectorizing them buys nothing);
the Brain converts them to numpy arrays it owns independently, so it can
learn() without ever touching the Genome or another Brain. forward() also
updates a reward-modulated Hebbian eligibility trace, and learn(reward)
uses that trace to nudge the Brain's own weights — this is the agent's
*personal* learning, kept apart from the Genome, which is the only thing
crossover/mutation ever touch. See config.py `# --- Reinforcement
learning ---`.
"""

import math

import numpy as np

from sim import config as cfg


def _clamp(w):
    return np.clip(w, -cfg.WEIGHT_CLAMP, cfg.WEIGHT_CLAMP)


class Brain:
    """One hidden layer (relu) + one output layer (sigmoid).

    The output layer also receives the raw inputs (skip connections),
    so a signal like "food direction" can drive movement directly.

    Personal learning: forward() also keeps a reward-modulated Hebbian
    eligibility trace per weight (a running average of the pre-activation
    times the unit's deviation from its own baseline, decaying with a time
    constant in *seconds*). learn(reward) nudges the weights along that
    trace — no backprop, no gradients. This mutates the Brain's own weight
    tables, which are always a private copy (see __init__): learning never
    reaches back into the Genome that built this Brain, so it is never
    inherited. Only cfg.LEARNABLE_OUTPUTS/LEARNABLE_CELLS (output layer)
    and cfg.LEARNABLE_HIDDEN (hidden layer, currently just the two
    "blank" exploratory units) change; everything else is instinct that
    evolution alone reshapes.
    """

    def __init__(self, w_hidden, b_hidden, w_out, b_out):
        # np.asarray on a list copies by default: a Brain owns independent
        # tables so learn() can mutate them without ever touching the
        # Genome's (or another Brain's) data.
        self.w_hidden = np.asarray(w_hidden, dtype=np.float64)
        self.b_hidden = np.asarray(b_hidden, dtype=np.float64)
        self.w_out = np.asarray(w_out, dtype=np.float64)
        self.b_out = np.asarray(b_out, dtype=np.float64)

        # Traces for both layers: most hidden rows never learn in-life (see
        # learn(), cfg.LEARNABLE_HIDDEN), but the trace itself is cheap
        # (hidden_size x input_size floats) next to the output trace, so it
        # is simplest to compute it uniformly and let learn() decide which
        # rows to apply.
        self._elig_w_hidden = np.zeros_like(self.w_hidden)
        self._elig_b_hidden = np.zeros_like(self.b_hidden)
        self._elig_w_out = np.zeros_like(self.w_out)
        self._elig_b_out = np.zeros_like(self.b_out)

        # Running baseline: what each unit usually does. The trace credits
        # the DEVIATION from this, not the raw activation (see
        # _update_eligibility). None until the first forward() seeds it with
        # the actual activations, so a brain does not spend its first
        # seconds unlearning an arbitrary starting guess.
        self._avg_hidden = None
        self._avg_out = None

        # Last forward() results, kept for the inspector (sim.inspector) so
        # it can read this tick's activations instead of recomputing them.
        self._last_hidden = None
        self._last_outputs = None

    def forward(self, inputs, dt: float) -> list:
        """inputs: list of floats, one per brain input (see config).

        dt (real seconds this tick) only drives the eligibility decay —
        the forward pass itself is stateless.
        """
        x = np.asarray(inputs, dtype=np.float64)
        hidden = np.maximum(0.0, self.w_hidden @ x + self.b_hidden)
        # Output layer input: hidden activations + raw inputs (skip connections).
        layer_in = np.concatenate((hidden, x))
        outputs = 1.0 / (1.0 + np.exp(-(self.w_out @ layer_in + self.b_out)))
        self._update_eligibility(hidden, x, outputs, layer_in, dt)
        self._last_hidden = hidden
        self._last_outputs = outputs
        return outputs.tolist()

    def _update_eligibility(self, hidden, x, outputs, layer_in, dt) -> None:
        """Blend this tick's pre*deviation correlation into every trace.

        Three properties, each fixing a specific way this rule goes wrong:

        - Exponential moving *average*, not a sum:
          `e = decay*e + (1-decay)*pre*post`. The old sum saturated at
          `pre*post / (1 - decay)` — 10x with the old per-tick 0.90, and it
          would have hit 120x with a tau long enough to credit a grab for a
          meal eaten seconds later, inflating the learning rate to match.
        - Decay per *second*, not per tick: `decay = exp(-dt / ELIGIBILITY_TAU_S)`.
          The old per-tick constant silently coupled the learning dynamics to
          FPS and to the speed multiplier (loop.py runs the step `speed`
          times per frame).
        - `post` is the unit's DEVIATION from its own running baseline, not
          its raw activation. This is the one that matters most. A raw
          activation is never negative, so every reward used to reinforce
          every active unit — including units with nothing to do with it,
          and biases worst of all, since their input is always 1. Measured
          on the first calibration run: the `drop` row, which no reward ever
          referred to, drifted from a 0.2% firing rate to 13% in four
          simulated minutes purely on this diffuse credit, agents spent
          their lives picking food up and putting it back down, and the
          population starved out. Crediting the deviation means a unit
          sitting at its usual value earns nothing, and only a unit that
          actually did something unusual — which, for the exploring rows, is
          exactly what the noise input causes — is held responsible.

        Only called from forward() (the hot path Agent.update drives) —
        opening the inspector on an agent must never call this a second
        time, or it would speed up that agent's learning (see
        sim.inspector, which reads Brain._last_hidden/_last_outputs
        instead of recomputing).
        """
        if self._avg_hidden is None:
            self._avg_hidden = hidden.copy()
        if self._avg_out is None:
            self._avg_out = outputs.copy()
        d_hidden = hidden - self._avg_hidden
        d_out = outputs - self._avg_out

        decay = math.exp(-dt / cfg.ELIGIBILITY_TAU_S)
        keep = 1.0 - decay
        self._elig_w_hidden = decay * self._elig_w_hidden + keep * np.outer(d_hidden, x)
        self._elig_b_hidden = decay * self._elig_b_hidden + keep * d_hidden
        self._elig_w_out = decay * self._elig_w_out + keep * np.outer(d_out, layer_in)
        self._elig_b_out = decay * self._elig_b_out + keep * d_out

        # The baseline moves on its own, slower clock: fast enough to follow
        # a real change of regime, slow enough that a burst still reads as a
        # deviation instead of instantly becoming "normal".
        b_decay = math.exp(-dt / cfg.BASELINE_TAU_S)
        b_keep = 1.0 - b_decay
        self._avg_hidden = b_decay * self._avg_hidden + b_keep * hidden
        self._avg_out = b_decay * self._avg_out + b_keep * outputs

    def learn(self, reward: float) -> None:
        """Reward-modulated Hebbian update: w += LEARNING_RATE * reward * eligibility.

        reward == 0.0 is the common case (nothing happened this tick) and
        is a no-op. Positive reward reinforces the weights that recently
        contributed to the current activations; negative reward pushes
        them the other way. Clamped to the same bounds as genetic weights.

        Only the rows in cfg.LEARNABLE_OUTPUTS change on the output side, and
        only cfg.LEARNABLE_HIDDEN rows change on the hidden side — the other
        6 hidden units and the other output rows are instinct: evolution
        shapes the senses, life shapes what you do with them. A single
        scalar reward cannot say which row earned it, so without this split
        the food reward rewrites circuits it knows nothing about: measured
        before it existed, learning wrote a `noise` weight into the `rest`
        row, whose inputs are otherwise constant, and an agent's sleep drive
        started flickering frame to frame right at its threshold — it
        stopped sleeping at night on a full stomach. The hand-tuned rows are
        instinct, and their margins (the 20x hunger weight on `eat`, the 8.0
        night weight on `rest`) exist precisely to survive drift; letting a
        diffuse Hebbian signal erode them destroys the thing those margins
        protect. They still evolve — mutation reaches every weight — just
        not within one lifetime.

        cfg.LEARNABLE_CELLS adds finer-grained plasticity on top: individual
        (row, col) weights that learn in life even in a row that is
        otherwise instinct (move_x/move_y/attack for the animal_dir/close/
        danger columns, and every output row for the two LEARNABLE_HIDDEN
        columns) — the rest of that row stays untouched here.
        """
        if reward == 0.0:
            return
        lr = cfg.LEARNING_RATE
        for i in cfg.LEARNABLE_HIDDEN:
            self.w_hidden[i] = _clamp(self.w_hidden[i] + lr * reward * self._elig_w_hidden[i])
            self.b_hidden[i] = _clamp(self.b_hidden[i] + lr * reward * self._elig_b_hidden[i])
        for i in cfg.LEARNABLE_OUTPUTS:
            self.w_out[i] = _clamp(self.w_out[i] + lr * reward * self._elig_w_out[i])
            self.b_out[i] = _clamp(self.b_out[i] + lr * reward * self._elig_b_out[i])
        for row, col in cfg.LEARNABLE_CELLS:
            if row in cfg.LEARNABLE_OUTPUTS:
                continue  # already updated above, avoid double-applying
            self.w_out[row, col] = _clamp(
                self.w_out[row, col] + lr * reward * self._elig_w_out[row, col])


if __name__ == "__main__":
    # Self-check: LEARNABLE_HIDDEN rows (and their LEARNABLE_CELLS output
    # columns) move under a nonzero reward; every other instinct weight
    # does not.
    import random

    rng = random.Random(0)
    b = Brain(cfg.BRAIN_W_HIDDEN, cfg.BRAIN_B_HIDDEN, cfg.BRAIN_W_OUT, cfg.BRAIN_B_OUT)
    # h6/h7 start at all-zero weight+bias (dead relu: constant 0, so no
    # input-dependent deviation to credit in life) — give them the small
    # input weight a first mutation would, to check the in-life mechanism
    # itself rather than the frozen-at-birth case, which is expected and
    # correct (see LEARNABLE_HIDDEN in config.py).
    for i in cfg.LEARNABLE_HIDDEN:
        b.w_hidden[i, 0] = 0.5
    w_hidden0 = b.w_hidden.copy()
    b_hidden0 = b.b_hidden.copy()
    w_out0 = b.w_out.copy()

    for _ in range(50):
        inputs = [rng.random() for _ in range(len(cfg.BRAIN_W_HIDDEN[0]))]
        b.forward(inputs, dt=0.1)
        b.learn(reward=1.0 if rng.random() < 0.5 else -1.0)

    instinct_hidden = [i for i in range(len(cfg.BRAIN_W_HIDDEN)) if i not in cfg.LEARNABLE_HIDDEN]
    assert np.array_equal(b.w_hidden[instinct_hidden], w_hidden0[instinct_hidden]), "instinct hidden rows moved"
    assert np.array_equal(b.b_hidden[instinct_hidden], b_hidden0[instinct_hidden]), "instinct hidden biases moved"
    for i in cfg.LEARNABLE_HIDDEN:
        assert not np.array_equal(b.w_hidden[i], w_hidden0[i]), f"LEARNABLE_HIDDEN row {i} did not move"

    learnable_out_cells = {(i, c) for i in cfg.LEARNABLE_OUTPUTS for c in range(b.w_out.shape[1])}
    learnable_out_cells |= set(cfg.LEARNABLE_CELLS)
    moved = b.w_out != w_out0
    for row in range(b.w_out.shape[0]):
        for col in range(b.w_out.shape[1]):
            if (row, col) not in learnable_out_cells:
                assert not moved[row, col], f"instinct output cell {(row, col)} moved"
    print("brain.py self-check OK")
