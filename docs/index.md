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
- ✅ Documentación base creada.

## Hoja de ruta (idea aproximada, sin compromiso)

1. **Agentes** — entidades con posición, movimiento y estado (`sim/agent.py`).
2. **Mundo** — el espacio donde viven, con recursos (`sim/world.py`).
3. **Comportamientos** — reglas simples por agente (buscar, huir, descansar).
4. **Interacción** — comunicación y memoria entre agentes.
5. **Sociedades** — estructuras emergentes visibles en pantalla.

## Índice

| Documento | Contenido |
| --------- | --------- |
| [Guía de inicio](guia_inicio.md) | Instalar, ejecutar, solucionar problemas. |
| [Arquitectura](arquitectura.md) | Mapa de módulos y cómo editar el código. |
