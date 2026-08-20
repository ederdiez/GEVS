"""Brain: a small multilayer perceptron, pure Python (no dependencies).

The MLP is the agent's brain: it receives 11 signals and emits 5
intentions (movement direction, eat, rest, grab). All weights live in
sim.config (hand-tuned, readable tables); this module only does the
forward pass. See config.py `# --- Brain ---` for the meaning of every
unit and every weight.

Each agent builds its own Brain from its Genome's weight tables
(sim.genetics). The brain is a stateless forward machine: forward()
only reads the tables it was given, so a table can be shared by several
brains without risk.
"""

import math


def _relu(v: float) -> float:
    return max(0.0, v)


def _sigmoid(v: float) -> float:
    return 1.0 / (1.0 + math.exp(-v))


class Brain:
    """One hidden layer (relu) + one output layer (sigmoid).

    The output layer also receives the raw inputs (skip connections),
    so a signal like "food direction" can drive movement directly.
    """

    def __init__(self, w_hidden, b_hidden, w_out, b_out):
        self.w_hidden = w_hidden
        self.b_hidden = b_hidden
        self.w_out = w_out
        self.b_out = b_out

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
        return outputs
