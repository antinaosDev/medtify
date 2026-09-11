# CHANGELOG — Medtify V15 Chat

## [2026-09-11] Fix "Backend no responde" en cuentas sin leer WA_INSTANCE_NAME

### Problema
La cuenta **Alain** aparecía conectada, pero **cuenta_some2** mostraba
`❌ Backend no responde`.

### Causa raíz
Algunas cuentas (ej. cuentas con 2+ números) tenían su instancia real guardada en
la columna `WA_INSTANCE_NAME` del Admin Master. Si el header real de la hoja traía
un espacio (`"WA_INSTANCE_NAME "`), la lectura fallaba → `get_user_instance_name`
caía al nombre legacy `medtify-<cuenta>` → ese nombre NO existe en el servidor
Evolution → `_check_connection()` retorna `False` → UI mostraba "Backend no responde"
(cuando en realidad era "instancia no encontrada").

### Fix aplicado (`medtify_app_v15_chat.py`)
- Nueva función **`_cached_wa_instance_name_robusta(account_id)`**:
  - Lee el Admin Master con `get_all_values()` + **trim de headers** (mismo patrón
    que `load_app_configuration`).
  - Busca la fila por `CUENTA` y devuelve el valor de `WA_INSTANCE_NAME` limpio (`strip`).
- `get_user_instance_name()` ahora usa `_cached_wa_instance_name_robusta` en lugar
  de `_cached_wa_instance_name`.

### Impacto
- El nombre de instancia se lee correctamente aunque el header traiga espacios.
- Las cuentas con instancia ya conectada en el servidor volverán a mostrar
  "Conectado" en vez de "Backend no responde".
- Si la instancia no existe aún, la UI mostrará el botón de QR (no el error engañoso).

---

## [2026-09-11] Bandeja de Chat: Solo Usuarios Autorizados (privacidad) + Ordenamiento

### Contexto
La bandeja de chat mostraba TODOS los chats de la instancia WhatsApp. Ahora muestra
**solo los números autorizados** de la hoja propia de cada cuenta (URL_SHEET), con el
estado `ESTADO == "NOTIFICADO OK"`, ordenados por último mensaje recibido (más reciente primero).

### Cambios

#### `chat_helpers.py` (nuevas funciones, sin dependencia de Streamlit)
- **`build_autorizados_chat_index(df_base, col_estado="ESTADO", valor_ok="NOTIFICADO OK")`**
  - Construye el índice `jid → ficha` SOLO con filas donde `ESTADO == "NOTIFICADO OK"`.
  - No fusiona con la base de pacientes: el universo de la bandeja es exclusivamente
    los números autorizados de la hoja de la cuenta.
  - Normaliza nombres de columna con `strip()` por robustez (ej. `"ESTADO "`).
- **`ordenar_chats_por_ultimo_mensaje(chats_pacientes, reverse=True)`**
  - Ordena por `ts_chat` (timestamp unix del último mensaje), más reciente primero.

#### `medtify_app_v15_chat.py`
1. **Trim de headers en `load_app_configuration`**
   - `raw_headers = [str(h).strip() for h in raw_headers]`
   - Corrige el bug donde `"WA_INSTANCE_NAME "` (con espacio) no matchea la key esperada.
   - Aplica a TODAS las columnas del Admin Master (incluye `URL_SHEET`, `MENSAJE_AGEND`, etc.).
2. **Filtro de bandeja por autorizados**
   - `build_pacientes_chat_index(...)` → `build_autorizados_chat_index(...)`.
   - La bandeja ahora incluye solo `jid`s con `ESTADO == "NOTIFICADO OK"`.
3. **Timestamp del último mensaje**
   - Se agrega `ts_chat` a cada chat de la bandeja:
     `chat.get("t") or chat.get("lastMessageTimestamp") or 0`.
4. **Ordenamiento**
   - `chats_pacientes.sort(key=lambda x: (-x["unread"], x["nombre"]))`
     → `chats_pacientes = ordenar_chats_por_ultimo_mensaje(chats_pacientes)`.
   - Orden: último mensaje recibido, descendente.

### Protección de privacidad
- Un número personal nunca autorizado en ninguna hoja es **invisible**:
  1. No pertenece a ninguna instancia de la cuenta (la bandeja solo consulta la
     instancia de la cuenta activa).
  2. Aunque exista un chat en la instancia, el filtro `ESTADO == "NOTIFICADO OK"`
     lo bloquea.

### Pendiente / Notas
- **Multi-instancia por cuenta**: la arquitectura actual lee UNA instancia por cuenta
  (`get_user_instance_name` → columna `WA_INSTANCE_NAME`). Para cuentas con 2 números
  se requiere ampliar: agregar columna `WA_INSTANCE_NAME_2` (o lista separada por coma)
  en Admin Master y enumerar instancias al construir la bandeja. No implementado aún —
  requiere definir el formato en la hoja.

### No subido a GitHub
- Cambios solo locales. Pendiente revisión y `git commit` cuando el usuario lo autorice.