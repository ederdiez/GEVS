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
CELL_RESOURCE = 2             # food (green)
CELL_ROCK = 3                 # rock: collidable (future functionality pending)
CELL_WOOD = 4                 # wood: collidable (future functionality pending)

# --- Procedural generation (densities 0.0-1.0) ---
ROCK_DENSITY = 0.08
WOOD_DENSITY = 0.04
RESOURCE_DENSITY = 0.04

# --- Environment colors (RGB) ---
COLOR_FLOOR_DAY = (52, 62, 82)       # floor (empty cell) in full daylight
COLOR_FLOOR_NIGHT = (24, 28, 38)     # floor at full night
COLOR_CELL_ROCK = (116, 106, 96)     # rock (gray-brown)
COLOR_CELL_WOOD = (139, 101, 54)     # wood (brown)
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
ENERGY_DRAIN_RATE = 0.013  # energy lost per second while awake (full -> sleepy in ~20 s: real mid-day naps)
ENERGY_REST_RATE = 0.045   # energy gained per second while resting
RESOURCE_REGROW_S = 40.0   # seconds until an eaten food cell regrows
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
COLOR_AGENT_MATING = (214, 94, 194)    # magenta: in the mate cooldown (recently mated / newborn)
COLOR_AGENT_OUTLINE = (30, 32, 40)     # dark outline on every agent

# --- Brain (neural network) ---
# MLP: 11 inputs -> 6 hidden relu units -> 5 sigmoid outputs. Pure Python,
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
#   10 has_food      1.0 if the one-slot inventory is full (carrying a
#                    resource), 0.0 if empty

# Hidden layer: 6 readable detectors (relu). One row per unit; columns are
# inputs 0-6 and 10 (needs, night, food direction, food_close, noise,
# has_food). The output layer sees all 11 inputs via skip connections
# (see below). Each unit is a condition detector:
#   h0 food_x     = relu(2*hunger + food_dir_x - 2)  hunger-gated food on X
#   h1 food_y     = relu(2*hunger + food_dir_y - 2)  hunger-gated food on Y
#   h2 sleepy     = relu(0.70 - energy)   energy below 0.70
#   h3 night      = relu(night - 0.50)    it is dark
#   h4 food_ahead = relu(food_close - 0.20) food nearby
#   h5 carrying   = relu(has_food - 0.50) inventory full (carrying a resource)
#
# h0/h1 are the food-direction gates: relu(2*hunger + food_dir - 2) fires
# only when hunger is high enough AND food lies in that half-plane, so a
# satiated agent gets no food pull at all and wanders on noise alone
# ("curiosity"), while a hungry one pursues with a pull that grades with
# hunger: 0 below hunger ~0.5, ~0.4 at 0.7, 1.0 at hunger 1.0 with food
# directly ahead. Food behind (food_dir < 2 - 2*hunger) never fires, so
# pursuit never pushes the wrong way.
BRAIN_W_HIDDEN = [
    [2.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0],  # h0
    [2.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0],  # h1
    [0.0, -1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],  # h2
    [0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0],  # h3
    [0.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0],  # h4
    [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0],  # h5
]
BRAIN_B_HIDDEN = [-2.0, -2.0, 0.70, -0.50, -0.20, -0.50]

# Output layer: 5 outputs (move_x, move_y, eat, rest, grab). One row per output;
# columns are the 6 hidden activations followed by the 11 raw inputs
# (skip connections: the raw inputs also reach the outputs directly).
#   move_x, move_y:  direction, 2 * output - 1 in [-1, 1]. Food seeking is
#                    hunger-gated: the food direction arrives through the
#                    h0/h1 gates (see above), so a satiated agent has no
#                    food pull and wanders on noise alone, while a hungry
#                    one pursues the nearest food with a pull that grades
#                    with hunger (up to 2.4 at hunger 1.0). Avoidance:
#                    negative weight (-3.0) on the other_dir sensor pushes
#                    away from the nearest agent — it only engages when
#                    someone is within AGENT_SENSE_RANGE.
#   eat:             desire to eat; body acts only when > EAT_OUTPUT_THRESHOLD
#                    and the agent stands on a food cell. Hunger reaches the
#                    row directly (skip weight 20.0); paired with the bias
#                    -10.5 it replays the old "hungry" detector in the
#                    output layer: 20 * hunger - 10.5 crosses 0 (sigmoid
#                    0.5) at hunger ~0.53, just below HUNGER_WARNING. The
#                    food_ahead detector (h4, weight 1.0) seals the call on
#                    a food cell: it adds +0.8 pre-activation there, easing
#                    the threshold to ~0.48 when standing on food. The 20x
#                    weight also widens the drift margin: a mutation of
#                    ±0.2 on the weight shifts the threshold by ±0.01 of
#                    hunger.
#   rest:            desire to rest; body stops moving when > REST_OUTPUT_THRESHOLD.
#                    Weight on night (sleep at night) + sleepy (h2 weight 8.0:
#                    naps once energy < ~0.65). The h3 weight is 8.0 (not 4.0)
#                    to widen the night detector's structural margin: mutation
#                    drift shrinks h3's activation (noise/food weights on the
#                    unit) and can add a negative noise skip on this row, so a
#                    drifted genome can see h3 ~0.25 at full night; 8.0 keeps
#                    rest pre-activation >= ~0.9 even then (sigmoid >= 0.71,
#                    above the 0.6 threshold). The body's latch
#                    (REST_WAKE_ENERGY) makes naps real instead of a one-frame
#                    flicker at the threshold.
#   other_close (col 15): 0 everywhere, RESERVED for future training — a
#                    linear output cannot multiply closeness x direction, so
#                    distance modulation would need a hidden detector.
#   grab:            pick up the food under the agent into its one-slot
#                    inventory (the cell empties, the agent carries the
#                    food; deposit/consume of the inventory is future work).
#                    NOT hand-tuned: every weight is 0 and the bias is -2.0
#                    (sigmoid(-2) ~ 0.12, far below the threshold), so
#                    grabbing must be discovered by mutation drift over
#                    generations — it may never emerge. A usable policy
#                    needs pre-activation > 0, e.g. a weight ~ +2.1 on
#                    food_close (col 11) or on h4 (food_ahead, col 4); h5
#                    (carrying, col 5) and has_food (col 16) tell the brain
#                    the inventory is full, to decide what to do with it.
BRAIN_W_OUT = [
    #      h0  h1  h2  h3  h4  h5 | hunger energy night dir_x dir_y close noise oth_x oth_y oth_close has_food
    [2.4, 0.0, 0.0, 0.0, 0.0, 0.0,  0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 2.0,  -3.0, 0.0, 0.0, 0.0],  # move_x
    [0.0, 2.4, 0.0, 0.0, 0.0, 0.0,  0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 2.0,  0.0, -3.0, 0.0, 0.0],  # move_y
    [0.0, 0.0, 0.0, 0.0, 1.0, 0.0,  20.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0,  0.0, 0.0, 0.0, 0.0],  # eat
    [0.0, 0.0, 8.0, 8.0, 0.0, 0.0,  0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0,  0.0, 0.0, 0.0, 0.0],  # rest
    [0.0, 0.0, 0.0, 0.0, 0.0, 0.0,  0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0,  0.0, 0.0, 0.0, 0.0],  # grab
]
# Movement biases: +0.5. The old -0.5 was tuned against a neutral food_dir
# input (0.5 with no food) that contributed +2.4 * 0.5 = +1.2 to each move
# pre-activation; now food direction is gated through h0/h1 (0 when
# satiated), so that +1.2 baseline is gone and the bias compensates: the
# solo wander envelope is 2.0 * noise - 1.5 + 0.5 = 2.0 * noise - 1.0,
# i.e. [-1.0, +1.0] — symmetric, slightly livelier than the old
# [-0.8, +0.8].
# eat bias: -10.5 pairs with the 20.0 hunger skip (see the eat comment
# above). grab bias: -2.0, negative on purpose — see the grab row comment.
BRAIN_B_OUT = [0.5, 0.5, -10.5, -1.0, -2.0]

# Output thresholds: above these, the body acts on the intention.
EAT_OUTPUT_THRESHOLD = 0.5
REST_OUTPUT_THRESHOLD = 0.6
GRAB_OUTPUT_THRESHOLD = 0.3

# --- Inspector (per-agent neural network debug window) ---
INSPECTOR_WINDOW_WIDTH = 380
INSPECTOR_WINDOW_HEIGHT = 620
INSPECTOR_WINDOW_TITLE = "GEVS IA — Inspector"
INSPECTOR_CLICK_RADIUS = 0.6      # cells; max distance from click to select an agent
COLOR_INSPECTOR_BG = (18, 20, 28)
COLOR_INSPECTOR_TEXT = (235, 238, 245)
COLOR_INSPECTOR_MUTED = (140, 146, 165)
COLOR_NODE_LOW = (40, 46, 62)     # node color at activation 0
COLOR_NODE_HIGH = (96, 220, 160)  # node color at activation 1
COLOR_NODE_OUTLINE = (10, 11, 16)
COLOR_EDGE = (60, 66, 84)
COLOR_SELECTED_OUTLINE = (255, 224, 90)  # ring around the selected agent, main window

# --- Genetics ---
# Each agent owns a Genome: the brain weight tables (sim.genetics) plus
# body traits (multipliers ~1.0 over the base rates above). The initial
# population is born from the hand-tuned tables with small noise.
INITIAL_WEIGHT_NOISE = 0.02   # sigma gaussiana del ruido inicial en pesos
INITIAL_TRAIT_NOISE = 0.05    # sigma gaussiana del ruido inicial en rasgos
WEIGHT_MUTATION_RATE = 0.05   # probabilidad de mutar cada peso (por gen)
WEIGHT_MUTATION_SIGMA = 0.20  # sigma de la mutación aditiva de pesos
WEIGHT_CLAMP = 20.0           # pesos acotados a [-WEIGHT_CLAMP, +WEIGHT_CLAMP]
TRAIT_MUTATION_RATE = 0.20    # probabilidad de mutar cada rasgo
TRAIT_MUTATION_SIGMA = 0.05   # sigma multiplicativa (log-normal) de rasgos
TRAIT_MIN = 0.5               # límite inferior del multiplicador de rasgo
TRAIT_MAX = 2.0               # límite superior

# --- Reinforcement learning (aprendizaje personal, no genético) ---
# agent.brain empieza como copia exacta de los pesos del genoma y se ajusta
# en vida con una regla Hebbiana modulada por recompensa (sin backprop). El
# genoma nunca se toca: lo aprendido no se hereda.
LEARNING_RATE = 0.02          # tasa del ajuste hebbiano
ELIGIBILITY_DECAY = 0.90      # decaimiento por tick de la traza de elegibilidad
REWARD_GRAB_SUCCESS = 1.0     # recompensa al recoger comida con éxito
PUNISH_HUNGER_SCALE = 0.5     # castigo/tick = -escala * max(0, hunger - HUNGER_WARNING)

# --- Death and population ---
MAX_AGE_S = 300.0             # s; death by old age (5 simulated days)
MAX_POPULATION = 60           # safety cap on the living population

# --- Reproduction ---
MATE_ENERGY_THRESHOLD = 0.60  # min energy to be eligible to mate
MATE_HUNGER_MAX = 0.50        # max hunger to be eligible to mate
MATE_COOLDOWN_S = 15.0        # s of waiting after mating (also the child's "infancy")
MATE_RANGE = 5.0              # cells; mate reflex seeks partners within this radius
MATE_ENERGY_COST = 0.25       # energy paid by EACH parent (threshold 0.6 - cost 0.25 -> never negative)
CHILD_INITIAL_ENERGY = 0.80   # the child's starting energy
CHILD_INITIAL_HUNGER = 0.20   # the child's starting hunger
