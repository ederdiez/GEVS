# Los agentes: cerebro NN + cuerpo

**La red propone, el cuerpo ejecuta.** Todo el comportamiento sale de una
red neuronal (`sim/brain.py`, MLP en Python puro: 17 entradas → 8 neuronas
ocultas relu → 8 salidas sigmoid). La red emite *intenciones*; un cuerpo
(`sim/agent.py`) garantiza lo inviolable: no pisar rocas, no ocupar una
celda ajena, comer solo donde hay comida, no moverse mientras se descansa,
buscar pareja cuando es el momento. Así la red puede ser torpe y la
simulación nunca se rompe. Desde la genética, cada agente tiene **su propio
cerebro**: los pesos vienen de su genoma, no de una tabla compartida.

Las salidas `grab`, `interact` y `drop` son las **filas aprendidas**:
instinto débil + exploración + refuerzo (ver [Aprendizaje
personal](#aprendizaje-personal-no-genético)). El cuerpo limita el
inventario a un único recurso por agente. `interact`/`drop` despachan
según el tipo de objeto llevado (`_INVENTORY_ACTIONS`, constante de módulo
en `agent.py`): para comida, `interact` la come (mismo `eat_timer` que
comer del suelo) y `drop` la deja caer sobre una celda vacía. Añadir un
objeto llevable nuevo (no comida) es registrar su propio par
`(interact_fn, drop_fn)` en esa tabla —ambas devuelven `True` si el objeto
salió del inventario—; el cuerpo nunca hace casos especiales por tipo.
Madera y lanza son el primer caso real de esa extensión: `interact` sobre
madera cuenta como una interacción de fabricación (`WOOD_CRAFT_INTERACTIONS`
de ellas convierten la madera en lanza in situ, sin que salga nunca del
inventario) y `interact` sobre una lanza equipada no hace nada, porque su
bonus de daño es pasivo (ver [Depredadores](#depredadores)).

## Entradas de la red (17, normalizadas a [0,1])

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
| 11 | `pos_x`       | posición absoluta en el mundo, `x / GRID_COLS` (0-1) |
| 12 | `pos_y`       | posición absoluta en el mundo, `y / GRID_ROWS` (0-1) |
| 13 | `animal_dir_x` | dirección al animal más cercano, `(dx+1)/2`; 0.5 si no hay en rango |
| 14 | `animal_dir_y` | idem, eje Y |
| 15 | `animal_close` | `1 - min(dist / ANIMAL_SENSE_RANGE, 1)`; 0 si no hay animal en rango |
| 16 | `animal_danger` | 1.0 si el animal detectado es depredador, 0.0 si no o si no hay ninguno — verdad fundamental que da el mundo, no una inferencia del agente |

## Capa oculta (8 neuronas relu: 6 detectores legibles + 2 plásticas)

Cada una de las 6 primeras neuronas detecta una condición y su
significado está documentado en `config.py`:

- `h0 food_x` = relu(2·hunger + food_dir_x − 2)
- `h1 food_y` = relu(2·hunger + food_dir_y − 2)
- `h2 sleepy` = relu(0.70 − energy)
- `h3 night` = relu(night − 0.50)
- `h4 food_ahead` = relu(food_close − 0.20)
- `h5 carrying` = relu(has_food − 0.50)

`h0`/`h1` son las **compuertas de hambre**: solo se activan cuando el
agente tiene hambre suficiente *y* hay comida en esa mitad de plano, así
que un agente saciado no siente ningún tirón hacia la comida (deambula
solo con `noise`, "curiosidad"), mientras que uno hambriento persigue con
un tirón que crece con el hambre (0 por debajo de hambre ~0.5, ~0.4 a
0.7, 1.0 con hambre al máximo y comida justo delante). Comida detrás del
agente nunca dispara la compuerta, así que la persecución nunca empuja
hacia el lado equivocado.

`h6`/`h7` son **neuronas en blanco, sin significado hand-tuned**: todos
sus pesos entrantes y su bias nacen a 0 (`BRAIN_W_HIDDEN`/`BRAIN_B_HIDDEN`
en `config.py`), así que al nacer no aportan nada. Son el único par de
neuronas ocultas plástico en vida (ver `LEARNABLE_HIDDEN` más abajo), y
además de la mutación normal entre generaciones, es capacidad libre que
cada agente puede aprender a usar durante su propia vida.

## Salidas (8, sigmoid → [0,1])

| Salida       | Intención        | El cuerpo hace |
|--------------|------------------|----------------|
| `move_x`, `move_y` | dirección deseada (`2v−1 ∈ [−1,1]`) | avanzar a `AGENT_SPEED` celdas/s, con claims por eje; celda bloqueada → sostén pegajoso por eje (sin temblor) + re-sondeo cada `BLOCKED_PROBE_S`, o rodeo de `DETOUR_S` si la celda es una roca (ver Evitación de choques). El mapa no tiene borde: cruzar un extremo envuelve al lado opuesto (mundo toroidal, ver [Mundo](mundo.md)) |
| `eat`        | comer            | si `eat > EAT_OUTPUT_THRESHOLD` (0.5) y el agente está sobre comida → comer (celda se vacía, regrow) |
| `rest`       | descansar        | si `rest > REST_OUTPUT_THRESHOLD` (0.6) → no moverse y recuperar energía |
| `grab`       | recoger          | si `grab > GRAB_OUTPUT_THRESHOLD` (0.4) y hay comida, madera o una lanza tirada bajo el agente → pasa a su inventario (una ranura); la celda se vacía (mismo timer de regrow que comer, si el tipo regenera) pero el objeto se lleva, no se consume. El cuerpo ignora `grab` si el inventario está lleno. |
| `interact`   | usar lo llevado  | si `interact > INTERACT_OUTPUT_THRESHOLD` (0.4), hay algo en el inventario y el agente no está ya comiendo → dispatch por tipo de objeto; para comida, arranca el mismo `eat_timer` que comer del suelo y vacía el inventario; para madera, cuenta como una interacción de fabricación (`WOOD_CRAFT_INTERACTIONS` de ellas → lanza, ver arriba); para una lanza equipada, no hace nada. |
| `drop`       | soltar lo llevado | si `drop > DROP_OUTPUT_THRESHOLD` (0.4), hay algo en el inventario y la celda del agente está vacía → dispatch por tipo de objeto; para comida, madera o lanza, la deja en el suelo (`world.place_cell`) y vacía el inventario. |
| `attack`     | golpear un animal | si `attack > ATTACK_OUTPUT_THRESHOLD` (0.4) y el animal más cercano es un depredador a distancia ≤ 1 celda → le inflige `damage` (rasgo genético), multiplicado por `SPEAR_DAMAGE_MULT` si el agente lleva una lanza equipada (`inventory == CELL_SPEAR`); si el hp del animal llega a 0, muere. Ver [Depredadores](#depredadores). |

**Reflejo de supervivencia** (por debajo del cerebro, como en la biología):
si `hunger > HUNGER_CRITICAL` (0.85), el agente ignora `rest` y sigue
buscando comida.

## Ritmos de las necesidades

Sección `# --- Agents ---` de `config.py`, calibrados para un día de 60 s
reales (ciclo completo visible en ~2 min). Las necesidades son **regímenes
exclusivos** — o comes, o duermes, o estás activo, nunca dos a la vez:

| Régimen | Comportamiento |
| ------- | -------------- |
| Despierto | hambre sube a `HUNGER_RATE = 0.024`/s (~1 comida al día); energía se drena a `ENERGY_DRAIN_RATE = 0.016`/s (siestas reales a media mañana) |
| Descansando | energía recupera según una curva gaussiana asimétrica sobre el tiempo dormido *seguido* (`SLEEP_RECOVERY_*`, ver abajo), no a una tasa plana; hambre congelada (dormir congela la necesidad). Dormirse exige un mínimo de energía (`MIN_ENERGY_TO_REST = 0.50`: el agente exhausto no puede permitirse parar) y un descanso no se interrumpe hasta que la energía vuelve a `REST_WAKE_ENERGY = 0.60` (enclavamiento: sin él, la salida `rest` tiembla en el umbral y la siesta duraría un frame). Como la energía solo sube mientras se duerme, el mínimo solo compuerta el *inicio* de la siesta |
| De noche | todos duermen (luz < 0.5), a no ser que la hambre sea crítica |
| Comiendo | dura 2 s y baja la hambre 0.9; la comida reaparece a los 30 s (`RESOURCE_REGROW_S`) |

Estas son las tasas **base**: cada agente las multiplica por sus rasgos
hereditarios (ver Genética, `TRAIT_MIN`–`TRAIT_MAX`).

### Curva de recuperación del sueño

`ENERGY_REST_RATE` (plana) fue el origen de un problema real: como
cualquier fracción de segundo dormido ya sumaba energía a la tasa plana,
la evolución encontró que "dormir" milisegundos repetidamente para ir
sumando energía en microsiestas era una estrategia viable — nunca se
pagaba el coste real de parar a dormir. La solución (`sim/agent.py`,
`_sleep_recovery_rate`) es que la tasa de recuperación por segundo ya no
es constante: depende de `agent._sleep_timer`, el tiempo que el agente
lleva dormido *sin interrupción* (se reinicia en cuanto se despierta).
Sigue una campana gaussiana asimétrica, calibrada en `config.py`
(`SLEEP_RECOVERY_BASE_RATE`, `_PEAK_RATE`, `_PEAK_TIME`, `_SIGMA_RISE`,
`_SIGMA_FALL`):

- **Sueño ligero** (`t` cerca de 0): tasa casi nula (`SLEEP_RECOVERY_BASE_RATE`)
  — una siesta de un frame ya no recupera nada útil.
- **Sueño profundo** (`t` = `SLEEP_RECOVERY_PEAK_TIME`): pico de recuperación
  (`SLEEP_RECOVERY_PEAK_RATE`), alcanzado con una subida pronunciada
  (`SLEEP_RECOVERY_SIGMA_RISE` pequeño).
- **Después del pico**: la tasa baja de nuevo, pero despacio
  (`SLEEP_RECOVERY_SIGMA_FALL` >> `SIGMA_RISE`, cola larga a la derecha
  — de ahí que la campana quede "desplazada a la izquierda" dentro de su
  propio tramo), así que un descanso largo sigue recuperando energía en
  vez de estancarse en cero.

El multiplicador hereditario `rest_rate` (rasgo genético) escala la curva
entera (`agent.rest_rate_mult`), no una tasa plana.

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
  - Si la celda es una **roca** (nunca se libera, no merece la
    pena sondear — el mapa ya no tiene borde: los extremos envuelven, ver
    [Mundo](mundo.md)), arranca un rodeo de `DETOUR_S = 0.4` s
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

## Aprendizaje personal (no genético)

Además del genoma (ver [Genética](genetica.md)), cada agente aprende **en
vida** con una regla Hebbiana modulada por recompensa — sin backprop, sin
gradientes. `Brain.__init__` (`sim/brain.py`) copia en profundidad las
tablas del genoma: el `Brain` es dueño de sus propios pesos desde el
nacimiento, y `learn()` puede mutarlos sin tocar jamás el `Genome` que lo
construyó (lo único que `crossover`/`mutate` ven). **Lo aprendido vive y
muere con el agente: no se hereda.**

**El principio: se recompensa el resultado, no el acto.** La recompensa es
el hambre realmente saciada; la traza de elegibilidad, al durar segundos,
es la que reparte el crédito hacia atrás hasta el `grab` que hizo posible
esa comida. Así la cadena "recoger → llevar → comer" se aprende en vez de
estar cableada, y los exploits se cierran solos: dar vueltas recogiendo y
soltando comida no sacia nada, luego no paga nada.

### Las tres piezas

1. **Instinto** — `grab`/`interact`/`drop` nacen con pesos pequeños
   ajustados a mano que las acercan al umbral en el contexto correcto pero
   nunca lo cruzan solas: `grab` mira `h4` (comida debajo), `interact` mira
   `hunger` con un peso grande (compuerta de hambre nítida, alineada con el
   cruce ~0.53 de la fila `eat`) y `h5` (llevo algo), `drop` no tiene
   instinto ninguno.
2. **Exploración** — las tres filas tienen peso sobre la entrada `noise`
   ("balbuceo motor"): la acción se dispara de vez en cuando y por tanto
   puede ser reforzada. Es autolimitante, porque el peso del ruido es un
   peso más: lo que sale mal se castiga y baja. No añade ninguna tirada
   nueva del RNG (`noise` ya se sortea una vez por `_inputs()`), así que el
   determinismo no se toca.
3. **Refuerzo** — la escalera de recompensas hace crecer los pesos de señal
   real hasta que dominan al ruido.

### La escalera de recompensas

Cada peldaño responde a "¿qué necesidad se satisfizo?", nunca a "¿qué
acción se ejecutó?":

| Peldaño | Cuándo |
| --- | --- |
| `REWARD_EAT_K` × hambre saciada | comer, venga del suelo o del inventario |
| × `REWARD_INVENTORY_MEAL_MULT` | la comida venía del inventario y se llevó al menos `CARRY_BONUS_MIN_S`: eso es previsión |
| `REWARD_GRAB` (pequeño) | recoger comida *que creció en el mundo*: es una inversión, no un pago |
| `PENALTY_DROP_HUNGRY` | soltar comida con `hunger > HUNGER_WARNING`: desperdicio |
| `PENALTY_STARVING_WITH_FOOD` (por segundo) | `hunger > HUNGER_CRITICAL` **llevando comida encima** |

Comer domina por diseño: una comida entera sacia hasta 0.9 de hambre, o sea
paga ~2.7 (~4.0 desde el inventario) frente a los 0.15 de recoger. Recoger
nunca puede volverse un fin en sí mismo.

`PENALTY_STARVING_WITH_FOOD` **no** es el castigo por hambre que se retiró
en su día: exige llevar comida en el inventario. Aquel castigaba también al
agente que iba de camino a la comida sin haber llegado —empujando los pesos
en contra del comportamiento que sí funcionaba—, y ese agente tiene el
inventario vacío, así que nunca lo cobra. Aquí solo se castiga a quien
lleva la solución encima y no la usa.

Dos agujeros de *reward hacking* cerrados explícitamente, de la misma
familia que las microsiestas que cerró la curva del sueño:

- **`grab` → `drop` → `grab`.** Soltar deja la comida bajo los pies del que
  la soltó, o sea inmediatamente re-agarrable. `World.dropped_cells` marca
  la comida que puso un agente: recogerla no paga nada.
- **Recoger y soltar en bucle de un frame.** `CARRY_MIN_S`: no puedes
  soltar lo que acabas de coger, ni cobras el extra de previsión por una
  comida que no llegaste a llevar. Es el mismo enclavamiento del cuerpo que
  `REST_WAKE_ENERGY`, y por la misma razón: una salida que ronda su umbral
  produce parpadeo de un frame en vez de conducta. Medido sin él, la
  mediana de tiempo en el inventario era de **0.10 s** y los agentes
  recogían y soltaban comida 50 veces por cada vez que comían. El valor
  concreto importa: a 1 s hay mucho trasiego, a 3 s baja un 64 % *y* suben
  las comidas del inventario, y a 6 s la población se hunde porque bloquear
  tanto tiempo la única ranura impide recoger lo que sí hace falta.

### Qué es plástico y qué es instinto

**La evolución cambia los sentidos; la vida cambia qué haces con ellos.**
Solo las filas `grab`/`interact`/`drop` (`LEARNABLE_OUTPUTS`) aprenden en
vida en la capa de salida. `move_x`, `move_y`, `eat`, `rest` y las 6
primeras neuronas ocultas (`h0`-`h5`) son instinto: solo la mutación las
toca, entre generaciones.

No es purismo, es una necesidad. Una recompensa escalar única no puede
decir *qué* fila se la ganó, así que sin esta separación la recompensa por
comida reescribe circuitos que no tienen nada que ver. Medido antes de
existir: el aprendizaje le escribió un peso sobre `noise` a la fila `rest`
—cuyas entradas son por lo demás constantes— y el sueño de un agente empezó
a parpadear frame a frame justo en su umbral; dejó de dormir de noche con
el estómago lleno. Los márgenes afinados a mano (el peso ×20 del hambre en
`eat`, el 8.0 de la noche en `rest`) existen precisamente para sobrevivir a
la deriva: dejar que una señal hebbiana difusa los erosione destruye justo
lo que protegen.

**`LEARNABLE_CELLS` añade plasticidad de grano fino**, celda a celda
(`fila, columna`) en vez de fila completa: `move_x`, `move_y` y `attack`
siguen siendo instinto para todo lo demás (comida, otros agentes), pero
sus 4 columnas de animal (`animal_dir_x/y`, `animal_close`,
`animal_danger`) sí aprenden en vida — nada de esas 12 celdas se afina a
mano, arrancan en 0 y las moldea `PENALTY_ANIMAL_DAMAGE_K` (ver
[Depredadores](#depredadores)). El mismo mecanismo también cubre las
columnas de `h6`/`h7` en `w_out`, para las 8 filas de salida (las 3 que
ya son plásticas por fila completa lo heredan gratis; las otras 5 se
añaden aquí) — así lo que `h6`/`h7` aprenden a detectar puede
propagarse a cualquier salida, no solo a `grab`/`interact`/`drop`.
`Brain.learn()` aplica esta selección en un segundo bucle, independiente
de `LEARNABLE_OUTPUTS`.

**`LEARNABLE_HIDDEN = (6, 7)`** es la plasticidad simétrica del lado de
entrada: los pesos entrantes (input→hidden) de `h6`/`h7` también
aprenden en vida, con la misma regla hebbiana modulada por recompensa
que la capa de salida (`Brain._elig_w_hidden`/`_elig_b_hidden`, misma
`LEARNING_RATE`/`ELIGIBILITY_TAU_S`/`BASELINE_TAU_S`). `h0`-`h5` nunca
pasan por este bucle. Como `h6`/`h7` nacen con peso y bias en 0 (relu
muerta: activación constante 0, sin desviación de su propia línea base
que acreditar), no aprenden nada en vida hasta que una mutación les da
algún peso de entrada — a partir de ahí, la plasticidad en vida puede
seguir moldeándolas.

### La traza de elegibilidad

`w += LEARNING_RATE * reward * elegibilidad`, clampeado igual que los pesos
genéticos; `reward == 0.0` (el caso común) es un no-op. La traza tiene tres
propiedades, cada una arreglando una forma concreta en que esta regla se
tuerce:

- Es una **media móvil**, no una suma. La suma saturaba en 10× el producto
  pre×post, y habría saturado en 120× con un tau lo bastante largo para
  acreditar un `grab` por una comida que llega segundos después.
- Decae **por segundo** (`ELIGIBILITY_TAU_S`), no por tick. La constante por
  tick acoplaba en silencio la dinámica del aprendizaje a los FPS y al
  multiplicador de velocidad.
- Acredita la **desviación** de cada neurona respecto a su propia línea base
  (`BASELINE_TAU_S`), no su activación bruta. Ésta es la que más importa:
  como la activación nunca es negativa, cualquier recompensa reforzaba toda
  salida activa —y los biases más que nadie, porque su entrada es siempre
  1—. Medido en la primera calibración: la fila `drop`, a la que ninguna
  recompensa se refiere, pasó de una tasa de disparo del 0.2 % al 13 % en
  cuatro minutos simulados solo por esa deriva, los agentes se dedicaron a
  recoger y soltar comida sin parar, y la población se extinguió. Acreditar
  la desviación significa que una neurona en su valor de siempre no gana
  nada, y solo responde la que de verdad hizo algo inusual.

Constantes en `config.py`, sección `# --- Reinforcement learning ---`.

## Depredadores

Los animales (`sim/animal.py`, `world.animals`) son entidades scripted —
sin red ni genoma propios, siguiendo el patrón de
[`docs/arquitectura.md`](arquitectura.md) para añadir una entidad nueva.
Deambulan por defecto; si un agente vivo entra en `ANIMAL_DETECT_RANGE`,
lo persiguen (`ANIMAL_SPEED`, más lento que `AGENT_SPEED` a propósito) y
lo golpean por `ANIMAL_DAMAGE` al contacto, con cooldown `ATTACK_COOLDOWN_S`.

El agente, por su parte, tiene dos rasgos genéticos nuevos: `hp` (escala
`BASE_AGENT_HP`, vida real — a 0 el agente muere, mismo flujo diferido que
el resto de muertes) y `damage` (escala `BASE_AGENT_DAMAGE`, lo que
inflige su propia salida `attack`). Sensa animales con `_animal_dir()`
(calcado de `_other_agent()`, pero devuelve el objeto para poder atacarlo)
dentro de `ANIMAL_SENSE_RANGE`.

**Nada de esto está cableado a mano en la respuesta del agente**: huir,
ignorar o atacar es enteramente aprendido en vida (ver `LEARNABLE_CELLS`
arriba) a partir de `PENALTY_ANIMAL_DAMAGE_K` — el único término de reward
nuevo, proporcional a `hp perdido / hp_max` este tick. No hay recompensa
por golpear a propósito: la traza de elegibilidad ya correlaciona
`attack`/`move_x`/`move_y` con su propia desviación, así que basta con
castigar el daño recibido.

Densidad y presión ajustables en `config.py` `# --- Animals (predators)
---`: bajarlas si la población se extingue, subirlas si nunca hay presión
real. Los animales no se reproducen — `ANIMAL_RESPAWN_S` repone bajas
cuando la cuenta cae por debajo de `ANIMAL_SPAWN_COUNT`.

## El inspector (`sim/inspector.py`)

Clic izquierdo sobre un agente en la ventana principal (radio de selección
`INSPECTOR_CLICK_RADIUS`) lo selecciona: un anillo lo marca en el mundo
(`COLOR_SELECTED_OUTLINE`) y una **segunda ventana OS** (soporte
multi-ventana de pygame 2 / SDL2, `loop.py` la crea con
`create_inspector_window()`) dibuja en vivo, tick a tick:

- barras de `hunger`/`energy`/`hp`, generación, edad y estado;
- el grafo completo de la red — 17 entradas, 8 ocultas, 8 salidas,
  coloreado por activación: el inspector lee `Brain._last_hidden`/
  `_last_outputs`, que `forward()` ya guarda cada tick, en vez de volver
  a calcular nada — así abrir el inspector no acelera el aprendizaje
  (ni la traza de elegibilidad) del agente inspeccionado;
- los seis umbrales de salida (`eat`/`rest`/`grab`/`interact`/`drop`/`attack`)
  junto a su valor crudo.

Si el agente seleccionado muere, la selección se limpia sola. La ventana
es redimensionable; `loop.py` reescala la superficie offscreen en
`WINDOWRESIZED`.

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
- **Afinar el aprendizaje personal** → `LEARNING_RATE`,
  `ELIGIBILITY_TAU_S`, `BASELINE_TAU_S` y la escalera de recompensas
  (`REWARD_EAT_K`, `REWARD_INVENTORY_MEAL_MULT`, `REWARD_GRAB`,
  `PENALTY_*`), sección `# --- Reinforcement learning ---`.
- **Hacer plástica otra conducta** → añadir su índice de fila a
  `LEARNABLE_OUTPUTS`. Piénsalo dos veces con las filas afinadas a mano: sus
  márgenes están calculados para sobrevivir a la mutación, no a un gradiente
  hebbiano difuso.
- **Hacer plástica solo una columna, no la fila entera** → añadir el par
  `(fila, columna)` a `LEARNABLE_CELLS` en vez de la fila completa a
  `LEARNABLE_OUTPUTS` (así lo hacen las 4 señales de animal en
  `move_x`/`move_y`/`attack`).
- **Afinar cuánto exploran** → el peso de la columna `noise` (12) en las
  filas `grab`/`interact`/`drop` de `BRAIN_W_OUT`, y sus biases: juntos
  fijan la tasa de disparo de cada fila (la aritmética está en el comentario
  de `config.py`).
- **Lo inviolable** no se edita: lo garantiza el cuerpo (`sim/agent.py`).
