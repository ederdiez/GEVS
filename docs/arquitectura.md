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
    ├── config.py        # ★ TODAS las constantes editables (tamaño, FPS, colores, pesos de la red...).
    ├── window.py        # Crea la ventana de pygame.
    ├── world.py         # Lógica pura del mundo: grid + reloj + comida + claims + nacimientos/muertes (sin pygame).
    ├── agent.py         # El agente: cuerpo que ejecuta las intenciones del cerebro.
    ├── brain.py         # MLP pura en Python: forward de la red + aprendizaje Hebbiano personal (learn()).
    ├── genetics.py      # Genoma: pesos del cerebro + rasgos del cuerpo; crossover, mutación, clon.
    ├── drawing.py       # Funciones de dibujo (una función por elemento).
    ├── inspector.py     # Ventana secundaria: red neuronal de un agente en vivo (clic para seleccionar).
    └── loop.py          # Bucle principal: eventos → actualizar → dibujar (+ ventana del inspector).
```

## Flujo de ejecución

```
main.py
  └─ window.create_window()   →  crea la ventana principal
  └─ loop.run(screen)         →  crea la ventana del inspector, luego bucle infinito:
        1. eventos (cerrar ventana, clic → seleccionar agente, resize del
           inspector, +/- → cambia el multiplicador de velocidad...)
        2. world.update(dt)   →  reloj + regrow de comida
           + cada agente: brain.forward(inputs, dt) (+ traza de elegibilidad)
             + cuerpo (movimiento, comer, descansar, recoger/usar/soltar el
             inventario, aparearse) + brain.learn(reward)
           + world.end_frame() → materializa las muertes y nacimientos diferidos
           — este paso se repite `speed` veces por frame dibujado (ver
           "Velocidad de simulación" abajo)
        3. dibujar            ← drawing.py (5 capas, en orden) en la ventana principal
        4. inspector.draw_inspector() → red del agente seleccionado, en su propia ventana
        5. esperar al próximo frame (FPS)
```

## Velocidad de simulación (fast-forward)

Las teclas `+`/`-` cambian un multiplicador de velocidad (`sim/loop.py`,
opciones en `config.SPEED_LEVELS`, x1 por defecto). En vez de escalar
`dt`, cada frame dibujado repite el paso 2 completo (`world.update` +
`agent.update` por agente + `world.end_frame()`) `speed` veces con el
mismo `dt` real, y solo se dibuja una vez al final. Así el tiempo
simulado avanza más rápido en tiempo real sin tocar el sub-stepping de
movimiento (`AGENT_STEP_S`) ni el determinismo (mismo `dt` por paso,
mismo `world.rng`). El HUD muestra "Velocidad: x{n}" cuando no es x1.

## Cómo editar cada cosa

| Quiero cambiar...        | Dónde                                   |
| ------------------------ | --------------------------------------- |
| Tamaño de ventana, FPS, colores | `sim/config.py` (solo constantes). |
| Título de la ventana     | `WINDOW_TITLE` en `sim/config.py`.      |
| Densidad de rocas/madera/comida | `ROCK_DENSITY` / `WOOD_DENSITY` / `RESOURCE_DENSITY` en `sim/config.py`. |
| Duración del día         | `DAY_LENGTH_S` en `sim/config.py`.      |
| Horas de amanecer/anochecer | `DAWN_START`…`DUSK_END` en `sim/config.py`. |
| Número de agentes, velocidad, ritmos de hambre/energía | sección `# --- Agents ---` en `sim/config.py`. |
| Evitación: rango del sensor, re-sondeo y rodeo de rocas | `AGENT_SENSE_RANGE` / `BLOCKED_PROBE_S` / `DETOUR_S` en `sim/config.py`. |
| El comportamiento de los agentes (pesos de la red) | matrices de la sección `# --- Brain ---` en `sim/config.py`. |
| Genética (ruido inicial, mutación, clamps) | sección `# --- Genetics ---` en `sim/config.py`. |
| Aprendizaje personal (tasa, decaimiento, recompensa) | sección `# --- Reinforcement learning ---` en `sim/config.py` y `Brain.learn()` en `sim/brain.py`. |
| Reproducción (umbrales, cooldown, coste, rango) | sección `# --- Reproduction ---` en `sim/config.py`. |
| Muerte y tope de población | `MAX_AGE_S` / `MAX_POPULATION` en `sim/config.py`. |
| El genoma (crossover/mutación/clon) | `sim/genetics.py`.                    |
| Lo que un agente puede/cómo se mueve | `sim/agent.py` (el cuerpo).         |
| Las señales que la red recibe | `Agent._inputs()` en `sim/agent.py`. |
| Cómo se dibuja algo      | `sim/drawing.py` (añade una función).   |
| La ventana del inspector | `sim/inspector.py` (colores en `config.py`, sección `# --- Inspector ---`). |
| Qué hace el bucle        | `sim/loop.py`.                          |
| Multiplicadores de velocidad (fast-forward) | `SPEED_LEVELS` en `sim/config.py`; teclas en `sim/loop.py`. |
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

## Índice de módulos

| Documento | Contenido |
| --------- | --------- |
| [Mundo](mundo.md) | Grid, tipos de celda, reloj y API de `sim/world.py`. |
| [Agentes](agentes.md) | Cerebro NN, entradas/salidas, ritmos, evitación de choques. |
| [Genética](genetica.md) | Genoma, herencia, nacimiento, muerte, determinismo. |
| [Dibujo](dibujo.md) | Capas de dibujo, colores de agentes y HUD. |
