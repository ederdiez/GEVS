"""Inspector window: live view of one selected agent's brain.

A second, independent OS window (pygame 2's SDL2 multi-window support)
that shows the selected agent's needs and its brain's inputs, hidden
activations and outputs, tick by tick. Selection happens in the main
window (sim.loop); this module only knows how to open its window and
draw into it.
"""

import pygame
from pygame._sdl2.video import Renderer, Texture, Window

from sim import config as cfg
from sim.drawing import lerp_color

INPUT_LABELS = [
    "hunger", "energy", "night", "food_dx", "food_dy",
    "food_close", "noise", "other_dx", "other_dy", "other_close", "has_food",
    "pos_x", "pos_y",
]
HIDDEN_LABELS = ["food_x", "food_y", "sleepy", "night", "food_ahead", "carrying"]
OUTPUT_LABELS = ["move_x", "move_y", "eat", "rest", "grab", "interact", "drop"]

_font = None


def _get_font():
    global _font
    if _font is None:
        if not pygame._freetype.get_init():
            pygame._freetype.init()
        _font = pygame._freetype.Font(None, 14)
        _font.origin = True
        _font.pad = True
    return _font


class InspectorWindow:
    """A real second OS window, drawn to via an offscreen Surface each
    frame (this SDL2 wheel's Window has no get_surface(), so the
    software surface is uploaded as a Texture and presented through a
    Renderer instead).
    """

    def __init__(self):
        self.window = Window(cfg.INSPECTOR_WINDOW_TITLE,
                              size=(cfg.INSPECTOR_WINDOW_WIDTH, cfg.INSPECTOR_WINDOW_HEIGHT),
                              resizable=True)
        self.renderer = Renderer(self.window)
        self.surface = pygame.Surface(
            (cfg.INSPECTOR_WINDOW_WIDTH, cfg.INSPECTOR_WINDOW_HEIGHT))

    def resize(self, width: int, height: int) -> None:
        """Match the offscreen surface to the window's new size (called on
        WINDOWRESIZED). Drawing code reads the surface's own size each
        frame (see draw_inspector), so nothing else needs to know."""
        width = max(1, width)
        height = max(1, height)
        if (width, height) != self.surface.get_size():
            self.surface = pygame.Surface((width, height))

    def flip(self) -> None:
        texture = Texture.from_surface(self.renderer, self.surface)
        self.renderer.clear()
        texture.draw()
        self.renderer.present()

    def destroy(self) -> None:
        self.window.destroy()


def create_inspector_window() -> InspectorWindow:
    """Open the inspector window."""
    return InspectorWindow()


def _draw_text(surface, text, pos, color=cfg.COLOR_INSPECTOR_TEXT):
    font = _get_font()
    label, rect = font.render(text, color)
    surface.blit(label, (pos[0] + rect.x, pos[1] + rect.y))
    return rect.height


def _draw_bar(surface, x, y, w, h, value, color, label):
    pygame.draw.rect(surface, cfg.COLOR_NODE_LOW, (x, y, w, h))
    fill_w = int(w * max(0.0, min(1.0, value)))
    pygame.draw.rect(surface, color, (x, y, fill_w, h))
    pygame.draw.rect(surface, cfg.COLOR_NODE_OUTLINE, (x, y, w, h), 1)
    _draw_text(surface, f"{label}: {value:.2f}", (x, y + h + 2))


def _node_color(value):
    return lerp_color(cfg.COLOR_NODE_LOW, cfg.COLOR_NODE_HIGH, value)


def _draw_network(surface, top, height, inputs, hidden, outputs):
    """Three columns of nodes (inputs / hidden / outputs), connected by
    lines, colored by activation value."""
    width = surface.get_width()
    cols = [
        (list(zip(INPUT_LABELS, inputs)), width * 0.18),
        (list(zip(HIDDEN_LABELS, hidden)), width * 0.52),
        (list(zip(OUTPUT_LABELS, outputs)), width * 0.86),
    ]
    radius = 7
    positions = []  # per column: list of (x, y)
    for nodes, cx in cols:
        n = len(nodes)
        gap = height / (n + 1)
        col_positions = [(cx, top + gap * (i + 1)) for i in range(n)]
        positions.append(col_positions)

    # Edges: every node in a column connects to every node in the next.
    for col_a, col_b in zip(positions[:-1], positions[1:]):
        for pa in col_a:
            for pb in col_b:
                pygame.draw.line(surface, cfg.COLOR_EDGE, pa, pb, 1)

    for (nodes, _), col_positions in zip(cols, positions):
        for (label, value), (x, y) in zip(nodes, col_positions):
            pygame.draw.circle(surface, _node_color(value), (int(x), int(y)), radius)
            pygame.draw.circle(surface, cfg.COLOR_NODE_OUTLINE, (int(x), int(y)), radius, 1)
            text = f"{label} {value:.2f}"
            font = _get_font()
            label_surf, rect = font.render(text, cfg.COLOR_INSPECTOR_TEXT)
            # Inputs left of their node, outputs right, hidden centered above.
            if x < width * 0.35:
                pos = (x - radius - rect.width - 4, y - rect.height / 2)
            elif x > width * 0.65:
                pos = (x + radius + 4, y - rect.height / 2)
            else:
                pos = (x - rect.width / 2, y - radius - rect.height - 2)
            surface.blit(label_surf, (pos[0] + rect.x, pos[1] + rect.y))


def draw_inspector(surface, agent) -> None:
    """Draw the full inspector panel for `agent` (or an empty state)."""
    surface.fill(cfg.COLOR_INSPECTOR_BG)

    if agent is None or not agent.alive:
        _draw_text(surface, "Click a creature to inspect it",
                   (12, 12), cfg.COLOR_INSPECTOR_MUTED)
        return

    x = 12
    y = 10
    y += _draw_text(surface, f"Gen {agent.generation}  age {agent.age_s:5.1f}s  "
                              f"[{agent.state}]", (x, y)) + 6

    _draw_bar(surface, x, y, 160, 12, agent.hunger, cfg.COLOR_AGENT_HUNGRY, "hunger")
    _draw_bar(surface, x + 190, y, 160, 12, agent.energy, cfg.COLOR_AGENT_RESTING, "energy")
    y += 34

    inputs = agent._inputs()
    hidden, outputs = agent.brain.forward_debug(inputs)

    net_top = y + 10
    net_height = surface.get_height() - net_top - 90
    _draw_network(surface, net_top, net_height, inputs, hidden, outputs)

    # Raw output values + thresholds, spelled out below the diagram.
    y2 = surface.get_height() - 82
    move_x, move_y, eat_out, rest_out, grab_out, interact_out, drop_out = outputs
    lines = [
        f"eat  {eat_out:.2f}  (> {cfg.EAT_OUTPUT_THRESHOLD:.2f} to eat)",
        f"rest {rest_out:.2f}  (> {cfg.REST_OUTPUT_THRESHOLD:.2f} to rest)",
        f"grab {grab_out:.2f}  (> {cfg.GRAB_OUTPUT_THRESHOLD:.2f} to grab)",
        f"interact {interact_out:.2f}  (> {cfg.INTERACT_OUTPUT_THRESHOLD:.2f} to interact)",
        f"drop {drop_out:.2f}  (> {cfg.DROP_OUTPUT_THRESHOLD:.2f} to drop)",
    ]
    for line in lines:
        y2 += _draw_text(surface, line, (x, y2), cfg.COLOR_INSPECTOR_MUTED) + 2
