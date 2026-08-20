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
  suelo, obstáculos (rocas) y recursos (comida). Lógica pura en
  `sim/world.py`, testeable sin ventana.
- ✅ **Ciclo día/noche** — un día simulado cada 60 s reales: colores que se
  interpolan suavemente, overlay nocturno e HUD con hora (vista top-down,
  sin cielo: la iluminación varía con la hora).
- ✅ **Agentes v1: cerebro NN + cuerpo** — 14 agentes cuyo comportamiento
  *completo* (movimiento, comer, descansar) sale de una red neuronal MLP
  (7 entradas → 5 ocultas → 4 salidas) afinada a mano en `sim/config.py`.
  Hambre + sueño, comida que se agota y reaparece, los agentes se evitan
  (claims: nunca dos en la misma celda).

## Hoja de ruta (idea aproximada, sin compromiso)

1. ✅ **Agentes v1** — la red neuronal ya controla el comportamiento y el
   movimiento (MLP con capa oculta, pesos editables en `config.py`).
2. **Entrenar / evolucionar los pesos** — en vez de afinar a mano, que los
   pesos aprendan (evolución, gradiente o búsqueda); el cuerpo no cambia.
3. **Memoria e interacción** — comunicación y recuerdos entre agentes.
4. **Sociedades** — estructuras emergentes visibles en pantalla.

## Índice

| Documento | Contenido |
| --------- | --------- |
| [Guía de inicio](guia_inicio.md) | Instalar, ejecutar, solucionar problemas. |
| [Arquitectura](arquitectura.md) | Mapa de módulos y cómo editar el código. |
