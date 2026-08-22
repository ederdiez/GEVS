"""Main game loop: events, update, draw."""

import pygame

from sim import config
from sim.camera import Camera
from sim.drawing import (
    draw_agents,
    draw_animals,
    draw_background,
    draw_hud,
    draw_night_overlay,
    draw_world,
)
from sim.inspector import create_inspector_window, draw_inspector
from sim.tick_log import TickLogger
from sim.world import World

_PAN_KEYS = {
    pygame.K_w: (0, -1), pygame.K_UP: (0, -1),
    pygame.K_s: (0, 1), pygame.K_DOWN: (0, 1),
    pygame.K_a: (-1, 0), pygame.K_LEFT: (-1, 0),
    pygame.K_d: (1, 0), pygame.K_RIGHT: (1, 0),
}


def _pick_agent(world, camera, px: int, py: int):
    """Nearest living agent to screen pixel (px, py), within click radius; or None."""
    wx, wy = camera.to_world(px, py)
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
    camera = Camera()
    tick_log = TickLogger()
    running = True
    selected_agent = None
    inspector = create_inspector_window()
    # The inspector's empty state ("click a creature") never changes frame
    # to frame, unlike a live selection (whose age/needs/outputs move every
    # tick) — draw it once, not every frame, until the selection changes.
    inspector_empty_drawn = False
    speed_index = 0  # index into config.SPEED_LEVELS; x1 by default

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
                selected_agent = _pick_agent(world, camera, *event.pos)
            elif (event.type == pygame.MOUSEWHEEL
                    and getattr(event, "window", None) is None):
                factor = config.CAMERA_ZOOM_STEP if event.y > 0 else 1 / config.CAMERA_ZOOM_STEP
                camera.zoom_at(factor, *pygame.mouse.get_pos())
            elif event.type in (pygame.WINDOWRESIZED, pygame.WINDOWSIZECHANGED):
                event_window = getattr(event, "window", None)
                if event_window is inspector.window or getattr(
                        event_window, "id", None) == inspector.window.id:
                    inspector.resize(event.x, event.y)
            elif event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_EQUALS, pygame.K_KP_PLUS):
                    speed_index = min(speed_index + 1, len(config.SPEED_LEVELS) - 1)
                elif event.key in (pygame.K_MINUS, pygame.K_KP_MINUS):
                    speed_index = max(speed_index - 1, 0)

        # Camera pan: continuous while a WASD/arrow key is held.
        keys = pygame.key.get_pressed()
        pan_x = sum(dx for key, (dx, _) in _PAN_KEYS.items() if keys[key])
        pan_y = sum(dy for key, (_, dy) in _PAN_KEYS.items() if keys[key])
        if pan_x or pan_y:
            camera.pan(pan_x * config.CAMERA_PAN_SPEED * dt,
                       pan_y * config.CAMERA_PAN_SPEED * dt)

        # 2. Update the world (clock, food regrowth), then each agent
        #    (brain + body), `speed` times per rendered frame so
        #    simulated time fast-forwards while drawing stays at the same
        #    FPS. Deferred deaths/births materialize in end_frame, never
        #    while the loop is iterating entities.
        speed = config.SPEED_LEVELS[speed_index]
        for _ in range(speed):
            world.update(dt)
            # Animals move/attack before agents, so an agent's reward this
            # same tick already reflects any damage just taken (agent.py).
            for animal in world.animals:
                animal.update(dt)
            for agent in world.entities:
                agent.update(dt)
            world.end_frame()
            tick_log.log(world, dt)

        if selected_agent is not None and not selected_agent.alive:
            selected_agent = None

        # 3. Draw everything (HUD last so the night overlay never dims it).
        #    Agents sit between the world and the night overlay: at night the
        #    overlay dims them along with everything else (they are asleep).
        draw_background(screen, world)
        draw_world(screen, world, camera)
        draw_agents(screen, world, camera, selected=selected_agent)
        draw_animals(screen, world, camera)
        draw_night_overlay(screen, world)
        draw_hud(screen, world, speed=speed)
        pygame.display.flip()

        if selected_agent is not None:
            draw_inspector(inspector.surface, selected_agent)
            inspector.flip()
            inspector_empty_drawn = False
        elif not inspector_empty_drawn:
            draw_inspector(inspector.surface, None)
            inspector.flip()
            inspector_empty_drawn = True

    tick_log.close()
    inspector.destroy()
    pygame.quit()
