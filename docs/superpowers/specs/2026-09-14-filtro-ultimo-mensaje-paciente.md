# Filtro de Último Mensaje del Paciente en Bandeja de Chat

**Fecha:** 2026-09-14
**Estado:** Aprobado

## Objetivo

Mostrar en la bandeja izquierda de "Chat con Pacientes" el último mensaje del **paciente** (no del bot) como preview de cada tarjeta.

## Contexto

Actualmente, la tarjeta de cada chat muestra `ultimo_texto` extraído de `chat["lastMessage"]` — el mensaje más reciente del chat sin importar quién lo envió. Si el bot acaba de enviar una confirmación, el preview muestra el mensaje del bot en vez de la respuesta del paciente.

## Filtros existentes (NO se modifican)

1. **ESTADO "NOTIFICADO OK"** — solo pacientes con ese estado en Google Sheets
2. **Cruce con base** — solo chats cuyo `remoteJid` existe en `pacientes_index`
3. **Buscador de texto** — filtra por nombre, RUT o teléfono

El nuevo filtro es **adicional**: solo cambia el texto del preview, no la lista de chats que aparecen.

## Comportamiento

Para cada chat en la bandeja:

1. Extraer `lastMessage` del chat (campos: `conversation`, `message.conversation`, `extendedTextMessage.text`, `imageMessage.caption`)
2. Verificar si `lastMessage` es del bot:检查 `lastMessage.key.fromMe`
   - Si `fromMe == False` (mensaje del paciente) → usar como preview (comportamiento actual)
   - Si `fromMe == True` (mensaje del bot) → buscar el último mensaje del paciente
3. Para buscar el último mensaje del paciente:
   - Llamar a `_cached_get_messages(numero, limite=5)` (ya existe, TTL 20s)
   - Iterar los mensajes en orden cronológico inverso
   - Tomar el primer mensaje donde `fromMe == False`
   - Si no se encuentra ningún mensaje del paciente → usar el texto del bot (fallback)
4. El `ts_chat` (timestamp para ordenar) se mantiene como el más reciente del chat (sin filtrar)

## Cambios en código

### `medtify_app_v15.py` y `medtify_app_v15_chat.py`

**Bloque a modificar:** construcción de `chats_pacientes` (líneas ~3756-3792)

```python
# EXTRAER ÚLTIMO MENSAJE DEL PACIENTE (nuevo filtro)
lm = chat.get("lastMessage")
ultimo_texto = ""
lm_from_me = False

if isinstance(lm, dict):
    # Verificar si el último mensaje es del bot
    lm_key = lm.get("key") or {}
    lm_from_me = lm_key.get("fromMe", False)
    
    # Extraer texto del lastMessage
    ultimo_texto = lm.get("conversation", "") or ""
    if not ultimo_texto:
        m = lm.get("message")
        if isinstance(m, dict):
            ultimo_texto = m.get("conversation", "") or ""
            if not ultimo_texto:
                etm = m.get("extendedTextMessage") or {}
                ultimo_texto = etm.get("text", "") or ""
            if not ultimo_texto:
                img = m.get("imageMessage") or {}
                if img.get("caption"):
                    ultimo_texto = str(img["caption"])
                elif img:
                    ultimo_texto = "[Imagen]"

# Si el último mensaje es del bot, buscar la última respuesta del paciente
if lm_from_me and ultimo_texto:
    try:
        msgs = _cached_get_messages(evo_url_chat, evo_key_chat, evo_inst_chat, 
                                     info["telefono"], limite=5)
        # Buscar último mensaje del paciente (fromMe == False), desde el más reciente
        for m in reversed(msgs):
            if not m.get("fromMe", True) and m.get("body"):
                ultimo_texto = m["body"]
                break
    except Exception:
        pass  # Fallback: mantener el texto del bot
```

**Nota:** `_cached_get_messages` ya existe (línea 604, TTL 20s) y acepta `numero` (teléfono). Se reutiliza sin crear nueva función.

## Verificación

1. `py_compile` OK en ambos archivos
2. `diff` ambos archivos idénticos
3. Filtros existentes intactos (ESTADO, cruce, buscador)
4. Preview muestra último mensaje del paciente cuando el bot fue el último en hablar
5. Sin cambios en Evolution API client ni en `chat_helpers.py`
