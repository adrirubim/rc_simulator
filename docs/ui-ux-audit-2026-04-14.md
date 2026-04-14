# Auditoría UI/UX (Qt / PySide6) — 2026-04-14

## Resumen ejecutivo
- **Esc ya no debe cambiar tamaño/estado de ventana**: el proyecto tenía (y corregiste) un camino donde `Esc` hacía toggle a fullscreen cuando no había sesión. Esto era la causa más probable del “cambio de tamaño” reportado.
- **Drive Mode (layout B) pierde el estado previo de ventana**: al salir de Drive se hace `showNormal()` incondicional; si el operador estaba maximizado antes, percibe un “resize” al volver.
- **Persistencia `restoreState()` puede pelearse con layouts**: se restaura el estado de docks después de aplicar layout, lo que puede reintroducir docks/posiciones no deseadas.
- **Listas ricas (cars/log) están bien encaminadas**, pero hay 2 puntos UX/perf: selección reseteada al filtrar y coste de `setItemWidget()` en el log bajo carga prolongada.
- **Accesibilidad básica**: hay focus ring en QSS, pero faltan `setTabOrder` y “nombres accesibles” en controles de ventana (–/□/✕).

## Matriz de teclado (comportamiento esperado)
> Fuente principal: `src/rc_simulator/ui_qt/views/main_window.py` (`keyPressEvent`) + `QShortcut` en `_install_shortcuts()`.

| Tecla | Estado/Layout | Acción |
|------:|--------------|--------|
| Esc | Autoconnect pending | Cancela banner/autoconnect (`_hide_banner`) |
| Ctrl+Shift+Esc | Cualquiera | “Emergency exit”: fuerza layout A |
| F11 | Cualquiera | Toggle fullscreen; si Drive activo, sale a layout A |
| Esc | Drive (layout B fullscreen) | Vuelve a layout A (no desconecta) |
| Esc | Con sesión activa | Desconecta |
| Esc | Sin sesión, no fullscreen | **No cambia estado** (deja que el foco/Qt lo procese) |
| Esc | Sin sesión, fullscreen | Sale a normal |
| Ctrl+F | — | Foco a búsqueda |
| Ctrl+Shift+F | — | Foco a filtro de log |
| Ctrl+L | — | Limpia log |
| Ctrl+Enter | — | Conecta |
| F1 | — | Banner con ayuda de atajos |

## Hallazgos (priorizados)

### P0 — `Esc` cambia tamaño/estado de ventana (fullscreen) cuando no hay sesión
- **Síntoma**: pulsar `Esc` provoca cambio de tamaño (entra/sale fullscreen) inesperado.
- **Dónde**: `src/rc_simulator/ui_qt/views/main_window.py` en `keyPressEvent`.
- **Causa**: lógica de prioridad que, en estado “idle”, hacía toggle de fullscreen.
- **Estado**: **corregido en tu rama** (ahora `Esc` no entra a fullscreen; solo puede salir si ya estaba).
- **Recomendación**: mantener `F11` como único toggle de fullscreen. Para `Esc`, reservar “cancelar/salir/cerrar” (banner, drive->panel, desconectar).

### P1 — Salir de Drive Mode no preserva “maximized/normal” previo
- **Síntoma**: operador maximiza la app, entra a Drive (fullscreen), sale con `Esc` y vuelve a ventana normal (no maximizada) → “resize”.
- **Dónde**: `apply_layout()` / `_apply_layout_now()` en `src/rc_simulator/ui_qt/views/main_window.py`.
- **Causa**: al salir de layout B se llama `showNormal()` sin recordar estado previo (maximized).
- **Recomendación** (bajo riesgo): guardar un flag/estado previo al entrar en Drive (ej. `was_maximized = isMaximized()` o `windowState()`), y al salir restaurar: `showMaximized()` si estaba maximizada.

### P1 — `restoreState()` de docks puede contradecir el layout activo
- **Síntoma**: al arrancar, o tras cambiar layouts, algunos docks pueden reaparecer, moverse o quedar en un estado inesperado.
- **Dónde**: orden de llamadas en `MainWindow.__init__()`:
  - `_restore_layout()` (aplica A/B/C) y luego `_restore_window_state()` (`restoreGeometry` + `restoreState`).
- **Causa**: `restoreState()` restaura layout de docks (visibilidad/posición) y puede sobrescribir decisiones de `apply_layout()` (especialmente si la última sesión guardó layout C).
- **Recomendación**:
  - Opción A: restaurar `restoreGeometry/restoreState` **antes** de `apply_layout()` y luego “imponer” layout actual.
  - Opción B: persistir estados de docks por layout (A/C) y no aplicar `restoreState()` global cuando se arranca en B.

### P2 — `CarsPanel.apply_car_filter()` resetea selección a fila 0
- **Síntoma**: al filtrar o al recibir nueva lista de cars, la selección salta a la primera entrada aunque el operador estuviera enfocado en otra.
- **Dónde**: `src/rc_simulator/ui_qt/views/_cars_panel.py`.
- **Causa**: si hay resultados, se hace `setCurrentRow(0)` siempre.
- **Recomendación**: intentar preservar selección por `active_car_id` o por la fila previamente seleccionada si sigue presente.

### P2 — Log con `setItemWidget()` puede degradar rendimiento en sesiones largas
- **Síntoma**: bajo logs altos, el UI puede sentirse pesado.
- **Dónde**: `src/rc_simulator/ui_qt/views/_log_panel.py`.
- **Contexto**: ya hay mitigación (`enforce_widget_limit=500`, `log_max_lines`).
- **Recomendación** (si se observa lag real): migrar a un modelo (MVC) o a `QPlainTextEdit` con append, o reducir widgets ricos para cada línea.

### P2 — Accesibilidad: falta tab order y nombres accesibles en controles de ventana
- **Síntoma**: navegación por teclado puede ser impredecible; lectores de pantalla pueden anunciar “button” sin significado (–/□/✕).
- **Dónde**: `src/rc_simulator/ui_qt/components/header.py`.
- **Causa**: no hay `setTabOrder` y no se asignan `setAccessibleName/Description`.
- **Recomendación**: definir tab order básico (search → list → scan/connect/disconnect → log filter → log controls) y nombres accesibles para window controls.

## Checklist de verificación manual (rápido)
- **Idle**: `Esc` no cambia tamaño; `F11` sí.
- **Maximized**: maximizar → Drive → `Esc` → vuelve maximizado (si se implementa la mejora P1).
- **Layout C**: activar debug → reabrir app → docks en posiciones coherentes con layout.
- **Cars**: filtrar texto → selección se preserva (si se implementa P2).
- **Log**: hacer scroll arriba → auto-pause se activa; volver abajo → resume manual funciona; rendimiento aceptable.

