# Documentación — GEVS IA

Proyecto: **simulación de sociedades inteligentes** con Python + pygame.

## Visión

Simular individuos (agentes) con comportamientos propios que interactúan
entre sí dentro de un mundo, y observar cómo de esas interacciones emergen
estructuras sociales: grupos, jerarquías, cooperación, conflictos, división
del trabajo...

Principios del proyecto:

- **Simplicidad por encima de todo.** Cada pieza hace una cosa y se entiende
  de un vistazo.
- **Modularidad.** Todo lo editable vive en un sitio claro (`sim/config.py`)
  y cada responsabilidad tiene su propio archivo.
- **Documentación viva.** Esta carpeta se mantiene al día con el código.

## Estado actual

- ✅ Repositorio git inicializado, `.gitignore` completo.
- ✅ Ventana pygame funcional (800×600, 60 FPS, cierre limpio).
- ✅ **Mundo 2D con grid** — 40×30 celdas generadas por semilla fija: suelo,
  rocas, madera y recursos (comida). Lógica pura en `sim/world.py`,
  testeable sin ventana. Ver [Mundo](mundo.md).
- ✅ **Ciclo día/noche** — un día simulado cada 60 s reales: colores
  interpolados, overlay nocturno e HUD con hora (vista top-down, sin cielo:
  la iluminación varía con la hora).
- ✅ **Agentes: cerebro NN + cuerpo** — comportamiento *completo*
  (movimiento, comer, descansar, recoger, interactuar, soltar) desde una MLP
  (13 entradas → 6 ocultas → 7 salidas) afinada a mano en `sim/config.py`,
  con **genoma propio por individuo**. Hambre + sueño, comida que se agota
  y reaparece, y evitación de choques. Ver [Agentes](agentes.md).
- ✅ **Genética y reproducción sexual** — genoma = pesos de la red + 6
  rasgos físicos hereditarios; crossover + mutación al aparearse, cooldown
  de infancia, población bajo tope (`MAX_POPULATION`), muerte por hambre,
  agotamiento o vejez (`MAX_AGE_S`). Todo el azar vive en la semilla del
  mundo: misma semilla → misma trayectoria evolutiva. Ver
  [Genética](genetica.md).
- ✅ **Aprendizaje personal (RL Hebbiano)** — cada agente ajusta su propio
  cerebro en vida con una escalera de recompensas que premia el *resultado*
  (el hambre saciada), no el acto; la cadena "recoger → llevar → comer" se
  aprende, no está cableada. Sin tocar el genoma: lo aprendido no se hereda.
  Ver [Agentes → Aprendizaje personal](agentes.md).
- ✅ **Mundo toroidal** — el grid no tiene borde; cruzar un extremo
  envuelve al lado opuesto. Ver [Mundo](mundo.md).
- ✅ **Inspector de agente** — clic sobre un agente para abrir una segunda
  ventana con su red neuronal en vivo. Ver [Agentes → El inspector](agentes.md).

## Hoja de ruta (idea aproximada, sin compromiso)

1. ✅ **Agentes v1** — la red neuronal ya controla el comportamiento y el
   movimiento (MLP con capa oculta, pesos editables en `config.py`).
2. ✅ **(bases) Evolución por genética** — cada agente tiene su genoma
   (pesos + rasgos del cuerpo), se reproduce sexualmente por encuentro y
   muere.
3. ✅ **(bases) Aprendizaje personal** — RL Hebbiano en vida, sin backprop,
   separado del genoma (no heredable): instinto débil + exploración por
   ruido + escalera de recompensas por necesidad satisfecha. Pendiente:
   selección con fitness explícita si hace falta.
4. **Memoria e interacción** — comunicación y recuerdos entre agentes.
5. **Sociedades** — estructuras emergentes visibles en pantalla.

## Índice

| Documento | Contenido |
| --------- | --------- |
| [Guía de inicio](guia_inicio.md) | Instalar, ejecutar, solucionar problemas. |
| [Arquitectura](arquitectura.md) | Mapa de módulos, flujo, cómo editar y añadir cosas. |
| [Mundo](mundo.md) | Grid, tipos de celda, reloj y API de `sim/world.py`. |
| [Agentes](agentes.md) | Cerebro NN, entradas/salidas, ritmos, evitación de choques, aprendizaje personal, inspector. |
| [Genética](genetica.md) | Genoma, herencia, nacimiento, muerte, determinismo. |
| [Dibujo](dibujo.md) | Capas de dibujo, colores de agentes y HUD. |
