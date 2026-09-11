# Avance — Rediseño UI Chat con Pacientes y fixes (2026-09-10)

## Alcance
`medtify_app_v15_chat.py` fue rediseñado y validado en navegador (cuenta Alain). Su contenido completo fue aplicado a
`medtify_app_v15.py` (archivo desplegado en Streamlit Cloud), quedando **idénticos** (4244 líneas, sintaxis OK).

## Cambios en la vista "Chat con Pacientes"

### Bandeja premium (estilo WhatsApp)
- Tarjetas clicables con avatar circular (inicial + gradiente de color por posición)
- Nombre en negrita, hora del último mensaje, chip de etiqueta (`🏷️ MEDICO APS`), último mensaje truncado en gris
- Badge verde de no leídos (gradiente WhatsApp)
- Hover con borde verde + sombra + elevación
- Click implementado con **overlay invisible** (botón Streamlit transparente, `opacity: 0`) que cubre toda la tarjeta
  (selectores CSS corregidos para `stBaseButton-secondary` existente en el DOM)

### Cabecera de conversación
- Avatar grande (48px) + nombre + RUT/política + pill verde "En línea" con punto pulsante (animación `ch-pulse`)
- Fondo de la app tipo WhatsApp (`#ece5dd`)

### Burbujas de mensajes
- Mensajes propios: gradiente verde WhatsApp (`#dcf8c6 → #d1f4b8`) con cola asimétrica
- Mensajes del paciente: blancas con borde gris y cola opuesta
- Hora interna con ticks `✓✓` azules en mensajes propios (`.ch-time::after`)
- Soporte existente para imágenes (`[Imagen]` + botón "Ver imagen")

### Input / Enviar
- Input pill redondeado (18px) con foco verde `#25d366`
- Botón "Enviar" con gradiente WhatsApp (`#25d366 → #128c7e`), sombra y hover

## Fix crítico: `st.cache_data.clear()` en Streamlit 1.59.2
- El código llamaba `st.cache_data.clear(_cached_...)` pasando la función como argumento.
- En la versión instalada (1.59.2) `clear()` **no acepta argumentos** y lanzaba
  `TypeError: CacheDataAPI.clear() takes 1 positional argument but 2 were given`,
  lo que tiraba la app de vuelta al login.
- Corregido en las 3 ubicaciones → `st.cache_data.clear()` sin argumentos:
  1. Botón "Refrescar" de la vista chat
  2. Envío de mensaje (limpieza de cache de mensajes y chats)
  3. Logout de WhatsApp (sección Gestión de Sesión)

## Dependencias nuevas del chat
- `chat_helpers.py` (nuevo, stdlib puro: `re`, `datetime`) — `normalizar_telefono_chat`, `make_jid`,
  `build_pacientes_chat_index`, `formatear_hora_mensaje`
- `evolution_client.py` (modificado) — métodos de chat: `list_chats(limite)`, `send_message(..., delay_ms)`
  (delay aleatorio 1.2–3 s si no se especifica), `get_media_b64`, y fix de `_url()` para evitar doble slash

## Verificación
- Navegador: login Alain/1111 → Chat con Pacientes → bandeja con tarjeta "jeanette" (avatar J, hora, chip MEDICO APS)
- Click en tarjeta abre la conversación: 5 burbujas, cabecera con "En línea", input y botón Enviar presentes
- 0 excepciones en la vista
- Sintaxis validada con `ast.parse` tras cada edición
- Footer de créditos ("Aplicación desarrollada por...") preservado al final del archivo

## Confidencialidad multi-cuenta (2026-09-10, commit 54e8db6)

**Requisito:** una cuenta Medtify solo debe ver los mensajes del WhatsApp que escaneó el QR de su instancia.
Ninguna otra cuenta puede leer sus mensajes, incluso si rota la sesión de WhatsApp.

**Modelo aplicado:**
- Cada cuenta tiene UNA instancia determinista `medtify-<account_id>` (función `get_user_instance_name`).
- La vista Chat con Pacientes y el panel Estado de Conexión usan SIEMPRE esa instancia derivada de la
  cuenta logueada — nunca un valor libre.
- El `Instance Name` / `Session ID` del panel ya **no son editables**: se muestran en modo solo lectura
  con candado 🔒. Se eliminó un texto que guardaba el valor en `session_state["evo_instance"]` sin verificar
  pertenencia (vector de fuga).
- Guard en Chat con Pacientes: si la sesión no tiene `account_id` válido, bloquea con `st.stop()`.
- Rótulo en la bandeja: “🔒 Solo conversaciones de la instancia <x> (cuenta actual)”.

**Refuerzo con token aleatorio (commit 83011bb):**
- Nueva columna en Admin Master: `WA_INSTANCE_NAME` (una por cuenta).
- `get_user_instance_name` lee ese valor; si está vacío genera
  `medtify-<cuenta>-<token8>` (secrets.token_hex) y **lo persiste en la hoja**.
- El nombre de instancia ya no es derivable desde el sheet ni adivinable con URL/key
  del panel: otra cuenta no puede apuntar a la instancia de otra.
- Caché de lectura 10 min; fallback legacy solo si la columna no existe/sin acceso.
- IMPORTANTE: el service account del sheet Admin Master debe ser **EDITOR** para poder
  escribir el token. La primera vez, el nombre de instancia cambia → re-escanear QR una vez.
- La rotación de teléfono ocurre DENTRO de la misma instancia (WA_INSTANCE_NAME no cambia).

## Pendiente / nota
- El archivo local `medtify_app_v15_chat.py` es la fuente de trabajo; `medtify_app_v15.py` es el desplegado y ambos
  deben mantenerse sincronizados (copiar el primero sobre el segundo al desplegar).
- `docs/: metodologia-desarrollo-chat.md` y `docs/superpowers/plans/` quedan en el árbol local sin commitear.