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
    ├── config.py        # ★ TODAS las constantes editables (tamaño, FPS, colores).
    ├── window.py        # Crea la ventana de pygame.
    ├── drawing.py       # Funciones de dibujo (una función por elemento).
    └── loop.py          # Bucle principal: eventos → actualizar → dibujar.
```

## Flujo de ejecución

```
main.py
  └─ window.create_window()   →  crea la ventana
  └─ loop.run(screen)         →  bucle infinito:
        1. eventos (cerrar ventana...)
        2. actualizar el mundo   ← aquí entrarán los agentes
        3. dibujar               ← dibujo.py
        4. esperar al próximo frame (FPS)
```

## Cómo editar cada cosa

| Quiero cambiar...        | Dónde                                   |
| ------------------------ | --------------------------------------- |
| Tamaño de ventana, FPS, colores | `sim/config.py` (solo constantes). |
| Título de la ventana     | `WINDOW_TITLE` en `sim/config.py`.      |
| Cómo se dibuja algo      | `sim/drawing.py` (añade una función).   |
| Qué hace el bucle        | `sim/loop.py`.                          |
| Qué módulos se cargan    | `main.py`.                              |

## Cómo añadir algo nuevo (ejemplo: agentes)

1. Crea `sim/agent.py` con la clase `Agent` (posición, estado, método `update`).
2. Crea `sim/world.py` con el mundo (lista de agentes, método `update`).
3. En `loop.py`, sustituye el paso 2 (`# Update the world`) por
   `world.update()`.
4. En `drawing.py`, añade `draw_agents(screen, world)` y llámala en el
   paso 3 del bucle.
5. Actualiza `docs/` para reflejar los módulos nuevos.

## Reglas informales del proyecto

- **Un archivo, una responsabilidad.** Si un archivo crece demasiado,
  divídelo.
- **Nada de números mágicos en el código.** Todo número configurable va a
  `config.py`.
- **Código en inglés, documentación en español.**
