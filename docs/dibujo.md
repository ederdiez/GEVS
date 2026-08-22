# El dibujo (`sim/drawing.py`)

Una función por elemento, y el bucle las llama en este orden (importa):

1. `draw_background` — suelo, con color interpolado según la hora.
2. `draw_world` — rocas, madera y recursos (celdas no vacías).
3. `draw_agents` — un círculo por agente (color según estado):

   | Color | Estado |
   | ----- | ------ |
   | verde | comiendo |
   | azul | descansando |
   | naranja | hambriento (activo con hambre) |
   | magenta | cooldown de apareamiento (recién apareado o recién nacido) |
   | gris | activo, sin hambre |

   Un agente que lleva un recurso en su inventario muestra un punto pequeño
   sobre la cabeza en el color de su recurso (comida: verde) con borde
   oscuro. El agente seleccionado para el inspector (clic, ver
   [Agentes → El inspector](agentes.md)) recibe un anillo
   (`COLOR_SELECTED_OUTLINE`).
4. `draw_animals` — un cuadrado por animal (`COLOR_ANIMAL`), a propósito
   distinto de los círculos de los agentes — ver [Agentes →
   Depredadores](agentes.md).
5. `draw_night_overlay` — oscurece el mundo de noche (surface translúcida);
   agentes y animales se oscurecen con el mundo (dormidos/activos de
   noche, coherente).
6. `draw_hud` — "Día N  HH:MM" y "Población: N  †muertes  +nacimientos"
   (siempre legible, encima del overlay).

> **Perspectiva:** la vista es top-down pura (el mundo se ve desde arriba),
> así que no hay cielo: la luz del día se transmite solo con la
> interpolación de colores y el overlay nocturno.

> **Ventana del inspector:** es una segunda ventana OS, independiente de
> estas 5 capas — `sim/inspector.py` la dibuja aparte (ver
> [Agentes → El inspector](agentes.md)).

## La cámara (`sim/camera.py`)

El grid (120×90 celdas) es más grande que la ventana (800×600 px), así
que `Camera` (lógica pura, sin pygame) traduce coordenadas de celda a
píxel de pantalla con un desplazamiento (`x`, `y`, en píxeles de mundo) y
un zoom: `screen = (celda * CELL_SIZE - offset) * zoom`. Cada función de
dibujo que coloca algo en el mundo (`draw_world`, `draw_agents`,
`draw_animals`) recibe la cámara y la usa para convertir; las tres
además hacen *culling* con `camera.visible_cell_range()` — `draw_world`
solo recorre esas celdas, y `draw_agents`/`draw_animals` se saltan
(sin llamar a `pygame.draw`) cualquier agente/animal fuera de ese
rango (más 1 celda de margen para el radio/anillo) — así que el coste
de dibujar no crece con el tamaño del mundo ni con la población fuera
de pantalla. El HUD y el overlay nocturno son en espacio de pantalla,
no la usan.

Controles (`sim/loop.py`):

- **Rueda del ratón** — zoom, centrado en el cursor (`CAMERA_ZOOM_MIN/MAX/STEP`
  en `config.py`).
- **WASD / flechas** — pan continuo mientras se mantiene pulsada
  (`CAMERA_PAN_SPEED`).

`Camera._clamp()` evita que la vista se salga del grid; si el zoom es lo
bastante bajo para que la ventana entera del mundo quepa en pantalla, se
centra en vez de pegarse a un borde. La selección de agente por clic
(`loop._pick_agent`) convierte el píxel de clic a coordenadas de celda
con `camera.to_world` antes de buscar el agente más cercano.

> **Nota técnica:** el HUD se dibuja con `pygame._freetype` en lugar de
> `pygame.font`. El wheel de pygame 2.6.1 para Python 3.14 no incluye la
> extensión C de `font` (ni `imageext` ni `mixer`), y su fallback en Python
> puro muere por un import circular entre `font.py` y `sysfont.py`. El motor
> real que sí funciona es `pygame._freetype`; el HUD lo usa directamente con
> la misma fuente integrada.
