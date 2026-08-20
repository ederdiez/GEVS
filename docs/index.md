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
  (movimiento, comer, descansar, recoger) desde una MLP
  (11 entradas → 6 ocultas → 5 salidas) afinada a mano en `sim/config.py`,
  con **genoma propio por individuo**. Hambre + sueño, comida que se agota
  y reaparece, y evitación de choques. Ver [Agentes](agentes.md).
- ✅ **Genética y reproducción sexual** — genoma = pesos de la red + 6
  rasgos físicos hereditarios; crossover + mutación al aparearse, cooldown
  de infancia, población bajo tope (`MAX_POPULATION`), muerte por hambre,
  agotamiento o vejez (`MAX_AGE_S`). Todo el azar vive en la semilla del
  mundo: misma semilla → misma trayectoria evolutiva. Ver
  [Genética](genetica.md).

## Hoja de ruta (idea aproximada, sin compromiso)

1. ✅ **Agentes v1** — la red neuronal ya controla el comportamiento y el
   movimiento (MLP con capa oculta, pesos editables en `config.py`).
2. ✅ **(bases) Evolución por genética** — cada agente tiene su genoma
   (pesos + rasgos del cuerpo), se reproduce sexualmente por encuentro y
   muere. Pendiente: aprendizaje por gradiente o búsqueda, y selección con
   fitness explícita si hace falta.
3. **Memoria e interacción** — comunicación y recuerdos entre agentes.
4. **Sociedades** — estructuras emergentes visibles en pantalla.

## Índice

| Documento | Contenido |
| --------- | --------- |
| [Guía de inicio](guia_inicio.md) | Instalar, ejecutar, solucionar problemas. |
| [Arquitectura](arquitectura.md) | Mapa de módulos, flujo, cómo editar y añadir cosas. |
| [Mundo](mundo.md) | Grid, tipos de celda, reloj y API de `sim/world.py`. |
| [Agentes](agentes.md) | Cerebro NN, entradas/salidas, ritmos, evitación de choques. |
| [Genética](genetica.md) | Genoma, herencia, nacimiento, muerte, determinismo. |
| [Dibujo](dibujo.md) | Capas de dibujo, colores de agentes y HUD. |
