"""Brain: a small multilayer perceptron, pure Python (no dependencies).

The MLP is the agent's brain: it receives 11 signals and emits 7
intentions (movement direction, eat, rest, grab, interact, drop). All weights live in
sim.config (hand-tuned, readable tables); this module only does the
forward pass. See config.py `# --- Brain ---` for the meaning of every
unit and every weight.

Each agent builds its own Brain from its Genome's weight tables
(sim.genetics); the Brain deep-copies them, so it owns independent
weights from birth. forward() also updates a reward-modulated Hebbian
eligibility trace, and learn(reward) uses that trace to nudge the
Brain's own weights — this is the agent's *personal* learning, kept
apart from the Genome, which is the only thing crossover/mutation ever
touch. See config.py `# --- Reinforcement learning ---`.
"""

import math

from sim import config as cfg


def _relu(v: float) -> float:
    return max(0.0, v)


def _sigmoid(v: float) -> float:
    return 1.0 / (1.0 + math.exp(-v))


def _clamp(w: float) -> float:
    return max(-cfg.WEIGHT_CLAMP, min(cfg.WEIGHT_CLAMP, w))


class Brain:
    """One hidden layer (relu) + one output layer (sigmoid).

    The output layer also receives the raw inputs (skip connections),
    so a signal like "food direction" can drive movement directly.

    Personal learning: forward() also keeps a reward-modulated Hebbian
    eligibility trace per weight (pre*post activation, decayed each
    tick). learn(reward) nudges the weights along that trace — no
    backprop, no gradients. This mutates the Brain's own weight tables,
    which are always a private copy (see __init__): learning never
    reaches back into the Genome that built this Brain, so it is never
    inherited.
    """

    def __init__(self, w_hidden, b_hidden, w_out, b_out):
        # Deep-copy: a Brain owns independent tables so learn() can mutate
        # them without ever touching the Genome's (or another Brain's) data.
        self.w_hidden = [list(row) for row in w_hidden]
        self.b_hidden = list(b_hidden)
        self.w_out = [list(row) for row in w_out]
        self.b_out = list(b_out)

        self._elig_w_hidden = [[0.0] * len(row) for row in self.w_hidden]
        self._elig_b_hidden = [0.0] * len(self.b_hidden)
        self._elig_w_out = [[0.0] * len(row) for row in self.w_out]
        self._elig_b_out = [0.0] * len(self.b_out)

    def forward(self, inputs) -> list:
        """inputs: list of floats, one per brain input (see config)."""
        hidden = [
            _relu(b + sum(w * x for w, x in zip(row, inputs)))
            for row, b in zip(self.w_hidden, self.b_hidden)
        ]
        # Output layer input: hidden activations + raw inputs (skip connections).
        layer_in = hidden + list(inputs)
        outputs = [
            _sigmoid(b + sum(w * x for w, x in zip(row, layer_in)))
            for row, b in zip(self.w_out, self.b_out)
        ]
        self._update_eligibility(inputs, hidden, outputs, layer_in)
        return outputs

    def _update_eligibility(self, inputs, hidden, outputs, layer_in) -> None:
        """Decay every trace, then add this tick's pre*post correlation.

        Only called from forward() (the hot path Agent.update drives) —
        forward_debug() must stay side-effect-free, or opening the
        inspector on an agent would speed up its learning.
        """
        decay = cfg.ELIGIBILITY_DECAY
        self._elig_w_hidden = [
            [decay * e + h * x for e, x in zip(erow, inputs)]
            for erow, h in zip(self._elig_w_hidden, hidden)
        ]
        self._elig_b_hidden = [decay * e + h for e, h in zip(self._elig_b_hidden, hidden)]
        self._elig_w_out = [
            [decay * e + o * x for e, x in zip(erow, layer_in)]
            for erow, o in zip(self._elig_w_out, outputs)
        ]
        self._elig_b_out = [decay * e + o for e, o in zip(self._elig_b_out, outputs)]

    def learn(self, reward: float) -> None:
        """Reward-modulated Hebbian update: w += LEARNING_RATE * reward * eligibility.

        reward == 0.0 is the common case (nothing happened this tick) and
        is a no-op. Positive reward reinforces the weights that recently
        contributed to the current activations; negative reward pushes
        them the other way. Clamped to the same bounds as genetic weights.
        """
        if reward == 0.0:
            return
        lr = cfg.LEARNING_RATE
        self.w_hidden = [
            [_clamp(w + lr * reward * e) for w, e in zip(row, erow)]
            for row, erow in zip(self.w_hidden, self._elig_w_hidden)
        ]
        self.b_hidden = [_clamp(b + lr * reward * e)
                          for b, e in zip(self.b_hidden, self._elig_b_hidden)]
        self.w_out = [
            [_clamp(w + lr * reward * e) for w, e in zip(row, erow)]
            for row, erow in zip(self.w_out, self._elig_w_out)
        ]
        self.b_out = [_clamp(b + lr * reward * e)
                       for b, e in zip(self.b_out, self._elig_b_out)]

    def forward_debug(self, inputs) -> tuple:
        """Like forward(), but also returns the hidden activations.

        For inspection only (sim.inspector): every agent's hot path keeps
        calling forward(), which stays untouched.
        """
        hidden = [
            _relu(b + sum(w * x for w, x in zip(row, inputs)))
            for row, b in zip(self.w_hidden, self.b_hidden)
        ]
        layer_in = hidden + list(inputs)
        outputs = [
            _sigmoid(b + sum(w * x for w, x in zip(row, layer_in)))
            for row, b in zip(self.w_out, self.b_out)
        ]
        return hidden, outputs
