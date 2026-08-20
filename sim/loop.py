"""Main game loop: events, update, draw."""

import pygame

from sim import config
from sim.drawing import (
    draw_agents,
    draw_background,
    draw_hud,
    draw_night_overlay,
    draw_world,
)
from sim.world import World


def run(screen: pygame.Surface) -> None:
    """Run the loop until the user closes the window."""
    clock = pygame.time.Clock()
    world = World()
    running = True

    while running:
        # Delta time in seconds since the last frame (capped to avoid
        # big time jumps after dragging the window or alt-tabbing).
        dt = min(clock.tick(config.FPS) / 1000.0, config.MAX_DT)

        # 1. Handle events (keyboard, mouse, window close)
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

        # 2. Update the world (clock, food regrowth), then each agent
        #    (brain + body). Deferred deaths/births materialize in
        #    end_frame, never while the loop is iterating entities.
        world.update(dt)
        for agent in world.entities:
            agent.update(dt)
        world.end_frame()

        # 3. Draw everything (HUD last so the night overlay never dims it).
        #    Agents sit between the world and the night overlay: at night the
        #    overlay dims them along with everything else (they are asleep).
        draw_background(screen, world)
        draw_world(screen, world)
        draw_agents(screen, world)
        draw_night_overlay(screen, world)
        draw_hud(screen, world)
        pygame.display.flip()

    pygame.quit()
