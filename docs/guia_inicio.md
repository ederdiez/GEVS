# Guía de inicio

## Instalación (una sola vez)

```bash
cd ~/programas/gevs_ia

# 1. Crear el entorno virtual
python3 -m venv .venv

# 2. Instalar dependencias
.venv/bin/pip install -r requirements.txt
```

## Ejecutar

```bash
.venv/bin/python main.py
```

Se abren dos ventanas: la principal (800×600) con un mundo de celdas
(rocas en gris, madera en marrón, recursos en verde), un ciclo día/noche
de 60 segundos y agentes circulares que deambulan de día, comen al
encontrar comida y duermen de noche (su comportamiento sale de una red
neuronal; los colores se explican en el `README`); y una ventana
**inspector**, vacía hasta que haces clic sobre un agente en la principal
— entonces muestra su red neuronal en vivo (ver
[Agentes → El inspector](agentes.md)). El mundo no tiene bordes: un
agente que cruza un extremo aparece por el lado opuesto. Para salir,
cierra la ventana principal (botón X) o pulsa `Ctrl+C` en la terminal.

## Problemas comunes

### `ModuleNotFoundError: No module named 'pygame'`

El venv no tiene las dependencias instaladas. Vuelve a ejecutar
`.venv/bin/pip install -r requirements.txt`.

### La ventana no se abre

- Asegúrate de tener un entorno gráfico activo (no basta con una sesión
  solo-terminal).
- Si usas SSH, prueba `ssh -X` o `ssh -Y`.

### Error al cargar `pygame.font` (`partially initialized module`)

Con **Python 3.14**, el wheel de pygame 2.6.1 no incluye la extensión C de
`font` (ni `imageext` ni `mixer`), y su fallback en Python puro falla con
un import circular entre `font.py` y `sysfont.py`. El HUD del proyecto ya
evita `pygame.font` y usa `pygame._freetype` directamente, así que el juego
funciona igual; solo fallarías si algún módulo nuevo importase
`pygame.font` o `pygame.freetype`. Si algún día hacen falta (por ejemplo
`pygame.mixer` para sonido), la solución es recompilar pygame con las
bibliotecas SDL completas (`pacman -S sdl2_ttf sdl2_image sdl2_mixer` y
`.venv/bin/pip install --force-reinstall --no-binary pygame pygame`).

### Quiero cambiar el tamaño o los colores

Abre `sim/config.py` y edita `WINDOW_WIDTH`, `WINDOW_HEIGHT`,
`COLOR_FLOOR_DAY`, `COLOR_CELL_ROCK`, etc. Todo lo ajustable está ahí.
