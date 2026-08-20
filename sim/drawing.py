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
    cfg.CELL_OBSTACLE: cfg.COLOR_CELL_OBSTACLE,
    cfg.CELL_RESOURCE: cfg.COLOR_CELL_RESOURCE,
}


def draw_world(screen: pygame.Surface, world) -> None:
    """Draw all non-empty cells on top of the floor background."""
    size = cfg.CELL_SIZE
    for y in range(world.rows):
        for x in range(world.cols):
            color = _CELL_COLORS.get(world.grid[y][x])
            if color is not None:
                pygame.draw.rect(screen, color, (x * size, y * size, size, size))


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


def draw_hud(screen: pygame.Surface, world) -> None:
    """Draw the time-of-day HUD; call last so the night overlay never dims it."""
    font = _get_font()
    total_min = int(round(world.hour * 60.0)) % (24 * 60)  # avoid "24:00"
    h, m = divmod(total_min, 60)
    text = f"Día {world.day}   {h:02d}:{m:02d}"
    x, y = cfg.HUD_MARGIN, cfg.HUD_MARGIN
    shadow, s_rect = font.render(text, (0, 0, 0))
    screen.blit(shadow, (x + s_rect.x + 1, y + s_rect.y + 1))
    label, l_rect = font.render(text, cfg.COLOR_HUD_TEXT)
    screen.blit(label, (x + l_rect.x, y + l_rect.y))
