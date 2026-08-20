# Documentación — GEVS IA

Proyecto: **simulación de sociedades inteligentes** con Python + pygame.

## Visión

Queremos simular individuos (agentes) con comportamientos propios que
interactúan entre sí dentro de un mundo, y observar cómo de esas
interacciones emergen estructuras sociales: grupos, jerarquías,
cooperación, conflictos, división del trabajo...

Principios del proyecto:

- **Simplicidad por encima de todo.** Cada pieza hace una cosa y se entiende
  de un vistazo.
- **Modularidad.** Todo lo editable vive en un sitio claro (`sim/config.py`)
  y cada responsabilidad tiene su propio archivo.
- **Documentación viva.** Esta carpeta se mantiene al día con el código.

## Estado actual

- ✅ Repositorio git inicializado, `.gitignore` completo.
- ✅ Ventana pygame funcional (800×600, 60 FPS, cierre limpio).
- ✅ **Mundo 2D con grid** — 40×30 celdas generadas por semilla fija:
  suelo, rocas, madera y recursos (comida). Lógica pura en
  `sim/world.py`, testeable sin ventana.
- ✅ **Ciclo día/noche** — un día simulado cada 60 s reales: colores que se
  interpolan suavemente, overlay nocturno e HUD con hora (vista top-down,
  sin cielo: la iluminación varía con la hora).
- ✅ **Agentes: cerebro NN + cuerpo** — agentes cuyo comportamiento
  *completo* (movimiento, comer, descansar, recoger) sale de una red
  neuronal MLP (10 entradas → 5 ocultas → 5 salidas) afinada a mano en
  `sim/config.py`,
  con un **genoma propio por individuo**. Hambre + sueño, comida que se
  agota y reaparece, y evitación de choques: al encontrarse dos agentes se
  apartan (sensores de proximidad con pesos negativos) y contra rocas o
  vecinos el cuerpo se queda firme sin temblar (claims: nunca dos en la
  misma celda).
- ✅ **Genética y reproducción sexual** — el genoma de cada agente son los
  pesos de su red + 6 rasgos físicos hereditarios (velocidad, rango de
  percepción de comida, ritmos metabólicos). Dos agentes elegibles a
  distancia corta se aparean: el hijo hereda por crossover uniforme +
  mutación, nace junto a sus padres con un cooldown de infancia, y la
  población fluctúa bajo un tope (`MAX_POPULATION`). Mueren por hambre,
  agotamiento o vejez (`MAX_AGE_S`). Todo el azar vive en la semilla del
  mundo: misma semilla → misma trayectoria evolutiva.

## Hoja de ruta (idea aproximada, sin compromiso)

1. ✅ **Agentes v1** — la red neuronal ya controla el comportamiento y el
   movimiento (MLP con capa oculta, pesos editables en `config.py`).
2. ✅ **(bases) Evolución por genética** — cada agente tiene su genoma
   (pesos + rasgos del cuerpo, ahora el cuerpo sí cambia), se reproduce
   sexualmente por encuentro y muere. Pendiente: aprendizaje por gradiente
   o búsqueda, y selección con fitness explícita si hace falta.
3. **Memoria e interacción** — comunicación y recuerdos entre agentes.
4. **Sociedades** — estructuras emergentes visibles en pantalla.

## Índice

| Documento | Contenido |
| --------- | --------- |
| [Guía de inicio](guia_inicio.md) | Instalar, ejecutar, solucionar problemas. |
| [Arquitectura](arquitectura.md) | Mapa de módulos y cómo editar el código. |
