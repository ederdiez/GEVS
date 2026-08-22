"""Camera: pan + zoom over a world grid bigger than the window.

Pure math, no pygame. screen = (world_px - offset) * zoom, where world_px
is cell coordinates times CELL_SIZE. Panning and zooming clamp so the
viewport never shows past the grid edges.
"""

from sim import config as cfg


class Camera:
    def __init__(self):
        self.zoom = cfg.CAMERA_DEFAULT_ZOOM
        self.x = 0.0  # world-pixel offset of the viewport's top-left corner
        self.y = 0.0
        self._clamp()

    def to_screen(self, cell_x: float, cell_y: float) -> tuple:
        """Cell-space coords -> screen pixel coords."""
        return ((cell_x * cfg.CELL_SIZE - self.x) * self.zoom,
                (cell_y * cfg.CELL_SIZE - self.y) * self.zoom)

    def to_world(self, screen_x: float, screen_y: float) -> tuple:
        """Screen pixel coords -> cell-space coords."""
        return ((screen_x / self.zoom + self.x) / cfg.CELL_SIZE,
                (screen_y / self.zoom + self.y) / cfg.CELL_SIZE)

    def cell_px(self) -> float:
        """Size in screen pixels of one world cell at the current zoom."""
        return cfg.CELL_SIZE * self.zoom

    def visible_cell_range(self) -> tuple:
        """(x0, x1, y0, y1) cell indices visible in the viewport, clamped
        to the grid — used to skip drawing cells off-screen."""
        x0, y0 = self.to_world(0, 0)
        x1, y1 = self.to_world(cfg.WINDOW_WIDTH, cfg.WINDOW_HEIGHT)
        return (max(0, int(x0)), min(cfg.GRID_COLS, int(x1) + 1),
                max(0, int(y0)), min(cfg.GRID_ROWS, int(y1) + 1))

    def pan(self, dx_cells: float, dy_cells: float) -> None:
        self.x += dx_cells * cfg.CELL_SIZE
        self.y += dy_cells * cfg.CELL_SIZE
        self._clamp()

    def zoom_at(self, factor: float, screen_x: float, screen_y: float) -> None:
        """Zoom in/out by `factor`, keeping the world point under
        (screen_x, screen_y) fixed on screen."""
        wx, wy = self.to_world(screen_x, screen_y)
        self.zoom = max(cfg.CAMERA_ZOOM_MIN, min(cfg.CAMERA_ZOOM_MAX, self.zoom * factor))
        self.x = wx * cfg.CELL_SIZE - screen_x / self.zoom
        self.y = wy * cfg.CELL_SIZE - screen_y / self.zoom
        self._clamp()

    def _clamp(self) -> None:
        world_w = cfg.GRID_COLS * cfg.CELL_SIZE
        world_h = cfg.GRID_ROWS * cfg.CELL_SIZE
        view_w = cfg.WINDOW_WIDTH / self.zoom
        view_h = cfg.WINDOW_HEIGHT / self.zoom
        self.x = (world_w - view_w) / 2 if view_w >= world_w else max(
            0.0, min(self.x, world_w - view_w))
        self.y = (world_h - view_h) / 2 if view_h >= world_h else max(
            0.0, min(self.y, world_h - view_h))
