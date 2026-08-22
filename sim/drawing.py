"""Drawing helpers.

Each function draws one thing onto a surface. Add new drawing
functions here as the simulation grows (agents, food, terrain...).
"""

import pygame

from sim import config as cfg


def lerp_color(c1: tuple, c2: tuple, t: float) -> tuple:
    """Blend between two RGB colors; t is clamped to [0, 1]."""
    t = max(0.0, min(1.0, t))
    return tuple(min(255, max(0, round(a + (b - a) * t))) for a, b in zip(c1, c2))


def draw_background(screen: pygame.Surface, world) -> None:
    """Fill the screen with the floor color for the current time of day."""
    floor = lerp_color(cfg.COLOR_FLOOR_NIGHT, cfg.COLOR_FLOOR_DAY, world.daylight_factor)
    screen.fill(floor)


_CELL_COLORS = {
    cfg.CELL_RESOURCE: cfg.COLOR_CELL_RESOURCE,
    cfg.CELL_ROCK: cfg.COLOR_CELL_ROCK,
    cfg.CELL_WOOD: cfg.COLOR_CELL_WOOD,
    cfg.CELL_SPEAR: cfg.COLOR_CELL_SPEAR,
    cfg.CELL_MEAT: cfg.COLOR_CELL_MEAT,
}


def draw_world(screen: pygame.Surface, world, camera) -> None:
    """Draw non-empty cells visible in the camera's viewport."""
    size = camera.cell_px()
    x0, x1, y0, y1 = camera.visible_cell_range()
    for y in range(y0, y1):
        for x in range(x0, x1):
            color = _CELL_COLORS.get(world.grid[y][x])
            if color is not None:
                sx, sy = camera.to_screen(x, y)
                pygame.draw.rect(screen, color, (sx, sy, size + 1, size + 1))


_AGENT_STATE_COLORS = {
    "eating": cfg.COLOR_AGENT_EATING,
    "resting": cfg.COLOR_AGENT_RESTING,
    "active": cfg.COLOR_AGENT_WANDER,
}


def draw_agents(screen: pygame.Surface, world, camera, selected=None) -> None:
    """Draw every agent as a circle, colored by state.

    active agents turn orange when hungry (hunger >= HUNGER_WARNING);
    agents in the mating cooldown (recently mated, or newborn) show
    magenta over any other state — watch the reproduction live.
    An agent carrying a resource in its one-slot inventory (inventory
    is not None) shows a small dot above the head in the resource's
    cell color (food green, wood brown); an agent mid-way through
    crafting a spear also shows a row of progress pips, and an agent
    with a finished spear shows a stick beside it instead of a dot.

    `selected`, if given, gets a highlighted ring (inspector selection).
    """
    r = cfg.AGENT_RADIUS * camera.zoom
    x0, x1, y0, y1 = camera.visible_cell_range()
    for agent in world.entities:
        # Skip agents outside the viewport (+1 cell margin for the radius/dot/ring).
        if not (x0 - 1 <= agent.x <= x1 + 1 and y0 - 1 <= agent.y <= y1 + 1):
            continue
        # Agent.x is in cell units, always inside [cx, cx + 1): the claimed
        # cell. Cell-center-to-pixel is just x * CELL_SIZE; the old
        # `+ CELL_SIZE // 2` shifted every agent one cell down-right.
        px, py = camera.to_screen(agent.x, agent.y)
        pygame.draw.circle(screen, cfg.COLOR_AGENT_OUTLINE, (px, py), r + 2)
        if agent._mate_cooldown > 0.0:
            color = cfg.COLOR_AGENT_MATING
        elif agent.state == "active" and agent.hunger >= cfg.HUNGER_WARNING:
            color = cfg.COLOR_AGENT_HUNGRY
        else:
            color = _AGENT_STATE_COLORS[agent.state]
        pygame.draw.circle(screen, color, (px, py), r)
        # Carried resource: small dot above the head, colored by cell type.
        # A finished spear gets its own stick icon instead; wood mid-craft
        # gets a row of progress pips above the dot.
        if agent.inventory == cfg.CELL_SPEAR:
            sx = px + r + 6
            pygame.draw.line(screen, cfg.COLOR_CELL_SPEAR,
                              (sx, py - r - 2), (sx, py + r + 2), 3)
        elif agent.inventory == cfg.CELL_WOOD and agent._wood_craft_progress > 0:
            for i in range(agent._wood_craft_progress):
                pygame.draw.circle(screen, cfg.COLOR_CELL_WOOD,
                                    (px - 6 + i * 3, py - r - 12), 2)
            dot = (px, py - r - 5)
            pygame.draw.circle(screen, cfg.COLOR_AGENT_OUTLINE, dot, 4)
            pygame.draw.circle(screen, cfg.COLOR_CELL_WOOD, dot, 3)
        elif agent.inventory is not None:
            dot = (px, py - r - 5)
            pygame.draw.circle(screen, cfg.COLOR_AGENT_OUTLINE, dot, 4)
            pygame.draw.circle(screen, _CELL_COLORS.get(agent.inventory,
                                                        cfg.COLOR_CELL_RESOURCE), dot, 3)
        if agent is selected:
            pygame.draw.circle(screen, cfg.COLOR_SELECTED_OUTLINE, (px, py), r + 4, 2)


def draw_animals(screen: pygame.Surface, world, camera) -> None:
    """Draw every animal as a square — distinct at a glance from the
    agents' circles."""
    r = cfg.ANIMAL_RADIUS * camera.zoom
    x0, x1, y0, y1 = camera.visible_cell_range()
    for animal in world.animals:
        if not (x0 - 1 <= animal.x <= x1 + 1 and y0 - 1 <= animal.y <= y1 + 1):
            continue
        px, py = camera.to_screen(animal.x, animal.y)
        rect = pygame.Rect(px - r, py - r, r * 2, r * 2)
        pygame.draw.rect(screen, cfg.COLOR_AGENT_OUTLINE, rect.inflate(4, 4))
        pygame.draw.rect(screen, cfg.COLOR_ANIMAL, rect)


_night_surf = None


def draw_night_overlay(screen: pygame.Surface, world) -> None:
    """Darken the world at night with a translucent blue surface."""
    global _night_surf
    alpha = int(round(cfg.NIGHT_OVERLAY_ALPHA * (1.0 - world.daylight_factor)))
    if alpha <= 0:
        return  # full daylight: not even a blit
    if _night_surf is None:
        _night_surf = pygame.Surface((cfg.WINDOW_WIDTH, cfg.WINDOW_HEIGHT))
        _night_surf.fill(cfg.NIGHT_OVERLAY_COLOR)
    _night_surf.set_alpha(alpha)
    screen.blit(_night_surf, (0, 0))


_font = None


def _get_font():
    """HUD font built directly on pygame._freetype.

    pygame.font is unusable in the pygame 2.6.1 wheel for Python 3.14:
    its C extension (font.so) was not shipped in that wheel, and the
    pure-Python fallback dies on a circular import between font.py and
    sysfont.py. pygame._freetype (the engine behind it) works, so the
    HUD uses it directly. Same built-in font, no assets.
    """
    global _font
    if _font is None:
        if not pygame._freetype.get_init():
            pygame._freetype.init()
        _font = pygame._freetype.Font(None, cfg.HUD_FONT_SIZE)
        _font.origin = True  # size the surface to the text, like pygame.font
        _font.pad = True
    return _font


_hud_line_cache = {}  # line index -> (text, shadow_surf, shadow_rect, label_surf, label_rect)


def draw_hud(screen: pygame.Surface, world, speed: int = 1) -> None:
    """Draw the time-of-day HUD, population and speed multiplier; call
    last so the night overlay never dims it."""
    font = _get_font()
    x, y = cfg.HUD_MARGIN, cfg.HUD_MARGIN
    # int() (not round()): at 23:59.5 round() -> 24:00 -> wraps to 00:00.
    total_min = int(world.hour * 60.0) % (24 * 60)  # avoid "24:00"
    h, m = divmod(total_min, 60)
    lines = [f"Día {world.day}   {h:02d}:{m:02d}",
             f"Población: {len(world.entities)}  "
             f"†{world.stats_deaths}  +{world.stats_births}"]
    if speed != 1:
        lines.append(f"Velocidad: x{speed}")
    for i, text in enumerate(lines):
        offset = i * 22
        cached = _hud_line_cache.get(i)
        # Most frames repeat the previous minute/population/speed, so this
        # skips re-rendering (font.render, twice per line) on those frames.
        if cached is None or cached[0] != text:
            shadow, s_rect = font.render(text, (0, 0, 0))
            label, l_rect = font.render(text, cfg.COLOR_HUD_TEXT)
            cached = (text, shadow, s_rect, label, l_rect)
            _hud_line_cache[i] = cached
        _, shadow, s_rect, label, l_rect = cached
        screen.blit(shadow, (x + s_rect.x + 1, y + offset + s_rect.y + 1))
        screen.blit(label, (x + l_rect.x, y + offset + l_rect.y))
