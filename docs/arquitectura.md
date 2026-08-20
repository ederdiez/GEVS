# Arquitectura

## Mapa de archivos

```
gevs_ia/
├── main.py              # Punto de entrada: crea la ventana y lanza el bucle.
├── requirements.txt     # Dependencias (pygame).
├── .gitignore           # Qué no se versiona (venv, secretos, caches...).
├── docs/                # Esta documentación.
├── tests/               # Smoke tests headless (sin pygame).
└── sim/                 # El código de la simulación.
    ├── __init__.py      # Marca el paquete `sim`.
    ├── config.py        # ★ TODAS las constantes editables (tamaño, FPS, colores, pesos de la red...).
    ├── window.py        # Crea la ventana de pygame.
    ├── world.py         # Lógica pura del mundo: grid + reloj + comida + claims + nacimientos/muertes (sin pygame).
    ├── agent.py         # El agente: cuerpo que ejecuta las intenciones del cerebro.
    ├── brain.py         # MLP pura en Python: forward de la red (máquina sin estado).
    ├── genetics.py      # Genoma: pesos del cerebro + rasgos del cuerpo; crossover, mutación, clon.
    ├── drawing.py       # Funciones de dibujo (una función por elemento).
    └── loop.py          # Bucle principal: eventos → actualizar → dibujar.
```

## Flujo de ejecución

```
main.py
  └─ window.create_window()   →  crea la ventana
  └─ loop.run(screen)         →  bucle infinito:
        1. eventos (cerrar ventana...)
        2. world.update(dt)   →  reloj + regrow de comida
           + cada agente: brain.forward() + cuerpo (movimiento, comer, descansar, aparearse)
           + world.end_frame() → materializa las muertes y nacimientos diferidos
        3. dibujar            ← drawing.py (5 capas, en orden)
        4. esperar al próximo frame (FPS)
```

## El mundo (`sim/world.py`)

`World` es **lógica pura**: no importa pygame, así que se puede probar sin
ventana. Contiene dos cosas:

- **El grid** `grid[y][x]` (filas primero), un tablero de 40×30 celdas de
  20 px. Cada celda es un entero: `CELL_EMPTY` (0), `CELL_OBSTACLE` (1)
  (rocas, muros) o `CELL_RESOURCE` (2) (comida). Se genera de forma
  procedimental con una semilla fija (`WORLD_SEED = 42`): mismo seed,
  mismo mundo.
- **El reloj simulado** `time_sim`: un día dura `DAY_LENGTH_S = 60` segundos
  reales. Desde él se derivan `hour` (0–24 h) y `daylight_factor` (0 =
  noche, 1 = día), que manejan el ciclo día/noche.

**API** (la que usan los agentes):

| Método / atributo       | Qué hace / devuelve                           |
| ----------------------- | --------------------------------------------- |
| `is_walkable(x, y)`     | `True` si la celda está en el mundo y no es obstáculo. |
| `cell_type(x, y)`       | Tipo de celda (fuera de límites = obstáculo). |
| `hour`                  | Hora simulada (0.0–24.0).                     |
| `daylight_factor`       | 0.0 noche → 1.0 día pleno (interpolación lineal). |
| `day`                   | Número de día simulado.                       |
| `food_cells`            | `set` de `(x, y)` con comida (en sync con el grid). |
| `consume_resource(x, y)`| Comer: la celda se vacía y arranca su timer de regrow. |
| `try_claim(x, y, agent)`| Intentar ocupar la celda: `False` si está ocupada o no es caminable. |
| `release(x, y, agent)`  | Soltar la claim (solo el dueño puede).        |
| `occupied`              | `dict` `(x, y) → agent`: las celdas reclamadas (nunca dos agentes en una). |
| `entities`              | Lista de agentes vivos en el mundo.           |
| `rng`                   | Aleatorio determinista del mundo (seed fija): aquí vive todo el azar de la simulación. |
| `spawn_agent(cx, cy, ...)` | Crea un agente (población inicial y nacimientos) y reclama su celda. |
| `kill(agent)`           | Marca la baja y libera la claim al instante; la remoción se materializa en `end_frame()`. |
| `mate(a, b)`            | Apareamiento: coste de energía, cooldown mutuo y nacimiento diferido (crossover + mutación). |
| `end_frame()`           | Tras el bucle de agentes: baja a los muertos y coloca a los nacidos. |
| `stats_deaths` / `stats_births` | Contadores acumulados de muertes y nacimientos (HUD). |

## Los agentes: cerebro NN + cuerpo

**La red propone, el cuerpo ejecuta.** Todo el comportamiento sale de una
red neuronal (`sim/brain.py`, MLP en Python puro: 10 entradas → 5 neuronas
ocultas relu → 5 salidas sigmoid). La red emite *intenciones*; un cuerpo
(`sim/agent.py`) garantiza lo inviolable: no pisar rocas, no ocupar una
celda ajena, comer solo donde hay comida, no moverse mientras se descansa,
buscar pareja cuando es el momento. Así la red puede ser torpe y la
simulación nunca se rompe. Desde la genética (ver sección siguiente), cada
agente tiene **su propio cerebro**: los pesos vienen de su genoma, no de
una tabla compartida. La salida 5ª (`grab`) no está ajustada a mano: parte
con pesos a cero y bias −2.0, por lo que el comportamiento de acaparar
recursos debe ser descubierto por mutación a lo largo de generaciones
(puede no surgir nunca). El cuerpo limita el inventario a un único recurso
por agente.

### Entradas de la red (10, normalizadas a [0,1])

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

### Capa oculta (5 detectores legibles, relu)

Cada neurona detecta una condición y su significado está documentado en
`config.py`:

- `h0 hungry` = relu(hunger − 0.55)
- `h1 starving` = relu(hunger − 0.85)
- `h2 sleepy` = relu(0.70 − energy)
- `h3 night` = relu(night − 0.50)
- `h4 food_ahead` = relu(food_close − 0.20)

### Salidas (4, sigmoid → [0,1])

| Salida       | Intención        | El cuerpo hace |
|--------------|------------------|----------------|
| `move_x`, `move_y` | dirección deseada (`2v−1 ∈ [−1,1]`) | avanzar a `AGENT_SPEED` celdas/s, con claims por eje; celda bloqueada → sostén pegajoso por eje (sin temblor) + re-sondeo cada `BLOCKED_PROBE_S`, o rodeo de `DETOUR_S` si la celda es una roca o el borde (ver Evitación de choques) |
| `eat`        | comer            | si `eat > EAT_OUTPUT_THRESHOLD` (0.5) y el agente está sobre comida → comer (celda se vacía, regrow) |
| `rest`       | descansar        | si `rest > REST_OUTPUT_THRESHOLD` (0.6) → no moverse y recuperar energía |

**Reflejo de supervivencia** (por debajo del cerebro, como en la biología):
si `hunger > HUNGER_CRITICAL` (0.85), el agente ignora `rest` y sigue
buscando comida.

**Ritmos** (sección `# --- Agents ---` de `config.py`, calibrados para un
día de 60 s reales, ciclo completo visible en ~2 min): las necesidades son
**regímenes exclusivos** — o comes, o duermes, o estás activo, nunca dos a
la vez. Despierto, la hambre sube a `HUNGER_RATE = 0.024`/s (~1 comida al
día) y la energía se drena a `ENERGY_DRAIN_RATE = 0.017`/s (de lleno a
soñoliento en ~20 s → siestas reales a media mañana). Descansando, la
energía recupera a `ENERGY_REST_RATE = 0.035`/s y la hambre queda congelada
(dormir congela la necesidad); un descanso no se interrumpe hasta que la
energía vuelve a `REST_WAKE_ENERGY = 0.60` (enclavamiento: sin él, la
salida `rest` tiembla en el umbral y la siesta duraría un frame). De noche
todos duermen (luz < 0.5), a no ser que la hambre sea crítica. Comer dura
2 s y baja la hambre 0.9; la comida reaparece a los 45 s. Estas son las
tasas **base**: cada agente las multiplica por sus rasgos hereditarios
(sección siguiente, `TRAIT_MIN`–`TRAIT_MAX`).

### Evitación de choques

Cuando dos agentes se acercan se apartan, y contra rocas o vecinos el cuerpo
se queda quieto y firme (sin temblar). Tiene dos mitades:

- **En la red (afinado a mano, estilo v1):** las entradas 7 y 8
  (`other_dir_x/y`, la dirección al otro agente más cercano dentro de
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
  propio sostén pegajoso** y los cruces se detectan con `math.floor()`: al
  fallar, el clamp deja al agente pegado al borde bloqueado (`cx + 0.99`) y,
  si la celda es una **claim ajena**, la posición se congela en ese eje y la
  celda se re-sondea cada `BLOCKED_PROBE_S = 0.5` s (el otro agente se
  moverá; si cambias de dirección, el sostén se suelta y te vas). Si la
  celda es una **roca o el borde del mapa** (nunca se libera, no merece la
  pena sondear), arranca un rodeo de `DETOUR_S = 0.4` s deslizándose por el
  eje tangente hacia el lado de la comida; los rodeos consecutivos en la
  misma dirección alternan de flanco (zigzag, para bordear grupos de rocas)
  y, tras dos lados fallidos, el agente retrocede para que la red
  reoriente. Empujar con fuerza cero (el otro eje hace el trabajo) no toca
  los sostenes.

Perillas de afinado (todas en `config.py`): el peso de evitación (3.0),
`AGENT_SENSE_RANGE` (cuánto "espacio personal" se detecta),
`BLOCKED_PROBE_S` (cada cuánto se re-intenta la celda bloqueada),
`DETOUR_S` (cuánto dura el rodeo de rocas/bordes) y `REST_WAKE_ENERGY`
(el nivel de energía que pone fin a una siesta).

### Cómo editar el comportamiento (receta)

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

## Genética y reproducción

Cada agente posee su propio **genoma** (`sim/genetics.py`): las tablas de
pesos del cerebro más 6 **rasgos del cuerpo** — velocidad, rango de
percepción de comida y ritmos de hambre/energía/comer/descansar — que
multiplican las tasas base de `config.py`. La población inicial nace de
las tablas afinadas ± ruido pequeño (`INITIAL_WEIGHT_NOISE`,
`INITIAL_TRAIT_NOISE`). El genoma es la **única unidad de herencia**:
crossover, mutación y clon operan solo sobre él. El `Brain` es una máquina
de forward sin estado hereditario: solo lee las tablas de su genoma, y
como `crossover`/`mutate` son puros (devuelven un genoma nuevo, nunca
tocan al padre), compartir referencias es inofensivo.

- **Herencia (sexual por encuentro).** Dos agentes elegibles (energía ≥
  `MATE_ENERGY_THRESHOLD`, hambre ≤ `MATE_HUNGER_MAX`, fuera de cooldown)
  a distancia Manhattan ≤ `MATE_RANGE` se buscan mutuamente: el reflejo de
  pareja vive en el **cuerpo** y sobreescribe la evitación de la red — el
  mismo patrón "cuerpo inviolable" que el food rush, sin tocar la
  topología 10→5→4 ni los pesos afinados (la **entrada 9 del cerebro
  sigue reservada**). A distancia 1 se aparean: cada padre paga
  `MATE_ENERGY_COST`, ambos entran en `MATE_COOLDOWN_S` (el primer
  apareamiento de un frame fija el cooldown de ambos, así que una pareja
  nunca produce doble nacimiento) y el hijo hereda por **crossover
  uniforme por gen** (p = 0.5) + **mutación** — pesos: aditiva gaussiana
  con clamp; rasgos: log-normal (mantiene la positividad), ambos
  clampeados a sus límites. El vector hacia la pareja se **normaliza**
  por distancia Manhattan: un delta crudo de 2 celdas por sub-paso
  violaría el invariante `AGENT_STEP_S · speed < 1` y saltaría claims.
- **El nacimiento.** El hijo se coloca en una celda libre adyacente
  (orden fijo y determinista: 4-vecindad primero, luego diagonales) con
  `CHILD_INITIAL_HUNGER`/`CHILD_INITIAL_ENERGY`, `generation = max(padres)
  + 1`, sus `parents` registrados y su propio cooldown de "infancia"
  (también una mitigación barata del incesto padre-hijo). Si no hay celda
  libre o la población está en `MAX_POPULATION`, el apareamiento aborta
  sin coste ni cooldown y el reflejo reintenta solo mientras sigan
  adyacentes.
- **Muerte.** `hunger ≥ 1.0`, `energy ≤ 0.0` o `age ≥ MAX_AGE_S`.
  `world.kill()` marca la baja y libera la claim al instante; la remoción
  de `entities` se materializa en `world.end_frame()` — nunca se muta la
  lista en medio del bucle de agentes (`loop.py` llama a `end_frame` tras
  el bucle; los tests hacen lo mismo). Las bajas se procesan antes que los
  nacimientos; si el spot del nacimiento se escapó entre `mate()` y
  `end_frame`, se re-busca y, si no queda sitio, se descarta el nacimiento
  (raro, documentado).

**Determinismo:** todo el azar — ruido inicial, crossover, mutación y el
noise del cerebro — sale del `rng` del mundo, así que una semilla
reproduce la misma trayectoria evolutiva (`tests/smoke_agents.py` lo
comprueba con dos mundos pisados lado a lado).

## El dibujo (`sim/drawing.py`)

Una función por elemento, y el bucle las llama en este orden (importa):

1. `draw_background` — suelo, con color interpolado según la hora.
2. `draw_world` — obstáculos y recursos (celdas no vacías).
3. `draw_agents` — un círculo por agente (color según estado: comiendo
   verde, descansando azul, hambriento naranja, apareándose **magenta**
   (cooldown de apareamiento, recién apareado o recién nacido), activo gris).
4. `draw_night_overlay` — oscurece el mundo de noche (surface translúcida);
   los agentes se oscurecen con el mundo (dormidos de noche, coherente).
5. `draw_hud` — "Día N  HH:MM" y "Población: N  †muertes  +nacimientos"
   (siempre legible, encima del overlay).

> **Perspectiva:** la vista es top-down pura (el mundo se ve desde arriba),
> así que no hay cielo: la luz del día se transmite solo con la
> interpolación de colores y el overlay nocturno.

> **Nota técnica:** el HUD se dibuja con `pygame._freetype` en lugar de
> `pygame.font`. El wheel de pygame 2.6.1 para Python 3.14 no incluye la
> extensión C de `font` (ni `imageext` ni `mixer`), y su fallback en Python
> puro muere por un import circular entre `font.py` y `sysfont.py`. El motor
> real que sí funciona es `pygame._freetype`; el HUD lo usa directamente con
> la misma fuente integrada.

## Cómo editar cada cosa

| Quiero cambiar...        | Dónde                                   |
| ------------------------ | --------------------------------------- |
| Tamaño de ventana, FPS, colores | `sim/config.py` (solo constantes). |
| Título de la ventana     | `WINDOW_TITLE` en `sim/config.py`.      |
| Densidad de rocas/comida | `OBSTACLE_DENSITY` / `RESOURCE_DENSITY` en `sim/config.py`. |
| Duración del día         | `DAY_LENGTH_S` en `sim/config.py`.      |
| Horas de amanecer/anochecer | `DAWN_START`…`DUSK_END` en `sim/config.py`. |
| Número de agentes, velocidad, ritmos de hambre/energía | sección `# --- Agents ---` en `sim/config.py`. |
| Evitación: rango del sensor, re-sondeo y rodeo de rocas | `AGENT_SENSE_RANGE` / `BLOCKED_PROBE_S` / `DETOUR_S` en `sim/config.py`. |
| El comportamiento de los agentes (pesos de la red) | matrices de la sección `# --- Brain ---` en `sim/config.py`. |
| Genética (ruido inicial, mutación, clamps) | sección `# --- Genetics ---` en `sim/config.py`. |
| Reproducción (umbrales, cooldown, coste, rango) | sección `# --- Reproduction ---` en `sim/config.py`. |
| Muerte y tope de población | `MAX_AGE_S` / `MAX_POPULATION` en `sim/config.py`. |
| El genoma (crossover/mutación/clon) | `sim/genetics.py`.                    |
| Lo que un agente puede/cómo se mueve | `sim/agent.py` (el cuerpo).         |
| Las señales que la red recibe | `Agent._inputs()` en `sim/agent.py`. |
| Cómo se dibuja algo      | `sim/drawing.py` (añade una función).   |
| Qué hace el bucle        | `sim/loop.py`.                          |
| Qué módulos se cargan    | `main.py`.                              |

## Cómo añadir algo nuevo (ejemplo: otra entidad)

Los agentes fueron el primer caso (ya hecho); el patrón sigue sirviendo
para añadir cualquier cosa nueva:

1. Crea un módulo nuevo (p. ej. `sim/mensaje.py`) con una clase y su `update`.
2. En `world.py`, añade la lista donde viva (p. ej. `self.mensajes`) y
   actualízala en `update(dt)`.
3. En `loop.py`, amplía el paso 2 para actualizar también lo nuevo.
4. En `drawing.py`, añade una función de dibujo y llámala en el paso 3,
   en la capa correcta.
5. Actualiza `docs/` para reflejar el módulo nuevo.

## Reglas informales del proyecto

- **Un archivo, una responsabilidad.** Si un archivo crece demasiado,
  divídelo.
- **Nada de números mágicos en el código.** Todo número configurable va a
  `config.py`.
- **Código en inglés, documentación en español.**
