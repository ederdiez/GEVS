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
    eligibility trace per output weight (a running average of the
    pre-activation times the unit's deviation from its own baseline,
    decaying with a time constant in *seconds*). learn(reward) nudges the
    weights along that trace — no backprop, no gradients. This mutates the
    Brain's own weight tables, which are always a private copy (see
    __init__): learning never reaches back into the Genome that built this
    Brain, so it is never inherited. Only cfg.LEARNABLE_OUTPUTS change;
    everything else is instinct that evolution alone reshapes.
    """

    def __init__(self, w_hidden, b_hidden, w_out, b_out):
        # np.asarray on a list copies by default: a Brain owns independent
        # tables so learn() can mutate them without ever touching the
        # Genome's (or another Brain's) data.
        self.w_hidden = np.asarray(w_hidden, dtype=np.float64)
        self.b_hidden = np.asarray(b_hidden, dtype=np.float64)
        self.w_out = np.asarray(w_out, dtype=np.float64)
        self.b_out = np.asarray(b_out, dtype=np.float64)

        # Traces exist for the output layer only: the hidden layer never
        # learns in-life (see learn()), so a hidden trace would be work the
        # hot path does every tick and nothing ever reads.
        self._elig_w_out = np.zeros_like(self.w_out)
        self._elig_b_out = np.zeros_like(self.b_out)

        # Running baseline: what each output usually does. The trace credits
        # the DEVIATION from this, not the raw activation (see
        # _update_eligibility). None until the first forward() seeds it with
        # the actual activations, so a brain does not spend its first
        # seconds unlearning an arbitrary starting guess.
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
        self._update_eligibility(outputs, layer_in, dt)
        self._last_hidden = hidden
        self._last_outputs = outputs
        return outputs.tolist()

    def _update_eligibility(self, outputs, layer_in, dt) -> None:
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
        if self._avg_out is None:
            self._avg_out = outputs.copy()
        d_out = outputs - self._avg_out

        decay = math.exp(-dt / cfg.ELIGIBILITY_TAU_S)
        keep = 1.0 - decay
        self._elig_w_out = decay * self._elig_w_out + keep * np.outer(d_out, layer_in)
        self._elig_b_out = decay * self._elig_b_out + keep * d_out

        # The baseline moves on its own, slower clock: fast enough to follow
        # a real change of regime, slow enough that a burst still reads as a
        # deviation instead of instantly becoming "normal".
        b_decay = math.exp(-dt / cfg.BASELINE_TAU_S)
        b_keep = 1.0 - b_decay
        self._avg_out = b_decay * self._avg_out + b_keep * outputs

    def learn(self, reward: float) -> None:
        """Reward-modulated Hebbian update: w += LEARNING_RATE * reward * eligibility.

        reward == 0.0 is the common case (nothing happened this tick) and
        is a no-op. Positive reward reinforces the weights that recently
        contributed to the current activations; negative reward pushes
        them the other way. Clamped to the same bounds as genetic weights.

        Only the rows in cfg.LEARNABLE_OUTPUTS change, and the hidden layer
        never does — evolution shapes the senses, life shapes what you do
        with them. A single scalar reward cannot say which row earned it,
        so without this split the food reward rewrites circuits it knows
        nothing about: measured before it existed, learning wrote a `noise`
        weight into the `rest` row, whose inputs are otherwise constant, and
        an agent's sleep drive started flickering frame to frame right at
        its threshold — it stopped sleeping at night on a full stomach.
        The hand-tuned rows are instinct, and their margins (the 20x hunger
        weight on `eat`, the 8.0 night weight on `rest`) exist precisely to
        survive drift; letting a diffuse Hebbian signal erode them destroys
        the thing those margins protect. They still evolve — mutation
        reaches every weight — just not within one lifetime.

        cfg.LEARNABLE_CELLS adds finer-grained plasticity on top: individual
        (row, col) weights that learn in life even in a row that is
        otherwise instinct (move_x/move_y/attack for the animal_dir/close/
        danger columns) — the rest of that row stays untouched here.
        """
        if reward == 0.0:
            return
        lr = cfg.LEARNING_RATE
        for i in cfg.LEARNABLE_OUTPUTS:
            self.w_out[i] = _clamp(self.w_out[i] + lr * reward * self._elig_w_out[i])
            self.b_out[i] = _clamp(self.b_out[i] + lr * reward * self._elig_b_out[i])
        for row, col in cfg.LEARNABLE_CELLS:
            if row in cfg.LEARNABLE_OUTPUTS:
                continue  # already updated above, avoid double-applying
            self.w_out[row, col] = _clamp(
                self.w_out[row, col] + lr * reward * self._elig_w_out[row, col])
