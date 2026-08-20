# Los agentes: cerebro NN + cuerpo

**La red propone, el cuerpo ejecuta.** Todo el comportamiento sale de una
red neuronal (`sim/brain.py`, MLP en Python puro: 11 entradas → 6 neuronas
ocultas relu → 5 salidas sigmoid). La red emite *intenciones*; un cuerpo
(`sim/agent.py`) garantiza lo inviolable: no pisar rocas, no ocupar una
celda ajena, comer solo donde hay comida, no moverse mientras se descansa,
buscar pareja cuando es el momento. Así la red puede ser torpe y la
simulación nunca se rompe. Desde la genética, cada agente tiene **su propio
cerebro**: los pesos vienen de su genoma, no de una tabla compartida.

La salida 5ª (`grab`) no está ajustada a mano: parte con pesos a cero y
bias −2.0, por lo que el comportamiento de acaparar recursos debe ser
descubierto por mutación a lo largo de generaciones (puede no surgir
nunca). El cuerpo limita el inventario a un único recurso por agente.

## Entradas de la red (11, normalizadas a [0,1])

Calculadas cada frame en `Agent._inputs()`:

| # | Señal         | De dónde |
|---|---------------|----------|
| 0 | `hunger`      | necesidad del agente (0–1) |
| 1 | `energy`      | necesidad del agente (0–1) |
| 2 | `night`       | `1 - daylight_factor` (0 = día, 1 = noche) |
| 3 | `food_dir_x`  | dirección a la comida más cercana, saturada a [-1,1] y normalizada `(dx+1)/2`; 0.5 si no hay en rango |
| 4 | `food_dir_y`  | idem, eje Y |
| 5 | `food_close`  | `1 - min(dist / FOOD_SENSE_RANGE, 1)`; 0 si no hay comida en rango |
| 6 | `noise`       | `world.rng.random()` por frame (deambular; determinista por semilla) |
| 7 | `other_dir_x` | dirección al otro agente más cercano, `(dx+1)/2`; 0.5 si no hay en rango |
| 8 | `other_dir_y` | idem, eje Y |
| 9 | `other_close` | `1 - min(dist / AGENT_SENSE_RANGE, 1)`; 0 si no hay otro agente en rango |
| 10 | `has_food`    | 1.0 si el inventario (una ranura) está lleno (lleva un recurso); 0.0 si está vacío |

## Capa oculta (6 detectores legibles, relu)

Cada neurona detecta una condición y su significado está documentado en
`config.py`:

- `h0 hungry` = relu(hunger − 0.55)
- `h1 starving` = relu(hunger − 0.85)
- `h2 sleepy` = relu(0.70 − energy)
- `h3 night` = relu(night − 0.50)
- `h4 food_ahead` = relu(food_close − 0.20)
- `h5 carrying` = relu(has_food − 0.50)

## Salidas (5, sigmoid → [0,1])

| Salida       | Intención        | El cuerpo hace |
|--------------|------------------|----------------|
| `move_x`, `move_y` | dirección deseada (`2v−1 ∈ [−1,1]`) | avanzar a `AGENT_SPEED` celdas/s, con claims por eje; celda bloqueada → sostén pegajoso por eje (sin temblor) + re-sondeo cada `BLOCKED_PROBE_S`, o rodeo de `DETOUR_S` si la celda es una roca o el borde (ver Evitación de choques) |
| `eat`        | comer            | si `eat > EAT_OUTPUT_THRESHOLD` (0.5) y el agente está sobre comida → comer (celda se vacía, regrow) |
| `rest`       | descansar        | si `rest > REST_OUTPUT_THRESHOLD` (0.6) → no moverse y recuperar energía |
| `grab`       | recoger          | si `grab > GRAB_OUTPUT_THRESHOLD` (0.5) y hay comida bajo el agente → pasa a su inventario (una ranura); la celda se vacía (mismo timer de regrow que comer) pero la comida se lleva, no se consume. El cuerpo ignora `grab` si el inventario está lleno; depositar/consumir lo llevado es trabajo futuro. |

**Reflejo de supervivencia** (por debajo del cerebro, como en la biología):
si `hunger > HUNGER_CRITICAL` (0.85), el agente ignora `rest` y sigue
buscando comida.

## Ritmos de las necesidades

Sección `# --- Agents ---` de `config.py`, calibrados para un día de 60 s
reales (ciclo completo visible en ~2 min). Las necesidades son **regímenes
exclusivos** — o comes, o duermes, o estás activo, nunca dos a la vez:

| Régimen | Comportamiento |
| ------- | -------------- |
| Despierto | hambre sube a `HUNGER_RATE = 0.024`/s (~1 comida al día); energía se drena a `ENERGY_DRAIN_RATE = 0.017`/s (de lleno a soñoliento en ~20 s → siestas reales a media mañana) |
| Descansando | energía recupera a `ENERGY_REST_RATE = 0.035`/s; hambre congelada (dormir congela la necesidad). Un descanso no se interrumpe hasta que la energía vuelve a `REST_WAKE_ENERGY = 0.60` (enclavamiento: sin él, la salida `rest` tiembla en el umbral y la siesta duraría un frame) |
| De noche | todos duermen (luz < 0.5), a no ser que la hambre sea crítica |
| Comiendo | dura 2 s y baja la hambre 0.9; la comida reaparece a los 45 s |

Estas son las tasas **base**: cada agente las multiplica por sus rasgos
hereditarios (ver Genética, `TRAIT_MIN`–`TRAIT_MAX`).

## Evitación de choques

Cuando dos agentes se acercan se apartan, y contra rocas o vecinos el
cuerpo se queda quieto y firme (sin temblar). Tiene dos mitades:

- **En la red (afinado a mano, estilo v1):** las entradas 7 y 8
  (`other_dir_x/y`, dirección al otro agente más cercano dentro de
  `AGENT_SENSE_RANGE = 2.0` celdas) llegan a `move_x`/`move_y` por skip
  connections con peso **−3.0**: si el otro está a la derecha, la red pide
  moverse a la izquierda. El peso negativo solo se activa cuando hay alguien
  en rango (sensor neutro 0.5 → contribución −1.5, compensada bajando los
  biases de movimiento de −2.0 a −0.5, así el deambular en solitario es
  idéntico a v1). `other_close` (entrada 9) está **reservada para el futuro
  entrenamiento**: una salida lineal no puede modular distancia × dirección,
  así que va a 0 en todos los pesos.
- **En el cuerpo (los bugs corregidos):** el clamp viejo ponía al agente en
  el lado *lejano* de su celda (`cx + 0.01` empujando a la derecha) y cada
  frame rebotaba ~0.9 celdas — el temblor visible contra rocas y vecinos.
  Además, un único sostén global se sobreescribía con cada eje, así que en
  las esquinas un agente quedaba congelado de por vida, y `int()` (que
  trunca hacia cero) no detectaba un cruce hacia la izquierda desde la
  columna 0 — el agente se escapaba del mapa. Ahora **cada eje tiene su
  propio sostén pegajoso** y los cruces se detectan con `math.floor()`:

  - Al fallar, el clamp deja al agente pegado al borde bloqueado
    (`cx + 0.99`).
  - Si la celda es una **claim ajena**, la posición se congela en ese eje y
    la celda se re-sondea cada `BLOCKED_PROBE_S = 0.5` s (el otro agente se
    moverá; si cambias de dirección, el sostén se suelta y te vas).
  - Si la celda es una **roca o el borde del mapa** (nunca se libera, no
    merece la pena sondear), arranca un rodeo de `DETOUR_S = 0.4` s
    deslizándose por el eje tangente hacia el lado de la comida; los rodeos
    consecutivos en la misma dirección alternan de flanco (zigzag, para
    bordear grupos de rocas) y, tras dos lados fallidos, el agente
    retrocede para que la red reoriente.
  - Empujar con fuerza cero (el otro eje hace el trabajo) no toca los
    sostenes.

Perillas de afinado (todas en `config.py`): el peso de evitación (3.0),
`AGENT_SENSE_RANGE` (cuánto "espacio personal" se detecta),
`BLOCKED_PROBE_S` (cada cuánto se re-intenta la celda bloqueada),
`DETOUR_S` (cuánto dura el rodeo de rocas/bordes) y `REST_WAKE_ENERGY`
(el nivel de energía que pone fin a una siesta).

## Cómo editar el comportamiento (receta)

- **Cambiar el comportamiento** → los pesos de la red en `config.py`
  (matrices comentadas): ajusta un detector de la capa oculta o su conexión
  con las salidas. Sin tocar código.
- **Añadir una señal nueva** → entrada nueva en `Agent._inputs()` + una
  columna en cada matriz de pesos de `config.py`.
- **Afinar la evitación** → peso −3.0 en `move_x`/`move_y` (matrices de
  `# --- Brain ---`) y el cuerpo: `AGENT_SENSE_RANGE`, `BLOCKED_PROBE_S`,
  `DETOUR_S` (sección `# --- Agents ---`).
- **Afinar el ritmo** → constantes de la sección `# --- Agents ---`.
- **Lo inviolable** no se edita: lo garantiza el cuerpo (`sim/agent.py`).
- **Probar sin abrir la ventana** → `tests/smoke_agents.py` y
  `tests/evolution_test.py` (headless).
