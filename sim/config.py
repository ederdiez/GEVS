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

# --- Simulation speed control ---
# Multiplier options cycled with the speed-up/speed-down keys (+/-): each
# multiplier runs that many world/agent update steps per rendered frame,
# so simulated time advances faster while drawing stays at the same FPS.
SPEED_LEVELS = (1, 2, 4, 8, 16)

# --- Grid and world ---
CELL_SIZE = 20                 # px per cell (invariant: GRID_COLS * CELL_SIZE == WINDOW_WIDTH)
GRID_COLS = 40                 # invariant: GRID_COLS * CELL_SIZE == WINDOW_WIDTH
GRID_ROWS = 30                 # invariant: GRID_ROWS * CELL_SIZE == WINDOW_HEIGHT
WORLD_SEED = 5

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
ENERGY_DRAIN_RATE = 0.016  # energy lost per second while awake (full -> sleepy in ~20 s: real mid-day naps)

# Energy recovery while resting is NOT a flat rate: it follows a
# skewed-gaussian bump over *time continuously asleep* (agent._sleep_timer,
# reset the instant an agent wakes). This closes the "micro-nap" loophole a
# flat rate left open — agents were learning to drop into `resting` for a
# single frame at a time, since even a millisecond of a flat rate nudges
# energy over REST_WAKE_ENERGY. Now recovery starts near-zero (light
# sleep), ramps up sharply once truly asleep for a while, peaks at
# SLEEP_RECOVERY_PEAK_TIME (deep sleep), and eases back down over a long
# tail (SIGMA_FALL >> SIGMA_RISE shifts the bell's hump toward the left of
# its own span) rather than dropping back to zero, so a long nap keeps
# paying off all the way through. A one-frame nap now recovers almost
# nothing; only committing to real sleep does.
SLEEP_RECOVERY_BASE_RATE = 0.005    # energy/s at t ~ 0 (just fell asleep)
SLEEP_RECOVERY_PEAK_RATE = 0.16     # energy/s at the deep-sleep peak
SLEEP_RECOVERY_PEAK_TIME = 7.0      # s asleep at the deep-sleep peak
SLEEP_RECOVERY_SIGMA_RISE = 1.5     # s; spread of the climb INTO deep sleep (steep)
SLEEP_RECOVERY_SIGMA_FALL = 10.0    # s; spread of the ease OUT of deep sleep (long tail)

RESOURCE_REGROW_S = 30.0   # seconds until an eaten food cell regrows
FOOD_SENSE_RANGE = 8.0     # cells; beyond this the brain gets no food direction
AGENT_SENSE_RANGE = 2.0    # cells; "personal space" — nearest-agent sensors below this
BLOCKED_PROBE_S = 0.5      # s; while holding a blocked cell, re-probe it this often
REST_WAKE_ENERGY = 0.60    # resting agents stay down until energy >= this (nap latch)
MIN_ENERGY_TO_REST = 0.50  # can't fall asleep below this energy (exhausted agents keep moving)
DETOUR_S = 0.4             # s; slide around a rock/border before resuming (2.4 cells at AGENT_SPEED)

# Agent colors (drawing.py): state -> color
COLOR_AGENT_WANDER = (200, 200, 210)   # active, not hungry
COLOR_AGENT_HUNGRY = (232, 152, 64)    # active, hunger >= HUNGER_WARNING
COLOR_AGENT_EATING = (72, 190, 120)    # eating (green, like the food)
COLOR_AGENT_RESTING = (92, 132, 226)   # resting / sleeping (blue)
COLOR_AGENT_MATING = (214, 94, 194)    # magenta: in the mate cooldown (recently mated / newborn)
COLOR_AGENT_OUTLINE = (30, 32, 40)     # dark outline on every agent

# --- Brain (neural network) ---
# MLP: 13 inputs -> 6 hidden relu units -> 7 sigmoid outputs. Pure Python,
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
#   11 pos_x         absolute world position, x / GRID_COLS (0-1)
#   12 pos_y         absolute world position, y / GRID_ROWS (0-1)

# Hidden layer: 6 readable detectors (relu). One row per unit; columns are
# inputs 0-6 and 10 (needs, night, food direction, food_close, noise,
# has_food); pos_x/pos_y (11, 12) are wired at zero — no detector reads
# position yet. The output layer sees all 13 inputs via skip connections
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
    [2.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],  # h0
    [2.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],  # h1
    [0.0, -1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0], # h2
    [0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],  # h3
    [0.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],  # h4
    [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0],  # h5
]
BRAIN_B_HIDDEN = [-2.0, -2.0, 0.70, -0.50, -0.20, -0.50]

# Output layer: 7 outputs (move_x, move_y, eat, rest, grab, interact, drop). One row per output;
# columns are the 6 hidden activations followed by the 13 raw inputs
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
#
# grab/interact/drop are the *learned* rows: weak instinct + exploration +
# reinforcement, instead of the all-zero tables they used to have. Those
# tables were unreachable by construction — output pinned at sigmoid(-2) ~
# 0.12 against a 0.4 threshold, while the only reward in the simulation
# required a successful grab. Measured on 20 simulated minutes and 22
# generations: zero grabs ever, grab_out drifting no higher than 0.26. The
# whole RL system was dead code. Now:
#
#   1. INSTINCT (weights below): small hand-tuned weights that bring the row
#      *close* to the threshold in the right context but never cross it alone.
#   2. EXPLORATION (weight 3.0 on the noise column, 12): the noise input
#      already feeds movement; giving it weight here too makes the row fire
#      occasionally — motor babbling. It adds NO new rng draw (noise is
#      sampled once per _inputs(), agent.py), so determinism is untouched.
#   3. REINFORCEMENT: the reward ladder (see `# --- Reinforcement learning ---`)
#      grows the signal weights until they dominate the noise. Exploration is
#      self-limiting — the noise weight is a weight like any other, so
#      babbling that ends badly gets pushed back down by learn().
#
# Firing rates below are per tick, for u = noise ~ U[0,1); a row fires when
# `noise_w * u + signal + bias > -0.406` (the sigmoid pre-activation for the
# 0.4 threshold).
#
#   grab:            pick up the food under the agent into its one-slot
#                    inventory (the cell empties, like eating, but the food
#                    is carried instead of consumed). Instinct: +1.0 on h4
#                    (food_ahead), which is 0.8 while standing on food.
#                    With bias -3.36 and noise weight 3.0: ~1.5% per tick
#                    with no food around (harmless — the body blocks a grab
#                    off a food cell anyway) and ~28% per tick while standing
#                    on food, so an agent that walks over food picks it up
#                    within a few frames. NOT hunger-gated on purpose:
#                    grabbing while satiated is the interesting behavior
#                    (carrying a spare meal), and hunger gates the *eating*
#                    of it through the interact row below.
#   interact:        use whatever is in the one-slot inventory — for food
#                    that means eating it (same eat_timer state machine as
#                    eating off the ground, see agent.py); other future
#                    carryable items each define their own interact
#                    behavior, dispatched by item type. Instinct: +6.0 on
#                    hunger (col 6) and +0.5 on h5 (carrying, 0.5 when the
#                    inventory is full). The big hunger weight makes this a
#                    sharp hunger gate, deliberately lined up with the eat
#                    row's ~0.53 crossing: with bias -6.9 the rate is ~0 below
#                    hunger 0.5, ~2% at 0.55, ~32% at 0.7 and ~92% at 1.0.
#                    So a carried meal is kept until hunger actually calls
#                    for it — that is the behavior worth having. Like the eat
#                    row, the 6.0 weight is also drift margin: a mutation of
#                    ±0.2 shifts the hunger crossing by only ±0.03.
#   drop:            release the inventory onto the ground under the agent
#                    (only onto an empty cell). No instinct at all — dropping
#                    is not obviously smart, so it stays pure exploration at
#                    a deliberately low rate (bias -3.40 -> ~0.05% per tick,
#                    roughly once per 30 s of carrying). Dropping food while
#                    hungry is punished (PENALTY_DROP_HUNGRY), so learning
#                    pushes this row further down; dropping while satiated is
#                    neutral, leaving room for caching to be discovered.
BRAIN_W_OUT = [
    #      h0  h1  h2  h3  h4  h5 | hunger energy night dir_x dir_y close noise oth_x oth_y oth_close has_food pos_x pos_y
    [2.4, 0.0, 0.0, 0.0, 0.0, 0.0,  0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 2.0,  -3.0, 0.0, 0.0, 0.0, 0.0, 0.0],  # move_x
    [0.0, 2.4, 0.0, 0.0, 0.0, 0.0,  0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 2.0,  0.0, -3.0, 0.0, 0.0, 0.0, 0.0],  # move_y
    [0.0, 0.0, 0.0, 0.0, 1.0, 0.0,  20.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0,  0.0, 0.0, 0.0, 0.0, 0.0, 0.0],  # eat
    [0.0, 0.0, 8.0, 8.0, 0.0, 0.0,  0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0,  0.0, 0.0, 0.0, 0.0, 0.0, 0.0],  # rest
    [0.0, 0.0, 0.0, 0.0, 1.0, 0.0,  0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 3.0,  0.0, 0.0, 0.0, 0.0, 0.0, 0.0],  # grab
    [0.0, 0.0, 0.0, 0.0, 0.0, 0.5,  6.0, 0.0, 0.0, 0.0, 0.0, 0.0, 3.0,  0.0, 0.0, 0.0, 0.0, 0.0, 0.0],  # interact
    [0.0, 0.0, 0.0, 0.0, 0.0, 0.0,  0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 3.0,  0.0, 0.0, 0.0, 0.0, 0.0, 0.0],  # drop
]
# Movement biases: +0.5. The old -0.5 was tuned against a neutral food_dir
# input (0.5 with no food) that contributed +2.4 * 0.5 = +1.2 to each move
# pre-activation; now food direction is gated through h0/h1 (0 when
# satiated), so that +1.2 baseline is gone and the bias compensates: the
# solo wander envelope is 2.0 * noise - 1.5 + 0.5 = 2.0 * noise - 1.0,
# i.e. [-1.0, +1.0] — symmetric, slightly livelier than the old
# [-0.8, +0.8].
# eat bias: -10.5 pairs with the 20.0 hunger skip (see the eat comment
# above). grab/interact/drop biases set the exploration floor of each
# learned row against BRAIN_EXPLORE_NOISE_W (see the block comment above
# BRAIN_W_OUT for the firing-rate arithmetic): -3.36 -> grab babbles ~1.5%
# of ticks, -6.9 -> interact is a sharp hunger gate crossing near 0.55,
# -3.40 -> drop babbles ~0.05% of ticks.
BRAIN_B_OUT = [0.5, 0.5, -10.5, -1.0, -3.36, -6.9, -3.40]

# Output thresholds: above these, the body acts on the intention.
EAT_OUTPUT_THRESHOLD = 0.5
REST_OUTPUT_THRESHOLD = 0.6
GRAB_OUTPUT_THRESHOLD = 0.4
INTERACT_OUTPUT_THRESHOLD = 0.4
DROP_OUTPUT_THRESHOLD = 0.4

# --- Inspector (per-agent neural network debug window) ---
INSPECTOR_WINDOW_WIDTH = 700
INSPECTOR_WINDOW_HEIGHT = 900
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
#
# PRINCIPIO: se recompensa el RESULTADO, no el acto. La recompensa es el
# hambre realmente saciada; la traza de elegibilidad, al durar segundos, es
# la que reparte el crédito hacia atrás hasta el `grab` que lo hizo posible.
# Así la cadena "recoger -> llevar -> comer" se aprende en vez de estar
# cableada, y los exploits se cierran solos: dar vueltas recogiendo y
# soltando comida no sacia nada, luego no paga nada.
LEARNING_RATE = 0.075          # tasa del ajuste hebbiano (~7x el 0.02 de antes: ver la nota de escala abajo)
# Qué filas de salida son plásticas en vida: grab, interact, drop. Las
# demás (move_x, move_y, eat, rest) y toda la capa oculta son INSTINTO —
# solo la evolución las toca. Una recompensa escalar única no puede decir
# qué fila se la ganó, así que sin esta separación la recompensa por comida
# reescribe circuitos que no tienen nada que ver: medido antes de existir,
# el aprendizaje le escribió un peso de `noise` a la fila `rest` —cuyas
# entradas son constantes— y el sueño de un agente empezó a parpadear frame
# a frame justo en su umbral, dejando de dormir de noche con el estómago
# lleno. Los márgenes afinados a mano (el peso 20x del hambre en `eat`, el
# 8.0 de la noche en `rest`) existen precisamente para sobrevivir a la
# deriva; dejar que una señal hebbiana difusa los erosione destruye justo
# lo que protegen.
LEARNABLE_OUTPUTS = (4, 5, 6)  # índices de fila en BRAIN_W_OUT
ELIGIBILITY_TAU_S = 2.5       # s; constante de tiempo de la traza de elegibilidad
BASELINE_TAU_S = 10.0         # s; constante de tiempo de "lo que esta neurona suele hacer"
# La traza acredita la DESVIACIÓN de cada neurona respecto a su línea base,
# no su activación bruta. Sin esto la regla tiene crédito difuso: como la
# activación nunca es negativa, cualquier recompensa refuerza toda salida
# activa, tuviera o no que ver — y los biases más que nadie, porque su
# entrada es siempre 1. Medido en la primera calibración: la fila `drop`, a
# la que ninguna recompensa se refiere, pasó de una tasa de disparo del 0.2%
# al 13% en cuatro minutos simulados solo por esa deriva, los agentes se
# dedicaron a recoger y soltar comida sin parar, y la población se extinguió.
# Escala: la traza es una media móvil (brain.py), no una suma, y de una
# desviación en vez de una activación — ambas cosas la hacen mucho menor, y
# por eso LEARNING_RATE sube desde el 0.02 de antes. La suma antigua
# saturaba en 10x el producto pre*post con el decaimiento 0.90 por tick, así
# que llevaba esa ganancia incorporada, y habría saturado en 120x con un tau
# lo bastante largo para acreditar un `grab` por una comida que llega
# segundos después. Medido: a 0.5 la población cae a 7 en dos minutos; a
# 0.15 se mantiene en 15 y sigue creciendo.
#
# La escalera de recompensas. Cada peldaño responde a "¿qué necesidad se
# satisfizo?", nunca a "¿qué acción se ejecutó?":
REWARD_EAT_K = 3.0            # por unidad de hambre saciada (comer, venga de donde venga)
REWARD_INVENTORY_MEAL_MULT = 1.5  # comer del inventario paga más: requirió previsión
CARRY_MIN_S = 3.0             # s mínimos que un objeto se queda en el inventario
REWARD_GRAB = 0.15            # recoger es una inversión, no un pago
PENALTY_DROP_HUNGRY = -0.5    # soltar comida con hunger > HUNGER_WARNING: desperdicio
PENALTY_STARVING_WITH_FOOD = -0.4  # por segundo, con hunger > HUNGER_CRITICAL y comida encima
#
# Por qué REWARD_EAT_K domina: una comida completa sacia hasta 0.9 de hambre
# (EAT_RATE * EAT_DURATION_S), o sea paga hasta ~2.7 (~4.0 si venía del
# inventario) frente a los 0.15 de recoger. Recoger nunca puede convertirse
# en un fin en sí mismo.
#
# CARRY_MIN_S: no puedes soltar lo que acabas de coger, y no cobras el extra
# de previsión por una comida que no llegaste a llevar. Es el mismo
# enclavamiento del cuerpo que REST_WAKE_ENERGY, y por la misma razón: una
# salida que ronda su umbral produce parpadeo de un frame en vez de conducta.
# Medido sin él: la mediana de tiempo en el inventario era de 0.10 s y los
# agentes recogían y soltaban comida 50 veces por cada vez que comían. El
# valor no es indiferente — barrido sobre 5 min simulados: a 1.0 s salen 703
# sueltas y 17 comidas del inventario; a 3.0 s, 256 sueltas y 27 comidas
# (menos trasiego Y más conducta útil); a 6.0 s la población se hunde,
# porque bloquear tanto tiempo la única ranura impide recoger lo que sí hace
# falta. Cierra el agujero del multiplicador de previsión cuando `grab` e
# `interact` caen en el mismo tick, que habría cobrado el extra sin haber
# previsto nada — el mismo reward hacking que las microsiestas. El agujero
# gemelo de REWARD_GRAB (cobrar por recoger *y* por la comida en el mismo
# tick) lo cierra agent.py comprobando que el inventario siga ocupado tras
# resolver interact/drop, no CARRY_MIN_S.
#
# Nota de fragilidad: la tasa de disparo de una fila es convexa respecto a su
# bias, así que la media poblacional de la tasa es bastante mayor que la tasa
# del bias medio (Jensen), y una mutación de ±0.2 sobre un bias de -3.4
# multiplica la tasa de `drop` por un factor grande. Por eso el enclavamiento
# vive en el cuerpo: acota la conducta pase lo que pase con los pesos.
#
# PENALTY_STARVING_WITH_FOOD NO es el castigo por hambre que se retiró: exige
# llevar comida en el inventario. Aquel castigaba también al agente que iba
# camino de la comida sin haber llegado —empujando los pesos en contra del
# comportamiento que sí funcionaba—, y ese agente tiene el inventario vacío,
# así que nunca lo cobra. Aquí solo se castiga a quien lleva la solución
# encima y no la usa.

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

# --- Logging ---
LOG_DIR = "logs"              # one file per run, one line every LOG_INTERVAL_S
LOG_INTERVAL_S = 30.0         # simulated seconds between log lines
CHILD_INITIAL_HUNGER = 0.20   # the child's starting hunger
