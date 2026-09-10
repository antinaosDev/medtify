# Chat con Pacientes — Design Doc

**Fecha:** 2026-09-10
**Proyecto:** Medtify V15
**Estado:** Aprobado por usuario (secciones 1-5)

## Objetivo

Agregar un centro de chat estilo WhatsApp dentro de la app Medtify, que permita al usuario logueado ver las conversaciones de **los pacientes de su base** que escriben a su WhatsApp (el número escaneado por QR en su cuenta), responderles manualmente cuando su respuesta no está en las plantillas de confirmación/negación, y mantener un log de trazabilidad en Google Sheets.

**Criterio rector:** que todo lo existente siga operativo — no se rompe nada del flujo actual (envío masivo de plantillas, verificación de respuestas, gestión de horas).

**Regla dura del proyecto:** nada se sube a GitHub (commit/push) sin instrucción explícita del usuario. Todo se trabaja y prueba en local hasta que el usuario lo apruebe para subir.

## Contexto actual (verificado)

- Backend: `EvolutionClient` en `evolution_client.py` (HTTP a Evolution API v2.3.7, auth header `apikey`).
- La app navega con `st.sidebar` + `st.radio` con 5 vistas. El chat será la 6ª opción.
- `send_message(numero, mensaje)` ya existe y funciona para enviar texto a cualquier número chileno.
- `get_last_incoming_message()` ya usa `POST /chat/findMessages/{instance}` (solo el último mensaje entrante por número).
- Instancia por cuenta: `get_user_instance_name(account_id)` → `medtify-{account_id}`.
- Cada cuenta escanea su propio QR. **Aislamiento estricto:** la cuenta logueada solo lee su propia instancia.
- No hay IA Groq activa para responder chats: los envíos son plantillas; las respuestas del paciente se verifican contra listas de confirmación/negación (`verificar_respuesta`).
- Google Sheets (gspread + `gcp_service_account`) es la base de datos existente.

## Decisiones del usuario

| # | Decisión |
|---|---|
| 1 | Bandeja **solo pacientes** de la base (los que tienen número en la Base de Pacientes de la cuenta logueada). |
| 2 | Chat manual para respuestas que no encajan en plantillas SÍ/NO. No hay auto-respuesta IA. |
| 3 | Contenido: **texto + ver imágenes** del paciente. NO se envían imágenes (fase 1). |
| 4 | Aislamiento: cada cuenta solo ve los mensajes de su propio QR (`medtify-{account_id}`). **Nunca hardcodear el número personal de prueba (medtify → Alain).** |
| 5 | Refresco **manual** con botón "Actualizar". |
| 6 | Trazabilidad: hoja **"Log de Chats"** append-only en Google Sheets. |
| 7 | UI **amigable y pulida** (criterio de diseño). |
| 8 | Se agregan métodos nuevos a `EvolutionClient` sin modificar los existentes (cero regresión en Evolution API). |

## Arquitectura

```
medtify_app_v15.py  → +"💬 Chat con Pacientes" en st.radio + función render_chat_view()
evolution_client.py → +3 métodos NUEVOS (list_chats, get_messages, get_media_b64)
Google Sheets       → +hoja "Log de Chats" (append-only)
```

**Flujo:**
1. Usuario logueado → instancia = `get_user_instance_name(account_id)` (solo su QR).
2. `list_chats()` → POST `/chat/findChats/{instance}`.
3. Filtrar chats solo de números presentes en Base de Pacientes (de esa cuenta).
4. `get_messages(numero, limite)` → POST `/chat/findMessages/{instance}` con `where.key.remoteJid = {numero}@s.whatsapp.net`.
5. Responder → `send_message()` existente.
6. Log → append a hoja "Log de Chats".

## Métodos nuevos en evolution_client.py

### 1. `list_chats() -> List[Dict]`
- `POST /chat/findChats/{instancia}` body: `{"take": 100, "orderBy": {"t": "desc"}}`.
- Filtrar grupos (`isGroup != true` / más seguro: descartar JIDs `@g.us`).
- Normalizar → `{numero, nombre, ultimo_mensaje, timestamp, no_leidos}`.
- Errores → retorna `[]`, nunca lanza.

### 2. `get_messages(numero: str, limite: int = 100) -> List[Dict]`
- `POST /chat/findMessages/{instancia}` body:
  `{"where": {"key": {"remoteJid": f"{numero}@s.whatsapp.net"}}, "take": limite, "orderBy": {"t": "desc"}}`
- El sufijo `@s.whatsapp.net` es obligatorio para el filtro (confirmado en issue #1632 de EvolutionAPI).
- Normalizar → `{de_mi, texto, timestamp, tipo, media_url, id}`.
- Si el mensaje es imagen con `media_url`, se devuelve para mostrarla.
- Errores → retorna `[]`, nunca lanza.

### 3. `get_media_b64(media_url: str) -> Optional[str]`
- GET a `media_url` con el apikey del cliente.
- Devuelve base64 para `st.image()`.
- Errores → retorna `None`, nunca lanza.

**Reglas comunes:** mismo session/headers, mismo patrón try/except, respeta `safe_mode` (si está activo: mostrar/lectura OK, envíos simulados).

Nota: NO se toca `openwa_adapter.py`. Si el backend fuera OpenWA, la vista muestra "no disponible" en vez de romper.

## Interfaz de usuario

- 6ª opción del menú: **"💬 Chat con Pacientes"**.
- 2 columnas estilo WhatsApp Web:
  - **Izquierda:** buscador (nombre/número), lista de pacientes con WhatsApp (nombre + etiquetas + último mensaje), botón "🔄 Actualizar".
  - **Derecha:** header con etiquetas del paciente; globos de mensajes (entrantes izquierda verde/izquierda, enviados derecha); imágenes entrantes con `st.image`; caja de texto + botón "Enviar".
- Etiquetas del header (cruce con Base de Pacientes): nombre, policlínico/zona, hora de lotificación, tramo/prioridad, última interacción.
- Distinción visual entre mensajes automáticos (plantillas) y manuales.
- UI pulida: CSS custom para globos, bandeja y etiquetas.

## Log de Chats (Google Sheets)

Hoja `Log de Chats`, append-only:

| fecha | cuenta | numero | direccion | texto | tipo | origen |
|---|---|---|---|---|---|---|
| 2026-09-10 15:30 | alain | +569... | recibido | "hola" | texto | chat |
| 2026-09-10 15:31 | alain | +569... | enviado | "¿en qué le ayudo?" | texto | manual |

- Solo mensajes vistos/respondidos desde el chat (no el flujo masivo de plantillas).
- Fallo de log → aviso suave, pero NO bloquea el envío.

## Manejo de errores

| Situación | Comportamiento |
|---|---|
| Instancia no conectada | Mensaje claro + enlace a Gestión de Sesión (QR) |
| API sin responder / timeout | Aviso + botón Reintentar. Nunca crashea |
| Paciente sin chat previo | "Sin mensajes aún" — igual se puede escribir (send_message crea el chat) |
| Envío fallido | Texto conservado en pantalla + aviso |
| Log de Sheets caído | Aviso suave, envío igual |

## Pruebas (antes de producción)

1. Local en `localhost:8501`: listar chats reales de la cuenta logueada, abrir conversación, responder, ver llegada en WhatsApp real.
2. Aislamiento: el chat de una cuenta NO ve mensajes de otra instancia.
3. Sin regresión: flujo de envío masivo (Centro de Notificaciones) debe quedar idéntico.
4. `git status`/`git check-ignore` antes de cualquier commit (nunca subir secretos).

**Criterio de éxito:** app funcional igual que hoy en todo lo demás + chat fluido en local antes de subir.

## Fuera de alcance (fase 1)

- Enviar imágenes/medios (fase 2 posible).
- Auto-refresco (opción A elegida: manual).
- Soporte OpenWA.
- Auto-respuesta IA (Groq) para chats.