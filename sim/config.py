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

# --- Agents ---
# Needs and body rates, calibrated for DAY_LENGTH_S = 60 real seconds per
# simulated day (a full hunger/energy cycle is visible in ~2 minutes).
AGENT_COUNT = 14           # agents spawned by the world
AGENT_SPEED = 6.0          # cells per second
AGENT_STEP_S = 0.1         # max movement sub-step (s); AGENT_SPEED * AGENT_STEP_S < 1 cell
AGENT_RADIUS = 7           # px, draw radius
HUNGER_RATE = 0.024        # hunger per second awake (0 -> 1 in ~42 s; eat ~once a day)
HUNGER_WARNING = 0.55      # >= this, agent looks hungry (color + eat drive)
HUNGER_CRITICAL = 0.85     # >= this, survival reflex: keep moving even at night
EAT_RATE = 0.45            # hunger lost per second while eating
EAT_DURATION_S = 2.0       # seconds it takes to eat one food cell
ENERGY_DRAIN_RATE = 0.017  # energy lost per second while awake (full -> sleepy in ~20 s: real mid-day naps)
ENERGY_REST_RATE = 0.035   # energy gained per second while resting
RESOURCE_REGROW_S = 45.0   # seconds until an eaten food cell regrows
FOOD_SENSE_RANGE = 8.0     # cells; beyond this the brain gets no food direction
AGENT_SENSE_RANGE = 2.0    # cells; "personal space" — nearest-agent sensors below this
BLOCKED_PROBE_S = 0.5      # s; while holding a blocked cell, re-probe it this often
REST_WAKE_ENERGY = 0.60    # resting agents stay down until energy >= this (nap latch)
DETOUR_S = 0.4             # s; slide around a rock/border before resuming (2.4 cells at AGENT_SPEED)

# Agent colors (drawing.py): state -> color
COLOR_AGENT_WANDER = (200, 200, 210)   # active, not hungry
COLOR_AGENT_HUNGRY = (232, 152, 64)    # active, hunger >= HUNGER_WARNING
COLOR_AGENT_EATING = (72, 190, 120)    # eating (green, like the food)
COLOR_AGENT_RESTING = (92, 132, 226)   # resting / sleeping (blue)
COLOR_AGENT_OUTLINE = (30, 32, 40)     # dark outline on every agent

# --- Brain (neural network) ---
# MLP: 10 inputs -> 5 hidden relu units -> 4 sigmoid outputs. Pure Python,
# weights hand-tuned below so behavior is sensible. The brain proposes
# intentions; the agent's body (agent.py) enforces what is inviolable.
#
# Inputs, in this exact order (agent.py `_inputs` builds them):
#   0 hunger         need (0-1)
#   1 energy         need (0-1)
#   2 night          1 - daylight_factor (0 = day, 1 = night)
#   3 food_dir_x     (dx + 1) / 2 toward nearest food cell; 0.5 if none in range
#   4 food_dir_y     same, Y axis
#   5 food_close     1 - min(dist / FOOD_SENSE_RANGE, 1); 0 if none in range
#   6 noise          world.rng.random() per frame (wandering; seeded, deterministic)
#   7 other_dir_x    (dx + 1) / 2 toward nearest other agent; 0.5 if none in range
#   8 other_dir_y    same, Y axis
#   9 other_close    1 - min(dist / AGENT_SENSE_RANGE, 1); 0 if none in range

# Hidden layer: 5 readable detectors (relu). One row per unit; columns are
# the first 7 inputs (0-6: needs, night, food direction, food_close, noise).
# The output layer sees all 10 inputs via skip connections (see below).
# Each unit is a condition detector:
#   h0 hungry     = relu(hunger - 0.55)   hunger above warning level
#   h1 starving   = relu(hunger - 0.85)   hunger above critical level
#   h2 sleepy     = relu(0.70 - energy)   energy below 0.70
#   h3 night      = relu(night - 0.50)    it is dark
#   h4 food_ahead = relu(food_close - 0.20) food nearby
BRAIN_W_HIDDEN = [
    [1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],  # h0
    [1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],  # h1
    [0.0, -1.0, 0.0, 0.0, 0.0, 0.0, 0.0],  # h2
    [0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0],  # h3
    [0.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0],  # h4
]
BRAIN_B_HIDDEN = [-0.55, -0.85, 0.70, -0.50, -0.20]

# Output layer: 4 outputs (move_x, move_y, eat, rest). One row per output;
# columns are the 5 hidden activations followed by the 10 raw inputs
# (skip connections, so food direction reaches movement directly).
#   move_x, move_y:  direction, 2 * output - 1 in [-1, 1]. Seek food
#                    (weight on food_dir) blended with noise (wandering).
#                    Avoidance: negative weight (-3.0) on the other_dir
#                    sensor pushes away from the nearest agent — it only
#                    engages when someone is within AGENT_SENSE_RANGE.
#   eat:             desire to eat; body acts only when > EAT_OUTPUT_THRESHOLD
#                    and the agent stands on a food cell. Weight on the
#                    hungry/starving detectors so it fires as hunger peaks,
#                    plus food_ahead (h4) so standing on food seals the call.
#   rest:            desire to rest; body stops moving when > REST_OUTPUT_THRESHOLD.
#                    Weight on night (sleep at night) + sleepy (h2 weight 8.0:
#                    naps once energy < ~0.65). The body's latch
#                    (REST_WAKE_ENERGY) makes naps real instead of a one-frame
#                    flicker at the threshold.
#   other_close (col 14): 0 everywhere, RESERVED for future training — a
#                    linear output cannot multiply closeness x direction, so
#                    distance modulation would need a hidden detector.
BRAIN_W_OUT = [
    #      h0  h1  h2  h3  h4  | hunger energy night dir_x dir_y close noise oth_x oth_y oth_close
    [0.0, 0.0, 0.0, 0.0, 0.0,  0.0, 0.0, 0.0, 2.4, 0.0, 0.0, 1.6,  -3.0, 0.0, 0.0],  # move_x
    [0.0, 0.0, 0.0, 0.0, 0.0,  0.0, 0.0, 0.0, 0.0, 2.4, 0.0, 1.6,  0.0, -3.0, 0.0],  # move_y
    [8.0, 10.0, 0.0, 0.0, 1.0,  0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0,  0.0, 0.0, 0.0],  # eat
    [0.0, 0.0, 8.0, 4.0, 0.0,  0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0,  0.0, 0.0, 0.0],  # rest
]
# Movement biases: -0.5 (was -2.0). A neutral other_dir (0.5, no neighbor)
# contributes -3.0 * 0.5 = -1.5 to each move pre-activation, exactly the
# amount the bias was lowered, so the solo wander envelope is unchanged.
BRAIN_B_OUT = [-0.5, -0.5, -1.0, -1.0]

# Output thresholds: above these, the body acts on the intention.
EAT_OUTPUT_THRESHOLD = 0.5
REST_OUTPUT_THRESHOLD = 0.6
