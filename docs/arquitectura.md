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
    ├── world.py         # Lógica pura del mundo: grid + reloj + comida + claims (sin pygame).
    ├── agent.py         # El agente: cuerpo que ejecuta las intenciones del cerebro.
    ├── brain.py         # MLP pura en Python: las redes neuronales de los agentes.
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
           + cada agente: brain.forward() + cuerpo (movimiento, comer, descansar)
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

## Los agentes v1: cerebro NN + cuerpo

**La red propone, el cuerpo ejecuta.** Todo el comportamiento sale de una
red neuronal (`sim/brain.py`, MLP en Python puro: 7 entradas → 5 neuronas
ocultas relu → 4 salidas sigmoid). La red emite *intenciones*; un cuerpo
(`sim/agent.py`) garantiza lo inviolable: no pisar rocas, no ocupar una
celda ajena, comer solo donde hay comida, no moverse mientras se descansa.
Así la red puede ser torpe y la simulación nunca se rompe — y cuando llegue
el entrenamiento/evolución, solo cambiarán los pesos, nunca el cuerpo.

### Entradas de la red (7, normalizadas a [0,1])

Calculadas cada frame en `Agent._inputs()`:

| # | Señal         | De dónde |
|---|---------------|----------|
| 0 | `hunger`      | necesidad del agente (0–1) |
| 1 | `energy`      | necesidad del agente (0–1) |
| 2 | `night`       | `1 - daylight_factor` (0 = día, 1 = noche) |
| 3 | `food_dir_x`  | dirección a la comida más cercana, `(dx+1)/2`; 0.5 si no hay en rango |
| 4 | `food_dir_y`  | idem, eje Y |
| 5 | `food_close`  | `1 - min(dist / FOOD_SENSE_RANGE, 1)`; 0 si no hay comida en rango |
| 6 | `noise`       | `world.rng.random()` por frame (deambular; determinista por semilla) |

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
| `move_x`, `move_y` | dirección deseada (`2v−1 ∈ [−1,1]`) | avanzar a `AGENT_SPEED` celdas/s, con claims y deslizamiento por el otro eje si está bloqueado |
| `eat`        | comer            | si `eat > EAT_OUTPUT_THRESHOLD` (0.5) y el agente está sobre comida → comer (celda se vacía, regrow) |
| `rest`       | descansar        | si `rest > REST_OUTPUT_THRESHOLD` (0.6) → no moverse y recuperar energía |

**Reflejo de supervivencia** (por debajo del cerebro, como en la biología):
si `hunger > HUNGER_CRITICAL` (0.85), el agente ignora `rest` y sigue
buscando comida.

**Ritmos** (sección `# --- Agents ---` de `config.py`, calibrados para un
día de 60 s reales, ciclo completo visible en ~2 min): la hambre sube solo
despierto (~1/día → comen una vez al día), la energía se drena despierto y
se recupera descansando, dormir congela la hambre, comer dura 2 s y baja la
hambre 0.9, la comida reaparece a los 45 s.

### Cómo editar el comportamiento (receta)

- **Cambiar el comportamiento** → los pesos de la red en `config.py`
  (matrices comentadas): ajusta un detector de la capa oculta o su conexión
  con las salidas. Sin tocar código.
- **Añadir una señal nueva** → entrada nueva en `Agent._inputs()` + una
  columna en cada matriz de pesos de `config.py`.
- **Afinar el ritmo** → constantes de la sección `# --- Agents ---`.
- **Lo inviolable** no se edita: lo garantiza el cuerpo (`sim/agent.py`).
- **Probar sin abrir la ventana** → `tests/smoke_agents.py` (headless).

## El dibujo (`sim/drawing.py`)

Una función por elemento, y el bucle las llama en este orden (importa):

1. `draw_background` — suelo, con color interpolado según la hora.
2. `draw_world` — obstáculos y recursos (celdas no vacías).
3. `draw_agents` — un círculo por agente (color según estado, ver leyenda abajo).
4. `draw_night_overlay` — oscurece el mundo de noche (surface translúcida);
   los agentes se oscurecen con el mundo (dormidos de noche, coherente).
5. `draw_hud` — reloj "Día N  HH:MM" (siempre legible, encima del overlay).

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
| El comportamiento de los agentes (pesos de la red) | matrices de la sección `# --- Brain ---` en `sim/config.py`. |
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
