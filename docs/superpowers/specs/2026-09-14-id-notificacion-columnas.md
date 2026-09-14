# Spec: Columnas ID_NOTIFICACION_1 / ID_NOTIFICACION_2

Fecha: 2026-09-14
Estado: aprobado por usuario (formato A)

## Objetivo

Trazabilidad mínima de QUÉN notificó: registrar en dos columnas nuevas el nombre de perfil y el número de teléfono de la cuenta de WhatsApp que envió cada notificación.

## Alcance

- **ID_NOTIFICACION_1** → columna **AD (índice 30)** — pareja de FECHA_NOTIF_1.
- **ID_NOTIFICACION_2** → columna **AE (índice 31)** — pareja de FECHA_NOTIF_2.
- Los encabezados ya existen en la hoja (fila 1). No se crea ninguna columna.

## Contenido de la celda

Solo texto legible:

- Normal: `"NombrePerfil (número)"` — ej. `Juan Pérez (56912345678)`.
- Si `profileName` viene vacío: solo `número`.
- Fuente de datos: `EvolutionClient.get_instance_details()` → `profile_name` y `phone`.
- Si la llamada falla: se escribe `""` (no bloquea el envío, dentro de `try/except`).

## Implementación

### 1. Helper cacheado (nuevo)

`_cached_notificador_info(evo_url, evo_key, evo_inst)` con `@st.cache_data(ttl=300, show_spinner=False)`:

1. Obtiene el cliente cached (`_evo_chat_cached`).
2. Llama `get_instance_details()` (1 sola llamada HTTP cacheada 5 min por ejecución).
3. Devuelve `"NombrePerfil (número)"`, o solo `número`, o `""` en error.

### 2. Ocho escrituras añadidas

En cada punto existente donde se escribe ESTADO + FECHA + METODO (todo dentro de `try/except: pass`), añadir una línea más:

- NOTIF_1 (éxito y error, ciclo 1 y ciclo 2) → `sheet_conn.update_cell(fila, 30, id_notif)`.
- NOTIF_2 (éxito y error, ciclo 1 y ciclo 2) → `sheet_conn.update_cell(fila, 31, id_notif)`.

`id_notif` se calcula una vez por ciclo (antes del loop) con `_cached_notificador_info(...)` y se reutiliza en los 4 puntos.

### 3. Sin cambios en lo existente

ESTADO, FECHA_NOTIF_X, METODO, OBSERVACION, confirmaciones y toda la lógica de envío quedan intactos.

## Criterios de aceptación

1. Tras enviar una notificación NOTIF_1, la celda AD de la fila contiene `"NombrePerfil (número)"` o solo `número`.
2. Ídem para NOTIF_2 → AE.
3. Si el envío falla, AD/AE también se escriben (misma info del intento) — camino de error.
4. Los dos archivos v15 quedan idénticos (salvo túnel EVO_API_URL_CODE).
5. `py_compile` OK en ambos.