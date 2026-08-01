# OIHK_AUDIT.md — Auditoría de OIHK Basic v0.1.1-alpha.2 (preparación de candidata)

> Fecha: 2026-07-31 · Rama: `release/0.1.1-alpha.2` · Alcance: repositorio `OIHK-Basic`

---

## 1. Estado actual

| Área | Estado | Detalle |
| --- | --- | --- |
| Frontend | ✅ Compila | React 18.3 · Vite 7 · TypeScript 5.5 · Vitest 4 · ESLint 10 |
| Backend | ✅ Compila | FastAPI 0.133 · SQLAlchemy 2.0 async · SQLite/aiosqlite · Pydantic 2 |
| Desktop | ✅ Compila | Tauri 2.11 · Rust 1.95 · cargo check --locked OK |
| Tests frontend | ✅ 39 passed | 10 archivos de test |
| Tests backend | ✅ 12 passed | pytest + pytest-asyncio |
| Lint | ✅ limpio | eslint (frontend) + ruff (backend) |
| TypeScript | ✅ 0 errores | tsc -b --noEmit |

### Stack identificado

- **Frontend**: React 18 + Vite 7 + TypeScript, motor de grafo Canvas propio (`src/graph/*`: store, layout, renderer, spatial index, camera, interaction), Tauri API.
- **Backend**: FastAPI + SQLAlchemy async + SQLite, 19 routers, autenticación opcional desactivada por defecto (loopback-only).
- **Desktop**: Tauri 2 con sidecar gestionado del backend (invoke `get_backend_url`, `desktop_status`).
- **Persistencia**: SQLite en `%APPDATA%/OIHK-Basic/oihk-basic.db` (Windows), migraciones propias en `database_migrations.py`.
- **Modelos locales**: `app/services/local_models.py` con adaptadores LM Studio / Ollama / OpenAI-compatible; restricción a endpoints loopback/privados.

### Entry points

- `backend/run.py` → `app.main:app` (uvicorn en 127.0.0.1:8000 por defecto).
- `frontend/src/main.tsx` → `App.tsx` → `PlatformShell`.
- `src-tauri/src/main.rs` → `lib.rs` (sidecar del backend gestionado).

---

## 2. Problemas encontrados

### 2.1 CRÍTICO — Sistema de chats Copilot (Fase 2)

Síntomas reportados: *se crean chats nuevos de manera inesperada* y *algunos chats guardados aparecen vacíos al abrirse*.

**Causa raíz (frontend, `frontend/src/features/copilot/CopilotWorkspaceView.tsx`):**

1. **Creación no controlada de conversaciones** — En `submit()`, si `activeId` está vacío se llama `createCopilotConversation` incondicionalmente. `activeId` queda vacío cuando:
   - El usuario pulsa "New conversation" (comportamiento intencional pero sin confirmación del estado previo).
   - El componente se remonta al navegar entre vistas (el estado local se pierde porque `App.tsx` desmonta el contenido por área), y la lista se vuelve a cargar con `rows[0]?.id ?? ""`.
   - Si el usuario teclea antes de que termine la carga asíncrona inicial, `activeId` es `""` → se crea un chat nuevo aunque ya exista una sesión activa.
2. **Carreras asíncronas (`race conditions`)** — `refreshConversations` y `openConversation` hacen `setActiveId` y `setMessages` sin guarda de generación. Si el usuario pulsa el chat A y rápidamente el chat B, la respuesta lenta de A puede sobrescribir los mensajes de B → el chat "aparece vacío" (se muestra la lista de mensajes de la conversación equivocada o una lista vacía de una petición cancelada).
3. **Pérdida de la conversación activa al cambiar de vista** — La vista Copilot se desmonta al navegar a otra área (`case "copilot"` en `App.tsx`), perdiendo `activeId`, mensajes y borrador. Al volver, se restaura `rows[0]` (la más reciente) en lugar de la conversación en uso → sensación de "chat perdido / nuevo chat".
4. **`refreshConversations` sin preservar el id activo** — Cuando `preferredId` no está en `rows` (p. ej. al archivar), se cae a `rows[0]?.id ?? ""` y se sobrescribe el estado → cambio de conversación no solicitado.
5. **El borrador se pierde al cambiar de vista** — `draft` es estado local del componente.

**Archivos afectados:**
- `frontend/src/features/copilot/CopilotWorkspaceView.tsx` (principal)
- `frontend/src/api.ts` (cliente, sin problemas graves)
- `backend/app/routers/assistant.py` (menor: validación de título vacío tras strip; migración de esquema pendiente para modelo por conversación)

**Severidad:** CRÍTICO. Rompe la confianza de persistencia del producto.

### 2.2 ALTO — Canvas: tipos de entidad incompletos y perf sin degradación controlada (Fase 3)

- `graphTypes.ts` no cubre todos los tipos requeridos: faltan `file`, `hash`, `location`, `username`, `custom` (el requisito pide Persona, Alias, Organización, Dominio, URL, Correo, Usuario, IP, Teléfono, Archivo, Hash, Ubicación, Fuente, Evidencia, Entidad personalizada).
- El renderer no aplica límite de nodos visibles (LOD) — `dimThreshold` está en el contrato de `RenderScene` pero nunca se usa.
- Existe un único test de rendimiento (1200 nodos en `layout.test.ts`); faltan pruebas small/medium/large.

**Archivos afectados:** `frontend/src/components/graphTypes.ts`, `frontend/src/graph/renderer.ts`, `frontend/src/graph/layout.ts`, tests.

### 2.3 MEDIO — Modelos locales (Fase 5)

- `LocalModelsView` y `local_models.py` ya existen y son funcionales (detección, listado, selección, test, timeout).
- Falta: **streaming real de respuestas** en el endpoint de chat (el proveedor siempre usa `stream: False`), **reintentos limitados** y **cancelación de generación** en el frontend (hay AbortController en el send, pero el backend no lo aprovecha como streaming).
- El cambio de modelo por chat no está persistido (el modelo se guarda globalmente, no por conversación).

### 2.4 MEDIO — Portabilidad y configuración (Fase 6)

- No se encontraron rutas absolutas del desarrollador ni claves hardcodeadas en el código fuente (los tests `test_separation.py` y `test_first_run.py` lo verifican).
- No existe `backend/.env.example` (requerido por la Fase 6).
- La configuración se genera por usuario vía `first_run.py` (correcto) y los directorios son compatibles Windows (`%APPDATA%`). Falta documentar variables de entorno.

### 2.5 MEDIO — Seguridad y documentación (Fase 7)

- `SECURITY.md` ya existe y es sólido. Faltan `PRIVACY.md`, `THREAT_MODEL.md` y `RESPONSIBLE_USE.md` (requeridos).
- La sanitización de HTML en reports usa `html.escape` (correcto).
- Los endpoints de modelos locales validan que sean loopback/privados (correcto, evita SSRF).
- El CSP de Tauri restringe `connect-src` a loopback (correcto).

### 2.6 BAJO — Componentes desconectados / legado

- `AssistantSidebar.tsx`, `CaseLaunchView.tsx`, `InspectorDock.tsx`, `EntityDock.tsx`, `AnalysisPanels.tsx` están definidos pero **no se importan** en ningún punto del app (código muerto / legado de OIHK Full que quedó en Basic). `CaseLaunchView` usa `preparedGraph` con datos de demostración.
- `ForensicLab.tsx` sí se usa (vía `ToolsWorkspaceView`).
- No se deben eliminar sin confirmación (restricción del encargo), pero hay que documentarlo.

### 2.7 BAJO — Scripts de build no estandarizados (Fase 8)

- `frontend/package.json` tiene `dev`, `build`, `test`, `lint`, `desktop:dev`, `desktop:build`.
- Faltan aliases estándar: `npm run check`, `npm run tauri:build`, `npm run release:alpha`.

---

## 3. Plan de implementación (por prioridad)

1. **Fase 2 — Reparar sistema de chats** (CRÍTICO):
   - Frontend: guarda de generación para peticiones asíncronas; no crear conversación si existe sesión activa (solo con "New conversation" explícito); preservar `activeId`/mensajes/borrador al cambiar de vista (persistencia en `sessionStorage` con clave por caso); `refreshConversations` sin sobrescribir la conversación activa.
   - Backend: validar título no vacío tras strip; persistir `model` por conversación (migración de esquema 4); reintentos limitados + streaming en endpoint de chat.
   - Tests: crear chat, guardar mensajes, abrir chat existente, cambiar entre chats, reiniciar app, eliminar chat, chat con muchos mensajes.

2. **Fase 3 — Canvas**: completar tipos de entidad, LOD de renderer, tests de rendimiento small/medium/large.

3. **Fase 5 — Modelos locales**: streaming SSE en `/assistant/conversations/{id}/stream`, cancelación y reintentos; modelo por conversación.

4. **Fase 6 — Portabilidad**: crear `backend/.env.example`; verificar ausencia de rutas personales.

5. **Fase 7 — Seguridad**: crear `PRIVACY.md`, `THREAT_MODEL.md`, `RESPONSIBLE_USE.md`; revisar y actualizar `SECURITY.md`.

6. **Fase 8 — Build**: añadir `npm run check`, `npm run tauri:build`, `npm run release:alpha`.

7. **Fase 9 — Aceptación**: ejecutar typecheck, tests, lint y build; comprobar regresiones.

## 4. Riesgos de regresión

- **Alto**: Modificar el flujo de envío de mensajes sin conservar el optimismo actual (`setMessages` con `pending-*`) puede provocar duplicados o pérdida visual de mensajes. Se mitigará con guarda de generación y reescritura mínima.
- **Medio**: Añadir una columna `model` a `assistant_conversations` requiere migración 4 con guardas de existencia de columna (el runner de migraciones ya contempla esto para `cases`).
- **Medio**: El streaming SSE en el backend cambia el contrato del endpoint de chat; el frontend debe degradar al modo no-streaming si el proveedor no lo soporta.
- **Bajo**: Añadir tipos de entidad nuevos al `graphTypes.ts` es aditivo; `getNodeConfig` ya tiene fallback para tipos desconocidos.
- **Bajo**: Los cambios en `package.json` son aditivos (aliases).

## 5. Verificación

- `npx tsc -b --noEmit` (frontend) — baseline: OK.
- `npx vitest run` (frontend) — baseline: 39 OK.
- `npx eslint .` (frontend) — baseline: OK.
- `python -m pytest -q` (backend) — baseline: 12 OK.
- `python -m ruff check app run.py` (backend) — baseline: OK.
- `cargo check --locked` (src-tauri) — baseline: OK.
