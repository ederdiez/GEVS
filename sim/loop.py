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
from sim.inspector import create_inspector_window, draw_inspector
from sim.world import World


def _pick_agent(world, px: int, py: int):
    """Nearest living agent to pixel (px, py), within click radius; or None."""
    wx, wy = px / config.CELL_SIZE, py / config.CELL_SIZE
    best, best_dist = None, config.INSPECTOR_CLICK_RADIUS
    for agent in world.entities:
        dist = ((agent.x - wx) ** 2 + (agent.y - wy) ** 2) ** 0.5
        if dist <= best_dist:
            best, best_dist = agent, dist
    return best


def run(screen: pygame.Surface) -> None:
    """Run the loop until the user closes the window."""
    clock = pygame.time.Clock()
    world = World()
    running = True
    selected_agent = None
    inspector = create_inspector_window()

    while running:
        # Delta time in seconds since the last frame (capped to avoid
        # big time jumps after dragging the window or alt-tabbing).
        dt = min(clock.tick(config.FPS) / 1000.0, config.MAX_DT)

        # 1. Handle events (keyboard, mouse, window close)
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif (event.type == pygame.MOUSEBUTTONDOWN and event.button == 1
                    and getattr(event, "window", None) is None):
                # Left click in the main window only (inspector has no
                # clickable content; `window` is None for the primary display).
                selected_agent = _pick_agent(world, *event.pos)
            elif event.type in (pygame.WINDOWRESIZED, pygame.WINDOWSIZECHANGED):
                event_window = getattr(event, "window", None)
                if event_window is inspector.window or getattr(
                        event_window, "id", None) == inspector.window.id:
                    inspector.resize(event.x, event.y)

        # 2. Update the world (clock, food regrowth), then each agent
        #    (brain + body). Deferred deaths/births materialize in
        #    end_frame, never while the loop is iterating entities.
        world.update(dt)
        for agent in world.entities:
            agent.update(dt)
        world.end_frame()

        if selected_agent is not None and not selected_agent.alive:
            selected_agent = None

        # 3. Draw everything (HUD last so the night overlay never dims it).
        #    Agents sit between the world and the night overlay: at night the
        #    overlay dims them along with everything else (they are asleep).
        draw_background(screen, world)
        draw_world(screen, world)
        draw_agents(screen, world, selected=selected_agent)
        draw_night_overlay(screen, world)
        draw_hud(screen, world)
        pygame.display.flip()

        draw_inspector(inspector.surface, selected_agent)
        inspector.flip()

    inspector.destroy()
    pygame.quit()
