# El mundo (`sim/world.py`)

`World` es **lógica pura**: no importa pygame, así que se puede probar sin
ventana. Contiene dos cosas:

- **El grid** `grid[y][x]` (filas primero), un tablero de 40×30 celdas de
  20 px. Cada celda es un entero:

  | Valor | Constante        | Qué es                                    |
  | ----- | ---------------- | ----------------------------------------- |
  | 0     | `CELL_EMPTY`     | suelo vacío                               |
  | 2     | `CELL_RESOURCE`  | comida, verde, caminable                  |
  | 3     | `CELL_ROCK`      | roca, colisionable                        |
  | 4     | `CELL_WOOD`      | madera, colisionable                      |

  Se genera de forma procedimental con semilla fija (`WORLD_SEED = 42`) en
  tres pasadas sobre celdas vacías: rocas (`ROCK_DENSITY = 0.08`), madera
  (`WOOD_DENSITY = 0.04`) y comida (`RESOURCE_DENSITY = 0.04`). Mismo seed,
  mismo mundo.

  El grid **no tiene borde**: es un mundo toroidal ("esférico"). Cruzar un
  extremo envuelve al lado opuesto — `World.wrap(x, y)` hace `x % cols, y
  % rows`, y todas las consultas de celda/movimiento pasan por ahí
  (`cell_type`, `is_walkable`, `try_claim`, `release`, el spawn de hijos...).
  Lo único que detiene a un agente son las rocas y la madera.

- **El reloj simulado** `time_sim`: un día dura `DAY_LENGTH_S = 60` s
  reales. De él se derivan `hour` (0–24 h) y `daylight_factor` (0 = noche,
  1 = día), que manejan el ciclo día/noche.

## API (la que usan los agentes)

| Método / atributo       | Qué hace / devuelve                           |
| ----------------------- | --------------------------------------------- |
| `wrap(x, y)`             | Envuelve una coordenada al grid toroidal (`x % cols, y % rows`); sirve tanto para celdas (int) como posiciones (float). |
| `is_walkable(x, y)`     | `True` si la celda (envuelta) no es roca ni madera (la comida sí es caminable). |
| `cell_type(x, y)`       | Tipo de celda (envuelta al grid; el mundo no tiene fuera de límites). |
| `hour`                  | Hora simulada (0.0–24.0).                     |
| `daylight_factor`       | 0.0 noche → 1.0 día pleno (interpolación lineal). |
| `day`                   | Número de día simulado.                       |
| `food_cells`            | `set` de `(x, y)` con comida (en sync con el grid). |
| `consume_resource(x, y)`| Comer: la celda se vacía y arranca su timer de regrow. |
| `try_claim(x, y, agent)`| Intentar ocupar la celda: `False` si está ocupada o no es caminable. |
| `release(x, y, agent)`  | Soltar la claim (solo el dueño puede).        |
| `occupied`              | `dict` `(x, y) → agent`: las celdas reclamadas (nunca dos agentes en una). |
| `entities`              | Lista de agentes vivos en el mundo.           |
| `animals`                | Lista de animales vivos (`sim.animal.Animal`, depredadores scripted — ver [Agentes → Depredadores](agentes.md)); no reclaman celda en `occupied`. |
| `rng`                   | Aleatorio determinista del mundo (seed fija): aquí vive todo el azar de la simulación. |
| `spawn_agent(cx, cy, ...)` | Crea un agente (población inicial y nacimientos) y reclama su celda. |
| `kill(agent)`           | Marca la baja y libera la claim al instante; la remoción se materializa en `end_frame()`. |
| `kill_animal(animal)`   | Igual que `kill()` para un animal (sin claim que liberar); la remoción se materializa en `end_frame()`. |
| `mate(a, b)`            | Apareamiento: coste de energía, cooldown mutuo y nacimiento diferido (crossover + mutación). |
| `end_frame()`           | Tras el bucle de agentes: baja a los muertos (agentes y animales) y coloca a los nacidos. |
| `stats_deaths` / `stats_births` | Contadores acumulados de muertes y nacimientos (HUD). |
