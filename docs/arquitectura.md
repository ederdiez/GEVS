# Arquitectura

## Mapa de archivos

```
gevs_ia/
├── main.py              # Punto de entrada: crea la ventana y lanza el bucle.
├── requirements.txt     # Dependencias (pygame).
├── .gitignore           # Qué no se versiona (venv, secretos, caches...).
├── docs/                # Esta documentación.
└── sim/                 # El código de la simulación.
    ├── __init__.py      # Marca el paquete `sim`.
    ├── config.py        # ★ TODAS las constantes editables (tamaño, FPS, colores...).
    ├── window.py        # Crea la ventana de pygame.
    ├── world.py         # Lógica pura del mundo: grid + reloj día/noche (sin pygame).
    ├── drawing.py       # Funciones de dibujo (una función por elemento).
    └── loop.py          # Bucle principal: eventos → actualizar → dibujar.
```

## Flujo de ejecución

```
main.py
  └─ window.create_window()   →  crea la ventana
  └─ loop.run(screen)         →  bucle infinito:
        1. eventos (cerrar ventana...)
        2. world.update(dt)      ← aquí entrarán los agentes
        3. dibujar               ← drawing.py (5 capas, en orden)
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

**API de consulta** (lo que usarán los futuros agentes):

| Método / atributo       | Qué devuelve                                  |
| ----------------------- | --------------------------------------------- |
| `is_walkable(x, y)`     | `True` si la celda está en el mundo y no es obstáculo. |
| `cell_type(x, y)`       | Tipo de celda (fuera de límites = obstáculo). |
| `hour`                  | Hora simulada (0.0–24.0).                     |
| `daylight_factor`       | 0.0 noche → 1.0 día pleno (interpolación lineal). |
| `day`                   | Número de día simulado.                       |

## El dibujo (`sim/drawing.py`)

Una función por elemento, y el bucle las llama en este orden (importa):

1. `draw_background` — suelo, con color interpolado según la hora.
2. `draw_world` — obstáculos y recursos (celdas no vacías).
3. `draw_night_overlay` — oscurece el mundo de noche (surface translúcida).
4. `draw_hud` — reloj "Día N  HH:MM" (siempre legible, encima del overlay).

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
| Cómo se dibuja algo      | `sim/drawing.py` (añade una función).   |
| Qué hace el bucle        | `sim/loop.py`.                          |
| Qué módulos se cargan    | `main.py`.                              |

## Cómo añadir algo nuevo (ejemplo: agentes)

1. Crea `sim/agent.py` con la clase `Agent` (posición, estado, método `update`).
2. En `world.py`, `World` ya tiene `self.entities` esperando a los agentes:
   añádelos ahí al crearlos.
3. En `loop.py`, amplía el paso 2 (`# Update the world`) para actualizar
   también cada entidad.
4. En `drawing.py`, añade `draw_agents(screen, world)` y llámala en el paso 3
   del bucle (antes del HUD).
5. Actualiza `docs/` para reflejar los módulos nuevos.

## Reglas informales del proyecto

- **Un archivo, una responsabilidad.** Si un archivo crece demasiado,
  divídelo.
- **Nada de números mágicos en el código.** Todo número configurable va a
  `config.py`.
- **Código en inglés, documentación en español.**
