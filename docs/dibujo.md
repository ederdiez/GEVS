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

> **Nota técnica:** el HUD se dibuja con `pygame._freetype` en lugar de
> `pygame.font`. El wheel de pygame 2.6.1 para Python 3.14 no incluye la
> extensión C de `font` (ni `imageext` ni `mixer`), y su fallback en Python
> puro muere por un import circular entre `font.py` y `sysfont.py`. El motor
> real que sí funciona es `pygame._freetype`; el HUD lo usa directamente con
> la misma fuente integrada.
