# GEVS IA — Simulación de Sociedades Inteligentes

Simulación visual de sociedades inteligentes construida con **Python + pygame**.
El objetivo a largo plazo es simular agentes que interactúan entre sí y
forman estructuras sociales emergentes.

**Estado actual:** mundo 2D con grid en vista top-down (rocas y recursos
generados por semilla fija), ciclo día/noche con iluminación variable
(HUD con hora y población) y agentes cuyo comportamiento completo sale de
una red neuronal **propia por individuo** (cada agente tiene su genoma:
pesos de la red + rasgos físicos hereditarios). Deambulan, comen con
hambre, duermen de noche y se apartan al encontrarse (sin temblores contra
rocas ni vecinos). **Nacen, se reproducen y mueren**: dos agentes con
energía suficiente y a distancia corta se aparean (crossover + mutación
del genoma); el hambre, el agotamiento o la vejez los matan, y la
población fluctúa bajo un tope de seguridad.

Leyenda de colores de los agentes:

| Color | Estado |
| ----- | ------ |
| 🟢 verde   | comiendo |
| 🔵 azul    | descansando / durmiendo |
| 🟠 naranja | activo y con hambre |
| 🟣 magenta | en cooldown de apareamiento (recién apareado o recién nacido) |
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
