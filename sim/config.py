"""Central place for all tunable settings.

Edit values here to change how the simulation looks and runs.
No other file should hard-code numbers that belong here.
"""

# --- Window ---
WINDOW_WIDTH = 800
WINDOW_HEIGHT = 600
WINDOW_TITLE = "GEVS IA — Intelligent Societies"

# --- Loop ---
FPS = 60

# --- Grid and world ---
CELL_SIZE = 20                 # px per cell (invariant: GRID_COLS * CELL_SIZE == WINDOW_WIDTH)
GRID_COLS = 40                 # invariant: GRID_COLS * CELL_SIZE == WINDOW_WIDTH
GRID_ROWS = 30                 # invariant: GRID_ROWS * CELL_SIZE == WINDOW_HEIGHT
WORLD_SEED = 42                # fixed seed -> reproducible world

# --- Cell types (ints) ---
CELL_EMPTY = 0
CELL_OBSTACLE = 1
CELL_RESOURCE = 2

# --- Procedural generation (densities 0.0-1.0) ---
OBSTACLE_DENSITY = 0.12
RESOURCE_DENSITY = 0.04

# --- Environment colors (RGB) ---
COLOR_FLOOR_DAY = (52, 62, 82)       # floor (empty cell) in full daylight
COLOR_FLOOR_NIGHT = (24, 28, 38)     # floor at full night
COLOR_CELL_OBSTACLE = (116, 106, 96) # rock / wall
COLOR_CELL_RESOURCE = (48, 148, 96)  # food (green)

# --- Day/night cycle (simulated hours) ---
DAY_LENGTH_S = 60.0          # real seconds per simulated day (1 h = 2.5 real s)
DAWN_START = 6.0             # dawn begins: light starts coming back
DAWN_END = 8.0               # full daylight
DUSK_START = 18.0            # dusk begins: light starts fading
DUSK_END = 21.0              # full night (invariant: DAWN_START < DAWN_END < DUSK_START < DUSK_END)
NIGHT_OVERLAY_COLOR = (8, 10, 28)
NIGHT_OVERLAY_ALPHA = 130    # max overlay alpha (0-255)
MAX_DT = 0.25                # cap delta time per frame (s)

# --- HUD ---
HUD_FONT_SIZE = 16
HUD_MARGIN = 10
COLOR_HUD_TEXT = (235, 238, 245)
