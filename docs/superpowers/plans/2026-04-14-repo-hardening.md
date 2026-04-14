# RC Simulator Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Dejar el repo limpio y reproducible (sin artefactos en-tree), robustecer el loop UI bajo carga (backpressure), unificar strings UI, y separar “headless service” vs GUI para que `systemd` no arranque una aplicación Qt.

**Architecture:** Cambios incrementales y verificables. Mantener el guardrail arquitectónico (UI no importa IO). Refactorizar `MainWindow` en módulos internos sin cambiar comportamiento observable. Añadir checks automáticos para evitar regresiones (artefactos de build, drenaje de cola UI ilimitado, systemd apuntando a GUI).

**Tech Stack:** Python 3.12+, PySide6/Qt, ruff, pytest, bash/PowerShell ops scripts, systemd unit template.

---

## Estado

- **Estado actual**: IMPLEMENTADO (Tasks 1–6).
- **Verificación local recomendada**: `./scripts/dev-verify.sh`
- **Verificación CI**: workflows `Lint`, `Tests`, `Security` en GitHub Actions

## Mapa de archivos (lo que se va a tocar)

**Build hygiene**
- Modify: `\\wsl.localhost\\Ubuntu\\var\\www\\rc_simulator\\scripts\\audit_layout.py`
- Modify: `\\wsl.localhost\\Ubuntu\\var\\www\\rc_simulator\\scripts\\dev-verify.sh`
- (Opcional) Modify: `\\wsl.localhost\\Ubuntu\\var\\www\\rc_simulator\\.github\\workflows\\*.yml` (si existe en este workspace)
- Test: `\\wsl.localhost\\Ubuntu\\var\\www\\rc_simulator\\tests\\test_layout_hygiene.py` (nuevo)

**UI backpressure + strings**
- Modify: `\\wsl.localhost\\Ubuntu\\var\\www\\rc_simulator\\src\\rc_simulator\\ui_qt\\views\\main_window.py`
- Modify: `\\wsl.localhost\\Ubuntu\\var\\www\\rc_simulator\\src\\rc_simulator\\ui_qt\\strings.py`
- (Nuevo) Create: `\\wsl.localhost\\Ubuntu\\var\\www\\rc_simulator\\src\\rc_simulator\\ui_qt\\views\\_queue_drain.py` (helper puro UI)

**Ops / systemd + headless entrypoint**
- Modify: `\\wsl.localhost\\Ubuntu\\var\\www\\rc_simulator\\ops\\linux\\services\\moza_udp_client.service.in`
- Create: `\\wsl.localhost\\Ubuntu\\var\\www\\rc_simulator\\src\\rc_simulator\\__main_headless__.py` (o comando equivalente)
- Modify: `\\wsl.localhost\\Ubuntu\\var\\www\\rc_simulator\\src\\rc_simulator\\__main__.py` (mantener GUI como default)
- (Opcional) Modify: `\\wsl.localhost\\Ubuntu\\var\\www\\rc_simulator\\ops\\linux\\install_service.sh` si necesita actualizar placeholders/docs

**Refactor grande (sin cambios de comportamiento)**
- Create: `\\wsl.localhost\\Ubuntu\\var\\www\\rc_simulator\\src\\rc_simulator\\ui_qt\\views\\_log_panel.py`
- Create: `\\wsl.localhost\\Ubuntu\\var\\www\\rc_simulator\\src\\rc_simulator\\ui_qt\\views\\_cars_panel.py`
- Create: `\\wsl.localhost\\Ubuntu\\var\\www\\rc_simulator\\src\\rc_simulator\\ui_qt\\views\\_session_panel.py`
- (Opcional) Create: `\\wsl.localhost\\Ubuntu\\var\\www\\rc_simulator\\src\\rc_simulator\\ui_qt\\views\\_video_panel.py` (si está contenido)

---

### Task 1: Endurecer higiene de layout (fallar si hay artefactos)

**Files:**
- Modify: `\\wsl.localhost\\Ubuntu\\var\\www\\rc_simulator\\scripts\\audit_layout.py`
- Test: `\\wsl.localhost\\Ubuntu\\var\\www\\rc_simulator\\tests\\test_layout_hygiene.py`

- [x] **Step 1: Escribir test (falla si hay `src/**/*.egg-info`)**

```python
from __future__ import annotations

from pathlib import Path


def test_no_egg_info_inside_src_tree() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    hits = list(repo_root.glob("src/*.egg-info")) + list(repo_root.glob("src/**/*.egg-info"))
    assert not hits, "Found `*.egg-info` inside src/ (repo should be clean):\n" + "\n".join(str(p) for p in hits)
```

- [x] **Step 2: Ejecutar el test para ver FAIL (si hoy existe egg-info)**

Run: `pytest -q tests/test_layout_hygiene.py -q`  
Expected: FAIL si existen `src/**/*.egg-info` en tu workspace actual; PASS si el tree ya está limpio.

- [x] **Step 3: Cambiar `audit_layout.py` para elevar severidad a ERROR**

Cambiar el finding de `*.egg-info` de `"WARN"` a `"ERROR"` para que `scripts/dev-verify.sh` devuelva código 2 y corte el pipeline.

- [x] **Step 4: Ejecutar `python3 scripts/audit_layout.py`**

Run: `python3 scripts/audit_layout.py`  
Expected: Exit code 2 cuando haya `*.egg-info` dentro de `src/`.

- [x] **Step 5: Ajustar `scripts/dev-verify.sh`**

Decisión: dejar de “barrer debajo de la alfombra” (no borrar egg-info automáticamente) y en su lugar fallar con un mensaje claro, o mantener el borrado pero además imprimir aviso severo.  
Recomendación: **quitar el `rm -rf ...egg-info`** y dejar que el audit/test fallen, para detectar el problema temprano.

- [x] **Step 6: Re-ejecutar `./scripts/dev-verify.sh`**

Expected: si hay `egg-info` → falla; si no hay → sigue con ruff/pytest.

---

### Task 2: Backpressure del drenaje de eventos UI (no bloquear el event loop)

**Files:**
- Create: `\\wsl.localhost\\Ubuntu\\var\\www\\rc_simulator\\src\\rc_simulator\\ui_qt\\views\\_queue_drain.py`
- Modify: `\\wsl.localhost\\Ubuntu\\var\\www\\rc_simulator\\src\\rc_simulator\\ui_qt\\views\\main_window.py`
- Test: `\\wsl.localhost\\Ubuntu\\var\\www\\rc_simulator\\tests\\test_ui_queue_drain.py`

- [x] **Step 1: Escribir test unitario del helper (drena máximo N)**

```python
from __future__ import annotations

import queue

from rc_simulator.ui_qt.views._queue_drain import drain_queue


def test_drain_queue_limits_items() -> None:
    q: queue.Queue[int] = queue.Queue()
    for i in range(100):
        q.put(i)

    drained = drain_queue(q, max_items=10)
    assert drained == list(range(10))
    assert q.qsize() == 90
```

- [x] **Step 2: Implementar helper `drain_queue` (puro, sin Qt)**

```python
from __future__ import annotations

import queue
from typing import TypeVar

T = TypeVar("T")


def drain_queue(q: "queue.Queue[T]", *, max_items: int) -> list[T]:
    if max_items <= 0:
        return []
    out: list[T] = []
    for _ in range(max_items):
        try:
            out.append(q.get_nowait())
        except queue.Empty:
            break
    return out
```

- [x] **Step 3: Cambiar `MainWindow.process_ui_queue` para procesar en lotes**

Cambiar el `while True` por:
- drenar \(N\) eventos por tick (configurable, p.ej. `RC_UI_MAX_EVENTS_PER_TICK`, default 200)
- (opcional) early-exit por presupuesto de tiempo (p.ej. 8–12ms) si prefieres tiempo sobre recuento

**Criterio de éxito verificable:** con un productor que mete eventos rápido, la UI mantiene capacidad de repintado (no “freeze” por ticks largos).

- [x] **Step 4: Ejecutar tests**

Run: `pytest -q tests/test_ui_queue_drain.py -q`  
Expected: PASS.

---

### Task 3: Unificar strings UI (fuente única en `ui_qt/strings.py`)

**Files:**
- Modify: `\\wsl.localhost\\Ubuntu\\var\\www\\rc_simulator\\src\\rc_simulator\\ui_qt\\strings.py`
- Modify: `\\wsl.localhost\\Ubuntu\\var\\www\\rc_simulator\\src\\rc_simulator\\ui_qt\\views\\main_window.py`

- [x] **Step 1: Añadir strings faltantes**

Agregar campos como:
- `session_status_prefix` (ej. `"Session status: "`),
- `error_prefix` (ej. `"Error: "`),
- `session_ended` (ej. `"Session ended."`),
- `scan_complete_found` / `scan_complete_none`

- [x] **Step 2: Reemplazar hardcodes en `process_ui_queue`**

Cambiar `self.session_label.setText(f"Stato sessione: {summary}")` por una versión basada en `UI`.

- [x] **Step 3: Verificación**

Run: `ruff check .`  
Expected: PASS.

---

### Task 4: Separar entrypoint headless para systemd (no levantar Qt)

**Files:**
- Create: `\\wsl.localhost\\Ubuntu\\var\\www\\rc_simulator\\src\\rc_simulator\\__main_headless__.py`
- Modify: `\\wsl.localhost\\Ubuntu\\var\\www\\rc_simulator\\ops\\linux\\services\\moza_udp_client.service.in`
- (Opcional) Modify docs: `\\wsl.localhost\\Ubuntu\\var\\www\\rc_simulator\\ops\\README.md` y/o `README.md`

- [x] **Step 1: Definir qué hace “headless”**

Comportamiento objetivo:
- corre `SessionController`/servicios de control (MOZA/UDP) sin Qt
- logging a stdout (para journald)
- shutdown limpio por SIGTERM

- [x] **Step 2: Implementar `python -m rc_simulator.__main_headless__`**

Código mínimo (esqueleto) con:
- `main()` que inicializa controlador headless
- bucle de vida hasta señal de salida

- [x] **Step 3: Apuntar systemd al entrypoint headless**

Cambiar `ExecStart=@PYTHON@ -m rc_simulator` por `ExecStart=@PYTHON@ -m rc_simulator.__main_headless__`.

- [x] **Step 4: Verificación**

Run: `python -m rc_simulator.__main_headless__ --help` (si agregas args) o `python -m rc_simulator.__main_headless__`  
Expected: arranca sin intentar importar PySide6/Qt (debe poder correr sin DISPLAY).

---

### Task 5: Refactor grande de `MainWindow` (dividir sin romper)

**Files:**
- Create: `\\wsl.localhost\\Ubuntu\\var\\www\\rc_simulator\\src\\rc_simulator\\ui_qt\\views\\_log_panel.py`
- Create: `\\wsl.localhost\\Ubuntu\\var\\www\\rc_simulator\\src\\rc_simulator\\ui_qt\\views\\_cars_panel.py`
- Create: `\\wsl.localhost\\Ubuntu\\var\\www\\rc_simulator\\src\\rc_simulator\\ui_qt\\views\\_session_panel.py`
- Modify: `\\wsl.localhost\\Ubuntu\\var\\www\\rc_simulator\\src\\rc_simulator\\ui_qt\\views\\main_window.py`

- [x] **Step 1: Extraer “Log dock” a `_log_panel.py`**

Mover métodos relacionados (ej. `append_log`, `refresh_log_view`, `_enforce_log_widget_limit`, handlers) a una clase `LogPanel` que reciba referencias a widgets/estilo.

- [x] **Step 2: Extraer “Cars list + filtro” a `_cars_panel.py`**

Mover `apply_car_filter`, `_refresh_car_row_active_styles`, debounce, `on_select`, manteniendo que `MainWindow` sigue siendo dueño del estado global.

- [x] **Step 3: Extraer “Session/mid state” a `_session_panel.py`**

Mover actualización de labels/badges/controls derivada de `AppPhase`.

- [x] **Step 4: Mantener guardrails**

Run: `pytest -q tests/test_architecture.py -q`  
Expected: PASS (los nuevos módulos siguen bajo `ui_qt/` y no importan IO).

- [x] **Step 5: Full verification**

Run: `./scripts/dev-verify.sh`  
Expected: PASS (audit layout + ruff + pytest).

---

### Task 6 (CI): Añadir checks en GitHub Actions (higiene + guardrails + headless)

**Files:**
- Modify: `\\wsl.localhost\\Ubuntu\\var\\www\\rc_simulator\\.github\\workflows\\tests.yml`
- Modify: `\\wsl.localhost\\Ubuntu\\var\\www\\rc_simulator\\.github\\workflows\\security.yml`

- [x] **Step 1: En `tests.yml`, ejecutar higiene antes del suite completo**

Añadir steps:
- `python scripts/audit_layout.py`
- `pytest -q tests/test_layout_hygiene.py -q`

- [x] **Step 2: En `tests.yml`, ejecutar guardrail de arquitectura**

Añadir step:
- `pytest -q tests/test_architecture.py -q`

- [x] **Step 3: En `tests.yml`, smoke test de entrypoint headless**

Añadir step:
- `python -c "import rc_simulator.__main_headless__"` (con `PYTHONPATH: src`)

- [x] **Step 4: En `security.yml`, añadir import check del entrypoint headless**

Añadir step:
- `python -c "import rc_simulator.__main_headless__"` (con `PYTHONPATH: src`)

- [x] **Step 5: Verificación**

En PR/push, esperar:
- Workflow `Lint`: PASS
- Workflow `Tests`: PASS (incluye higiene + guardrails + smoke headless + pytest)
- Workflow `Security`: PASS (import de `rc_simulator` + `rc_simulator.__main_headless__`)

---

## Notas de ejecución (si hay git)
- Si este workspace estuviera en git: commits pequeños por task.
- Si no: igual se ejecuta el plan, pero sin pasos de commit.

