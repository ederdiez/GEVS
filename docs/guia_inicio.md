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

Se abre una ventana oscura de 800×600. Para salir, cierra la ventana
(botón X) o pulsa `Ctrl+C` en la terminal.

## Problemas comunes

### `ModuleNotFoundError: No module named 'pygame'`

El venv no tiene las dependencias instaladas. Vuelve a ejecutar
`.venv/bin/pip install -r requirements.txt`.

### La ventana no se abre

- Asegúrate de tener un entorno gráfico activo (no basta con una sesión
  solo-terminal).
- Si usas SSH, prueba `ssh -X` o `ssh -Y`.

### Quiero cambiar el tamaño o los colores

Abre `sim/config.py` y edita `WINDOW_WIDTH`, `WINDOW_HEIGHT`,
`COLOR_BACKGROUND`, etc. Todo lo ajustable está ahí.
