"""Creates the pygame window."""

import pygame

from sim import config


def create_window() -> pygame.Surface:
    """Set up pygame and return the main window surface."""
    pygame.init()
    screen = pygame.display.set_mode((config.WINDOW_WIDTH, config.WINDOW_HEIGHT))
    pygame.display.set_caption(config.WINDOW_TITLE)
    return screen
