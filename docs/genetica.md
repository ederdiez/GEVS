# Genética y reproducción

Cada agente posee su propio **genoma** (`sim/genetics.py`): las tablas de
pesos del cerebro más 8 **rasgos del cuerpo** — velocidad, rango de
percepción de comida, ritmos de hambre/energía/comer/descansar, y `damage`/
`hp` (daño propio y vida máxima, ver [Agentes → Depredadores](agentes.md))
— que multiplican las tasas base de `config.py`. La población inicial nace de
las tablas afinadas ± ruido pequeño (`INITIAL_WEIGHT_NOISE`,
`INITIAL_TRAIT_NOISE`).

El genoma es la **única unidad de herencia**: crossover, mutación y clon
operan solo sobre él. `Genome.build_brain()` construye un `Brain` que
**copia en profundidad** esas tablas: el `Brain` es dueño de pesos propios
desde el nacimiento, así que el aprendizaje personal en vida (Hebbiano,
ver [Agentes → Aprendizaje personal](agentes.md)) puede ajustarlos sin
tocar jamás el genoma. `crossover`/`mutate` siguen siendo puros (devuelven
un genoma nuevo, nunca tocan al padre) — lo aprendido en vida no se
hereda, solo el genoma.

## Herencia (sexual por encuentro)

Dos agentes elegibles (energía ≥ `MATE_ENERGY_THRESHOLD`, hambre ≤
`MATE_HUNGER_MAX`, fuera de cooldown) a distancia Manhattan ≤ `MATE_RANGE`
(5 celdas)
se buscan mutuamente: el reflejo de pareja vive en el **cuerpo** y
sobreescribe la evitación de la red — el mismo patrón "cuerpo inviolable"
que el food rush, sin tocar la topología 17→6→8 ni los pesos afinados (la
**entrada 9 del cerebro sigue reservada**). A distancia 1 se aparean:

1. Cada padre paga `MATE_ENERGY_COST` y ambos entran en `MATE_COOLDOWN_S`
   (el primer apareamiento de un frame fija el cooldown de ambos, así que
   una pareja nunca produce doble nacimiento).
2. El hijo hereda por **crossover uniforme por gen** (p = 0.5) +
   **mutación** — pesos: aditiva gaussiana con clamp; rasgos: log-normal
   (mantiene la positividad), ambos clampeados a sus límites.
3. El vector hacia la pareja se **normaliza** por distancia Manhattan: un
   delta crudo de 2 celdas por sub-paso violaría el invariante
   `AGENT_STEP_S · speed < 1` y saltaría claims.

## El nacimiento

- El hijo se coloca en una celda libre adyacente (orden fijo y
  determinista: 4-vecindad primero, luego diagonales) con
  `CHILD_INITIAL_HUNGER`/`CHILD_INITIAL_ENERGY`, `generation = max(padres)
  + 1`, sus `parents` registrados y su propio cooldown de "infancia"
  (también una mitigación barata del incesto padre-hijo).
- Si no hay celda libre o la población está en `MAX_POPULATION`, el
  apareamiento aborta sin coste ni cooldown y el reflejo reintenta solo
  mientras sigan adyacentes.

## Muerte

`hunger ≥ 1.0`, `energy ≤ 0.0`, `age ≥ MAX_AGE_S` (300 s, 5 días
simulados) o `hp ≤ 0.0` (matado por un depredador, ver [Agentes →
Depredadores](agentes.md)). `world.kill()` marca la
baja y libera la claim al instante; la remoción de `entities` se materializa
en `world.end_frame()` — nunca se muta la lista en medio del bucle de
agentes (`loop.py` llama a `end_frame` tras el bucle; los tests hacen lo
mismo). Las bajas se procesan antes que los nacimientos; si el spot del
nacimiento se escapó entre `mate()` y `end_frame`, se re-busca y, si no
queda sitio, se descarta el nacimiento (raro, documentado).

## Determinismo

Todo el azar — ruido inicial, crossover, mutación y el noise del cerebro —
sale del `rng` del mundo, así que una semilla reproduce la misma trayectoria
evolutiva.
