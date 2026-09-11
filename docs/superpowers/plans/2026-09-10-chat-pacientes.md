# Plan de Implementación — Chat con Pacientes (Medtify V15)

**Fecha:** 2026-09-10
**Spec de referencia:** `docs/superpowers/specs/2026-09-10-chat-pacientes-design.md` (commits `d02aaee`, `56f31dd`)
**Regla dura:** nada se sube a GitHub (commit/push) sin instrucción explícita del usuario. Este trabajo se hace en local.

---

## 1. Objetivo

Agregar un centro de chat estilo WhatsApp dentro de Medtify V15:

- Nueva opción de menú **"💬 Chat con Pacientes"** (6ª opción del radio del sidebar).
- **Bandeja izquierda:** solo pacientes presentes en la Base de Pacientes, con etiquetas (policlínico, hora de lotificación, etc.), buscables por número.
- **Conversación derecha:** historial de mensajes reales de WhatsApp (texto) del paciente con la instancia `medtify-{account_id}` de la cuenta logueada.
- **Envío manual** de respuestas de texto (canal manual para respuestas fuera de las plantillas SÍ/NO confirmadas/vacunación).
- **Ver imágenes entrantes** (solo ver, no enviar imágenes en fase 1).
- **Refresco manual** con botón (sin auto-refresh).
- Registro de toda actividad en hoja **"Log de Chats"** (append-only).

No se toca el flujo existente de envío masivo de plantillas. Métodos actuales de `evolution_client.py` permanecen intactos.

---

## 2. Contexto técnico (verificado en exploración)

| Componente | Detalle |
|---|---|
| `evolution_client.py` (592 líneas) | `__init__` L24-46 (session header `apikey`), `_url` L48, `format_phone` L260-277, `send_message` L279, `get_last_incoming_message` L341 (ya usa `findMessages` con `where.key.remoteJid`), `verificar_respuesta` L417, `es_notificacion` L581 |
| Endpoints Evolution API v2.3.7 | `POST /chat/findChats/{instance}` — lista chats; `POST /chat/findMessages/{instance}` — historial (ya usado en codebase). Filtro por `remoteJid` requiere sufijo `@s.whatsapp.net` |
| `medtify_app_v15.py` | Radio sidebar ~L1645 (5 opciones; agregar 6ª), dispatch entre Centro de Notificaciones (~L3530) y Base de Pacientes (~L3531) |
| `connect_sheet` L513-560 | devuelve `(sheet, client, "OK")` |
| `get_data_fresh` L570 | obtiene Base de Pacientes (hoja REGISTRO con 29 columnas: RUT, NOMBRE_PACIENTE, TELEFONO, FECHA_NACIMIENTO, EDAD_ACTUAL, GENERO, FECHA_AGENDADA, HORA_AGENDADA, NOMBRE_PROFESIONAL, PROFESION, MOTIVO_CONSULTA, ESTADO, etc.) |
| `get_user_instance_name` L782 | `medtify-{account_id}` |
| `init_evolution_client` L788-817 | crea cliente Evolution con instancia de la cuenta |
| `enviar_mensaje_wsp` L1002 | envío existente |
| `format_whatsapp_phone` L1121 | formateo existente |
| Única escritura a Sheets | `append_row` L2817 (append-only) |
| `MASTER_ACCOUNT_ID` / `DYNAMIC_CREDS` / `URL_SHEET` L1490-1509 | config de cuentas y URL del spreadsheet |

**Decisiones de diseño (spec aprobado):**
1. Bandeja = solo pacientes de la base (no contactos arbitrarios de WhatsApp).
2. Sin IA Groq de auto-respuesta; canal manual.
3. Fase 1: texto + ver imágenes (sin enviar imágenes).
4. Refresco manual con botón.
5. Hoja "Log de Chats" append-only (se crea con los mismos permisos del cliente `gc`).
6. Aislamiento por cuenta: solo la instancia `medtify-{account_id}` de la cuenta logueada.
7. UI amigable, pulida, consistente con el resto de la app.
8. Nunca hardcodear números personales; el número de test `+56 9 6336 9748` solo se usa desde la cuenta "Alain" de forma manual/ocasional.

---

## 3. Arquitectura

```
medtify_app_v15.py   →  render_chat_view()  (nuevo, UI)
        │
        ├── chat_helpers.py  (NUEVO, lógica pura, sin importar Streamlit)
        │       ├── normalizar_telefono_chat(numero) -> str  (formato +569..., jid)
        │       ├── build_pacientes_chat_index(df_base) -> dict[jid -> {nombre, rut, pol, etiqueta}]
        │       └── formatear_hora_mensaje(ts) -> str
        │
        └── evolution_client.py  (3 métodos NUEVOS, no modifica existentes)
                ├── list_chats(limite) -> list
                ├── get_messages(numero, limite) -> list
                └── get_media_b64(media_url) -> str|None
                        └── hoja "Log de Chats" (append-only, connect_sheet + append_row)
```

**Principio:** `chat_helpers.py` es testeable sin Streamlit ni red (unittest + mocks). `evolution_client.py` se testea con `unittest.mock` apuntando a la session/url real pero sin HTTP.

---

## 4. Tareas

### Task 1 — Métodos nuevos en `evolution_client.py` + tests

**Archivos:** `evolution_client.py`, `tests/test_evolution_client_chat.py` (nuevo)

1. Agregar `import base64` al inicio.
2. Nuevo método `list_chats(self, limite=50)`:
   - `url = self._url("/chat/findChats/{instance}")` siguiendo el patrón de `get_last_incoming_message`.
   - Respuesta con key `chats` (lista de dicts con `remoteJid`, `name`, `unreadCount`, `lastMessage`).
   - `return resp.get("chats", [])`.
3. Nuevo método `get_messages(self, numero, limite=100)`:
   - Normalizar número con `format_phone` → `jid = numero + "@s.whatsapp.net"`.
   - POST `findMessages` con payload `{"where": {"key": {"remoteJid": jid}}, "limit": limite}`.
   - Respuesta con key `messages`; devolver lista plano (texto + timestamp si existe).
4. Nuevo método `get_media_b64(self, media_url)`:
   - GET con la misma session (headers `apikey`).
   - Si no es 200 o no hay `base64` en JSON → `return None` (no crashea el chat).
   - Devuelve `data:image/...;base64,<b64>` aplicando tipo según `mimetype`.
5. Tests `tests/test_evolution_client_chat.py` (unittest + mocks, runner `venv/bin/python -m unittest`):
   - `list_chats` proyecta `chats` de la respuesta.
   - `get_messages` construye el `remoteJid` con `@s.whatsapp.net` y usa `format_phone`.
   - `get_messages` con respuesta sin key `messages` → lista vacía, sin excepción.
   - `get_media_b64` con HTTP 404 → `None`; con `base64` ok → cadena `data:...`.

**Verificación Task 1:** `venv/bin/python -m unittest tests.test_evolution_client_chat -v` → OK.

---

### Task 2 — Módulo `chat_helpers.py` + tests

**Archivos:** `chat_helpers.py` (nuevo), `tests/test_chat_helpers.py` (nuevo)

1. Crear `chat_helpers.py` SIN importar Streamlit (importable en tests sin app ni red):
   - `normalizar_telefono_chat(numero)` → devuelve `569XXXXXXXX` (quitar espacios, guiones, +56, 0 inicial). Eleva `ValueError` si no hay 9 dígitos.
   - `build_pacientes_chat_index(df_base)` → dict `{jid: {nombre, rut, pol, etiqueta}}` donde `jid = num + "@s.whatsapp.net"`. Usa: `TELEFONO` (número), `NOMBRE_PACIENTE` (nombre), `RUT` (ID), `PROFESION` (etiqueta policlínico), `FECHA_AGENDADA` + `HORA_AGENDADA` (hora de lotificación).
   - `formatear_hora_mensaje(ts)` → legible para UI (ej. HH:MM si es hoy, fecha si no).
   - `make_jid(numero)` → `numero + "@s.whatsapp.net"` (reusa `format_phone`).

2. Tests `tests/test_chat_helpers.py` (unittest):
   - `normalizar_telefono_chat` con `+56 9 1234 5678`, `0912345678`, `56912345678` → todos `56912345678`.
   - entrada inválida (corta) → `ValueError`.
   - `build_pacientes_chat_index` sobre un df mínimo con columnas: `RUT, NOMBRE_PACIENTE, TELEFONO, PROFESION, FECHA_AGENDADA, HORA_AGENDADA` → genera jids correctos y solo filas con `TELEFONO` válido.
   - `make_jid` → termina en `@s.whatsapp.net`.

**Verificación Task 2:** `venv/bin/python -m unittest tests.test_chat_helpers -v` → OK.

---

### Task 3 — Bandeja en la UI (`render_chat_view`)

**Archivos:** `medtify_app_v15.py`

1. Radio del sidebar (~L1645): agregar 6ª opción `"💬 Chat con Pacientes"`.
2. Agregar else-if en dispatch (entre Centro de Notificaciones ~L3530 y Base de Pacientes ~L3531) que llama `render_chat_view(...)`.
3. Nueva función `render_chat_view()` con firma que reciba los objetos ya creados en main (`evo_client`, `df_base`, `account_id`, `nombre_maestro`, `gc`):
   - Header de la sección y botón **"🔄 Refrescar"** (refresco manual; recarga `list_chats` y `get_data_fresh`).
   - Build índice con `build_pacientes_chat_index(df_base)`.
   - `list_chats(limite)` del Evolution API → intersecar con el índice de pacientes (solo pacientes de la base aparecen en la bandeja).
   - Columna izquierda (bandeja): lista clicable con nombre/pol/etiqueta y último mensaje/NO LEÍDOS.
   - Columna derecha: conversación del paciente seleccionado (placeholder en Task 4) + caja de entrada de texto + botón enviar.
4. Manejar sin chats: estado vacío amigable ("Aún no hay conversaciones").
5. Manejar errores Evolution (instancia desconectada, QR caducado): mensaje claro y sugerencia de reconectar el QR desde Centro de Notificaciones.

**Verificación Task 3:** `cd` al repo y `venv/bin/python -c "import ast, io; ast.parse(open('medtify_app_v15.py').read())"` → sintaxis OK; y `venv/bin/python -m unittest` (suite completa) → sin regresiones.

---

### Task 4 — Conversación + envío + Log de Chats

**Archivos:** `medtify_app_v15.py`

1. En la columna derecha de la bandeja (cuando hay paciente seleccionado):
   - `get_messages(telefono, limite=100)` del Evolution API contra la instancia de la cuenta logueada.
   - Render de los mensajes en orden cronológico, resaltando los del paciente (izquierda) vs los enviados por la instancia (derecha).
   - Si un mensaje tiene adjunto/privacidad de imagen: botón **"Ver imagen"** que llama `get_media_b64(url)` y render con el HTML ya usado en la app para imágenes base64.
   - Input de texto + botón **"Enviar"** → `send_message(telefono, texto)` (método existente).
2. Registro en hoja **"Log de Chats"** (append-only):
   - Obtener spreadsheet con `gc.open_by_url(URL_SHEET)`.
   - Si la hoja no existe → crearla con `add_worksheet("Log de Chats", ...)`.
   - Nueva función `append_log_chat(gc, account_id, telefono, nombre, direccion, mensaje, timestamp)`: columna por columna con `append_row` (patrón L2817).
   - Se registran acciones: mensajes entrantes vistos, mensajes enviados manualmente.
   - Header de la hoja: `fecha`, `cuenta`, `telefono`, `nombre`, `direccion`, `tipo`, `mensaje`.
3. **No** se registra la conversación completa automáticamente (evitar ruido); solo eventos de uso manual del chat.

**Verificación Task 4:** `venv/bin/python -m unittest` completo → OK; y smoke local (`venv/bin/python -m streamlit run medtify_app_v15.py`) → HTTP 200 y revisión manual de la bandeja.

---

## 5. Testing / Validación final

1. `venv/bin/python -m unittest discover -s tests -v` → todos los tests en verde (chat + existentes).
2. Smoke local de la app (usuario) en `localhost:8501` con cuenta propio: entrar a Chat con Pacientes, ver bandeja, abrir conversación, ver imagen, enviar mensaje manual y confirmar que aparece en Log de Chats.
3. Verificación con celular: responder/recibir mensaje real a la instancia re-escanando QR si hace falta.
4. Nada se push a GitHub hasta instrucción explícita del usuario.

---

## 6. Riesgos y mitigaciones

| Riesgo | Mitigación |
|---|---|
| Instancia desconectada / QR caducado al abrir el chat | Mensaje claro + sugerencia de reconectar QR; no crashea la app |
| `findMessages` devuelve volumen alto | `limite=100` y solo se pide la conversación seleccionada |
| Imagen no descargable (evolución limita base64) | `get_media_b64` devuelve `None` y la UI muestra aviso sin romper |
| Nombres de columnas de la Base difieren | Confirmar nombres exactos en `get_data_fresh` antes de codificar el índice |
| Comillas/JSON rotos al escribir docs | Mantener chunks cortos al editar archivos grandes |

---

## 7. Definición de hecho (DoD)

- [ ] 6ª opción visible en el sidebar y navegable.
- [ ] Bandeja muestra solo pacientes de la base (con etiquetas) y no contactos ajenos.
- [ ] Conversación muestra historial correcto por cuenta (aislamiento `medtify-{account_id}`).
- [ ] Envío manual funciona y queda registrado en Log de Chats.
- [ ] Ver imagen funciona o muestra aviso controlado.
- [ ] Tests unitarios nuevos en verde + sin regresiones en suite existente.
- [ ] Verificación manual local OK; sin push a GitHub.