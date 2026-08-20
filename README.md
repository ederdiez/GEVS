# GEVS IA — Simulación de Sociedades Inteligentes

Simulación visual de sociedades inteligentes construida con **Python + pygame**.
El objetivo a largo plazo es simular agentes que interactúan entre sí y
forman estructuras sociales emergentes.

**Estado actual:** mundo 2D con grid en vista top-down (rocas y recursos
generados por semilla fija), ciclo día/noche con iluminación variable
(HUD con hora) y **14 agentes cuyo comportamiento completo sale de una red
neuronal** (MLP afinada a mano en `sim/config.py`): deambulan, comen con
hambre, duermen de noche y se apartan al encontrarse (sin temblores contra
rocas ni vecinos).

Leyenda de colores de los agentes:

| Color | Estado |
| ----- | ------ |
| 🟢 verde   | comiendo |
| 🔵 azul    | descansando / durmiendo |
| 🟠 naranja | activo y con hambre |
| ⚪ gris    | activo, sin hambre |

## Requisitos

- Python 3.12+
- pygame (ver `requirements.txt`)

## Ejecutar

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python main.py
```

## Documentación

Toda la documentación vive en [`docs/`](docs/index.md):

- [`docs/guia_inicio.md`](docs/guia_inicio.md) — instalación y ejecución.
- [`docs/arquitectura.md`](docs/arquitectura.md) — estructura del código y cómo editarlo.
