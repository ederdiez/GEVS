"""Main game loop: events, update, draw."""

import pygame

from sim import config
from sim.drawing import draw_background


def run(screen: pygame.Surface) -> None:
    """Run the loop until the user closes the window."""
    clock = pygame.time.Clock()
    running = True

    while running:
        # 1. Handle events (keyboard, mouse, window close)
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

        # 2. Update the world (agents will be updated here later)

        # 3. Draw everything
        draw_background(screen)
        pygame.display.flip()

        # 4. Keep a steady frame rate
        clock.tick(config.FPS)

    pygame.quit()
