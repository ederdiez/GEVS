# GEVS IA

Una simulación visual de sociedades inteligentes hecha con Python y
pygame. La idea de fondo es sencilla: meter en un mundo a unos individuos
que no siguen ningún guion, dejar que cada uno tome sus propias decisiones
con su propio cerebro, y ver si de todo ese lío acaban saliendo cosas que
parecen sociedad: grupos, jerarquías, cooperación, peleas...

Cada individuo es único: tiene su propio cerebro (una red neuronal
pequeña, unas decenas de conexiones) y su propio cuerpo con rasgos
heredados de sus padres. Nadie les dice qué hacer; deambulan, tienen
hambre, sueño y curiosidad, y las consecuencias de sus actos les enseñan
en vida. Y como también se reproducen y se mueren, la evolución hace de
las suyas sobre lo que cada generación aprende a hacer bien.

## Qué se ve hoy al ejecutarla

Un mundo 2D que se envuelve sobre sí mismo (si cruzas un borde apareces
en el contrario), con día y noche que cambian la iluminación, y un
terreno generado por semilla fija: la misma semilla produce siempre el
mismo mundo. Ahí dentro viven los agentes, que:

- comen, duermen de noche y buscan recursos cuando tienen hambre;
- pueden recoger comida, madera o herramientas del suelo y llevarlas
  consigo (una cosa a la vez);
- se pelean entre ellos y con los depredadores, y un agente armado con
  una lanza pega más fuerte;
- se reproducen por encuentro: dos individuos con energía suficiente se
  aparean y su cría hereda una mezcla de los genomas de ambos, con
  pequeñas mutaciones;
- mueren de hambre, de agotamiento, de vejez o a manos de otro; la
  población total está limitada para que el mundo no se desborde;
- y lo más interesante: **aprenden durante su vida**. Cada agente ajusta
  su propio cerebro según los resultados que obtiene (un premio interno
  cuando el hambre se le calma, cuando escapa de un peligro, cuando gana
  una pelea...). Ese aprendizaje es personal: lo que uno aprende no pasa
  a sus hijos, solo lo que trae en los genes.

El comportamiento completo de un agente sale de su red neuronal: la red
propone y el cuerpo decide, de forma que un cerebro mal entrenado nunca
puede romper la simulación (no puede atravesar rocas, ni comer donde no
hay, ni robarle el sitio a otro). El cuerpo es lo que garantiza que las
reglas del mundo se cumplen siempre.

## Controles

| Entrada | Acción |
| --- | --- |
| Rueda del ratón | Zoom sobre el cursor |
| WASD o flechas | Mover la cámara |
| Clic izquierdo | Seleccionar un agente |
| `+` / `-` | Acelerar / ralentizar la simulación |

Al hacer clic sobre un agente se abre una segunda ventana con su cerebro
en vivo: se ve cómo se iluminan las neuronas y qué está decidiendo en
cada momento.

## Cómo leer a los individuos por su color

| Color | Significado |
| --- | --- |
| <span style="color:gray">gris</span> | Activo y sin hambre |
| <span style="color:orange">naranja</span> | Activo y con hambre |
| <span style="color:#48be78">verde</span> | Comiendo |
| <span style="color:#5c84e2">azul</span> | Descansando o durmiendo |
| <span style="color:#d65ec2">magenta</span> | En periodo de espera tras aparearse o nacer |
| <span style="color:#b42828">rojo</span> | Un depredador, no un agente |
| <span style="color:#ffe05a">amarillo</span> | Anillo que marca al agente seleccionado |

## Requisitos e instalación

Python 3.12 o superior. El resto es mínimo: `pygame` y `numpy`
(`requirements.txt`).

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python main.py
```

La simulación corre a 60 FPS y cada día simulado dura 60 segundos
reales. El ritmo se puede cambiar en marcha con `+` y `-`.

## Un poco de arquitectura, para quien quiera trastear

El código vive en `sim/`, separado por responsabilidades: el mundo y sus
reglas (`world.py`), el cuerpo de los agentes (`agent.py`), el cerebro
(`brain.py`), la genética (`genetics.py`), el dibujado (`drawing.py`) y
el bucle principal (`loop.py`). Todo lo que se pueda ajustar —tamaños,
colores, ritmos, umbrales, incluso las matrices de pesos iniciales del
cerebro— está concentrado en `sim/config.py`, sin números mágicos
sueltos por el código.

Dos decisiones que conviene conocer antes de tocar nada:

- **Determinismo.** Todo el azar del programa sale de una semilla
  (configurable). Misma semilla, misma trayectoria evolutiva. Si algo
  usa aleatoriedad, debe usar el generador del mundo, no el `random` de
  Python.
- **El cerebro propone, el cuerpo ejecuta.** Las nuevas conductas se
  añaden como intención de la red (una salida nueva, o una percepción
  nueva como entrada), y es el cuerpo quien decide qué se permite
  físicamente. Así la evolución nunca rompe la simulación.

La documentación completa y detallada vive en [`docs/`](docs/index.md):
cómo funciona el mundo, cada módulo, y cómo añadir cosas nuevas sin
cargarte lo que ya hay.
