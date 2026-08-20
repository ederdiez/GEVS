"""Drawing helpers.

Each function draws one thing onto a surface. Add new drawing
functions here as the simulation grows (agents, food, terrain...).
"""

import pygame

from sim import config


def draw_background(screen: pygame.Surface) -> None:
    """Fill the whole screen with the background color."""
    screen.fill(config.COLOR_BACKGROUND)
