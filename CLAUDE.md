# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Qué es

GEVS IA: simulación visual de sociedades inteligentes (Python + pygame,
mundo 2D toroidal, agentes controlados íntegramente por una red neuronal
propia por individuo, con genética/reproducción sexual y aprendizaje
Hebbiano en vida). La documentación completa y actualizada vive en
`docs/` — léela antes de tocar código, especialmente
[`docs/arquitectura.md`](docs/arquitectura.md) (mapa de módulos y flujo)
y la tabla "Cómo editar cada cosa" que contiene.

## Comandos

```bash
# Setup (una sola vez)
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# Ejecutar la simulación (abre ventana principal + ventana inspector)
.venv/bin/python main.py
```

No hay linter/formatter ni framework de tests configurado (no pytest, no
ruff, no mypy).

## Arquitectura

Todo el estado y comportamiento vive en `sim/`; `main.py` solo crea la
ventana y arranca `loop.run()`. Módulos, por responsabilidad única:

| Módulo | Responsabilidad |
| --- | --- |
| `sim/config.py` | **Toda** constante editable: tamaño, FPS, colores, densidades, ritmos, umbrales, y las matrices de pesos afinadas a mano de la red. Nada de números mágicos en el resto del código. |
| `sim/world.py` | Lógica pura del mundo (sin pygame, testeable headless): grid toroidal, reloj día/noche, comida, claims de celda, nacimientos/muertes diferidos. |
| `sim/agent.py` | El cuerpo del agente: ejecuta las intenciones del cerebro garantizando lo inviolable (no atravesar rocas, no pisar una claim ajena, comer solo con comida debajo...). Construye las 11 entradas de la red en `_inputs()`. |
| `sim/brain.py` | MLP en Python puro (11→6→7) + aprendizaje Hebbiano personal (`learn()`, traza de elegibilidad, no heredable). |
| `sim/genetics.py` | El genoma (pesos + 6 rasgos hereditarios): crossover, mutación, clon. Única unidad de herencia. |
| `sim/drawing.py` | Una función de dibujo por capa/elemento, llamadas en orden fijo desde `loop.py`. |
| `sim/inspector.py` | Segunda ventana OS: red neuronal en vivo del agente seleccionado. |
| `sim/loop.py` | Bucle principal: eventos → `world.update` + `agent.update`/`brain.learn` por agente → `world.end_frame()` → dibujar → inspector. |

Flujo por frame (`loop.py`): eventos → `world.update(dt)` (reloj + regrow)
→ por cada agente `brain.forward()` + cuerpo (mover/comer/descansar/
aparearse) + `brain.learn(reward)` → `world.end_frame()` (materializa
muertes y nacimientos diferidos; nunca se muta `entities` a mitad del
bucle) → 5 capas de dibujo → inspector.

**Patrón "el cerebro propone, el cuerpo ejecuta":** la red nunca puede
romper la simulación porque el cuerpo (`agent.py`) es quien decide
físicamente qué se permite. Al añadir comportamiento nuevo, sigue este
patrón: intención en la red (o entrada nueva en `_inputs()` + columna en
las matrices de `config.py`), ejecución/validación en el cuerpo.

**Determinismo:** todo el azar (spawn, ruido inicial del genoma,
crossover, mutación, ruido de la red) sale de `world.rng`, sembrado por
`WORLD_SEED`. Misma semilla → misma trayectoria evolutiva byte a byte;
ambos tests headless lo verifican pisando dos mundos lado a lado. Al
tocar cualquier cosa que use aleatoriedad, usa siempre `world.rng`, nunca
`random` global.

**Mundo toroidal:** el grid no tiene borde — toda consulta de celda o
movimiento pasa por `World.wrap(x, y)` (`x % cols, y % rows`). Al añadir
código que calcule posiciones o distancias, envuelve las coordenadas o
usa distancias que ya lo hagan (ver `docs/mundo.md`).

## Convenciones del proyecto

- **Un archivo, una responsabilidad**; si un archivo crece demasiado, se
  divide.
- **Nada de números mágicos**: todo lo configurable va a `sim/config.py`.
- **Código en inglés, documentación en español** (`docs/`, comentarios de
  alto nivel).
- Al añadir una entidad/módulo nuevo al mundo, el patrón está descrito en
  `docs/arquitectura.md` → "Cómo añadir algo nuevo".
- Actualiza `docs/` junto con cualquier cambio de comportamiento —la
  documentación se mantiene viva y es la fuente de verdad más detallada,
  más que este archivo.
