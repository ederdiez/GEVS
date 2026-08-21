# GEVS IA — Simulación de Sociedades Inteligentes

Simulación visual de sociedades inteligentes construida con **Python +
pygame**. El objetivo a largo plazo es simular agentes que interactúan entre
sí y forman estructuras sociales emergentes.

**Estado actual:** mundo 2D **toroidal** (sin bordes: los extremos
envuelven) en vista top-down (rocas, madera y recursos generados por
semilla fija), ciclo día/noche con iluminación variable (HUD con hora y
población) y agentes cuyo comportamiento completo sale de una red
neuronal **propia por individuo** (cada agente tiene su genoma: pesos de
la red + rasgos físicos hereditarios). Además de la herencia, cada agente
**aprende en vida** (RL Hebbiano al recoger comida) sin tocar su genoma:
lo aprendido no se hereda. Deambulan, comen con hambre, duermen de noche,
se apartan al encontrarse y pueden recoger comida en un inventario de una
ranura (punto sobre la cabeza mientras la llevan). **Nacen, se reproducen
y mueren**: dos agentes con energía suficiente y a distancia corta se
aparean (crossover + mutación del genoma); el hambre, el agotamiento o la
vejez los matan, y la población fluctúa bajo un tope de seguridad. Un
clic sobre un agente abre una segunda ventana con su red neuronal en
vivo.

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

| Documento | Contenido |
| --------- | --------- |
| [Índice](docs/index.md) | Visión, estado actual y hoja de ruta. |
| [Guía de inicio](docs/guia_inicio.md) | Instalación y ejecución. |
| [Arquitectura](docs/arquitectura.md) | Mapa de módulos y cómo editar el código. |
| [Mundo](docs/mundo.md) | Grid, reloj y API del mundo. |
| [Agentes](docs/agentes.md) | Cerebro NN, cuerpo y evitación de choques. |
| [Genética](docs/genetica.md) | Genoma, reproducción y muerte. |
| [Dibujo](docs/dibujo.md) | Capas de dibujo y HUD. |
