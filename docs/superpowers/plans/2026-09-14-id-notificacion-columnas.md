# Columnas ID_NOTIFICACION_1 / ID_NOTIFICACION_2 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Registrar en las columnas AD (30) y AE (31) de la hoja principal el nombre de perfil y número de la cuenta de WhatsApp que envió cada notificación.

**Architecture:** Cambio quirúrgico. Se añade un helper cacheado `_cached_notificador_info()` que consulta `get_instance_details()` (1 llamada HTTP cacheada 5 min) y devuelve el texto `"NombrePerfil (número)"`. En los 8 puntos existentes donde se escribe ESTADO+FECHA+METODO (éxito y error de NOTIF_1 y NOTIF_2, en los 2 ciclos), se añade una cuarta escritura `update_cell(fila, 30|31, id_notif)`.

**Tech Stack:** Python, Streamlit (`st.cache_data`), gspread (`update_cell`), Evolution API (`get_instance_details`).

## Global Constraints

- Ambos archivos `medtify_app_v15.py` y `medtify_app_v15_chat.py` deben recibir cambios IDÉNTICOS. El único diff permitido entre ellos es la línea preexistente `EVO_API_URL_CODE` (túnel de cada máquina).
- No se crean columnas en la hoja: los encabezados "ID_NOTIFICACION_1" (AD) y "ID_NOTIFICACION_2" (AE) ya existen.
- Contenido de celda: `"NombrePerfil (número)"`; si `profile_name` vacío → solo `número`; en error → `""`. Nunca debe lanzar excepción ni bloquear el envío.
- No modificar ESTADO, FECHA, METODO ni ninguna otra lógica de envío existente.
- NO hacer `git push` (el usuario autoriza push explícitamente en cada momento).
- Commit local obligatorio al terminar cada tarea.

---

### Task 1: Helper cacheado `_cached_notificador_info`

**Files:**
- Modify: `medtify_app_v15.py` (añadir helper tras `_cached_get_messages`, ~después de la nueva función `_bandeja_previews` ya existente, antes de la sección chat; buscar el bloque de helpers con `@st.cache_data`)
- Modify: `medtify_app_v15_chat.py` (idéntico)

**Interfaces:**
- Consumes: `_evo_chat_cached(evo_url, evo_key, evo_inst, evo_safe)` decorado con `@st.cache_resource` (ya existe); `EvolutionClient.get_instance_details()` (ya existe) que devuelve dict con `phone`, `profile_name`.
- Produces: `_cached_notificador_info(evo_url, evo_key, evo_inst) -> str` — texto listo para la celda.

- [ ] **Step 1: Añadir el helper en ambos archivos**

Tras el bloque de helpers cacheados existentes, añadir exactamente:

```python
@st.cache_data(ttl=300, show_spinner=False)
def _cached_notificador_info(evo_url, evo_key, evo_inst):
    """Nombre de perfil y número de la cuenta de WhatsApp que notifica.

    Devuelve 'NombrePerfil (número)' o solo 'número' si el perfil viene
    vacío. Devuelve '' si la llamada falla (nunca bloquea el envío).
    """
    try:
        cli = _evo_chat_cached(evo_url, evo_key, evo_inst, False)
        if cli is None:
            return ""
        det = cli.get_instance_details()
        phone = str(det.get("phone", "") or "").strip()
        prof = str(det.get("profile_name", "") or "").strip()
        if prof:
            return f"{prof} ({phone})" if phone else prof
        return phone
    except Exception:
        return ""
```

- [ ] **Step 2: Verificar compilación**

```bash
python3 -m py_compile medtify_app_v15.py && python3 -m py_compile medtify_app_v15_chat.py && echo "COMPILE OK"
```
Expected: `COMPILE OK`

- [ ] **Step 3: Commit**

```bash
git add medtify_app_v15.py medtify_app_v15_chat.py
git commit -m "feat(notif): helper cached para nombre y número de la cuenta notificadora"
```

---

### Task 2: Escrituras en NOTIF_1 (columna 30/AD)

**Files:**
- Modify: `medtify_app_v15.py` — 4 puntos: ciclo 1 éxito (~2943-2948), ciclo 1 error (~2949-2954), ciclo 2 éxito (~3141-3155), ciclo 2 error (~3155+)
- Modify: `medtify_app_v15_chat.py` (idéntico)

**Interfaces:**
- Consumes: `_cached_notificador_info(evo_url, evo_key, evo_inst) -> str`.
- Produces: celdas AD escritas en éxito y error de NOTIF_1.

- [ ] **Step 1: Calcular `id_notif_1` al inicio de cada ciclo**

Justo antes del `for idx, row in df_proc.iterrows():` de cada ciclo (el mismo scope donde existen `client`, `sheet_conn`), añadir:

```python
id_notif_1 = _cached_notificador_info(
    st.session_state.get("evo_api_url", EVO_API_URL_CODE),
    st.session_state.get("evo_api_key", EVO_API_KEY_CODE),
    st.session_state.get("evo_instance", EVO_INSTANCE_CODE),
)
```

- [ ] **Step 2: Añadir escritura en los 4 bloques NOTIF_1 (éxito y error)**

En cada `try:` que ya escribe `update_cell(fila, 12, ...)`, `update_cell(fila, 13, ahora)`, `update_cell(fila, 14, "WHATSAPP")` — tanto la rama éxito como la rama error de NOTIF_1 en AMBOS ciclos — añadir como cuarta línea:

```python
sheet_conn.update_cell(fila, 30, id_notif_1)
```

- [ ] **Step 3: Verificar**

```bash
python3 -m py_compile medtify_app_v15.py && echo "COMPILE OK"
grep -n "fila, 30" medtify_app_v15.py   # 4 ocurrencias
grep -n "id_notif_1" medtify_app_v15.py # 5 ocurrencias (1 cálculo + 4 usos)
```

- [ ] **Step 4: Commit**

```bash
git add medtify_app_v15.py medtify_app_v15_chat.py
git commit -m "feat(notif): escribir ID_NOTIFICACION_1 (AD) en éxito y error"
```

---

### Task 3: Escrituras en NOTIF_2 (columna 31/AE)

**Files:**
- Modify: `medtify_app_v15.py` — 4 puntos: ciclo 1 éxito (~2899-2905), ciclo 1 error (~2908-2911), ciclo 2 éxito (~3100-3105), ciclo 2 error (~3108-3111)
- Modify: `medtify_app_v15_chat.py` (idéntico)

**Interfaces:**
- Consumes: `_cached_notificador_info(evo_url, evo_key, evo_inst) -> str`.
- Produces: celdas AE escritas en éxito y error de NOTIF_2.

- [ ] **Step 1: Calcular `id_notif_2` al inicio de cada ciclo**

Junto a `id_notif_1` (mismo bloque), añadir:

```python
id_notif_2 = _cached_notificador_info(
    st.session_state.get("evo_api_url", EVO_API_URL_CODE),
    st.session_state.get("evo_api_key", EVO_API_KEY_CODE),
    st.session_state.get("evo_instance", EVO_INSTANCE_CODE),
)
```

- [ ] **Step 2: Añadir escritura en los 4 bloques NOTIF_2 (éxito y error)**

En cada `try:` que ya escribe `update_cell(fila, 22, ...)`, `update_cell(fila, 23, ahora)`, `update_cell(fila, 24, "WHATSAPP")` — rama éxito y error de NOTIF_2 en AMBOS ciclos — añadir:

```python
sheet_conn.update_cell(fila, 30 if False else 31, id_notif_2)
```

O simplificado literal:

```python
sheet_conn.update_cell(fila, 31, id_notif_2)
```

(Puedes cualquiera de las dos formas; la segunda es la recomendada.)

- [ ] **Step 3: Verificar**

```bash
python3 -m py_compile medtify_app_v15.py && echo "COMPILE OK"
grep -n "fila, 31" medtify_app_v15.py   # 4 ocurrencias
grep -n "id_notif_2" medtify_app_v15.py # 5 ocurrencias (1 cálculo + 4 usos)
```

- [ ] **Step 4: Commit**

```bash
git add medtify_app_v15.py medtify_app_v15_chat.py
git commit -m "feat(notif): escribir ID_NOTIFICACION_2 (AE) en éxito y error"
```

---

### Task 4: Verificación de consistencia final

**Files:**
- Modify: ninguno

**Interfaces:**
- Consumes: Task 1, 2, 3 aplicadas.

- [ ] **Step 1: Verificación global**

```bash
# 1. Compilación
python3 -m py_compile medtify_app_v15.py && python3 -m py_compile medtify_app_v15_chat.py && echo "COMPILE OK"

# 2. Correlación de escrituras (8 esperadas: 4 en col 30, 4 en col 31)
grep -c "fila, 30" medtify_app_v15.py    # 4
grep -c "fila, 31" medtify_app_v15.py    # 4

# 3. Fachada idéntica (único diff permitido = túnel)
diff <(grep -v "EVO_API_URL_CODE" medtify_app_v15.py) <(grep -v "EVO_API_URL_CODE" medtify_app_v15_chat.py)   # SIN SALIDA

# 4. Sin regresiones en columnas existentes
grep -n "fila, 12\|fila, 13\|fila, 22\|fila, 23" medtify_app_v15.py   # intactas

# 5. Estado del repo
git status --short
git log --oneline -6
```

Expected: compila, 8 escrituras, diff vacío, columnas anteriores intactas.

- [ ] **Step 2: Reporte final**

Resumir: líneas modificadas, 8 escrituras ubicadas, estado del repo, commits locales creados (sin push pendiente autorizado por el usuario).

---

## Self-Review

- **Spec coverage:** Espec cubre helper cacheado (Task 1), 8 escrituras éxito+error (Tasks 2-3), criterios de aceptación (Task 4). Sin huecos.
- **Placeholder scan:** Sin TBD/TODO; todos los pasos tienen contenido concreto.
- **Type consistency:** `_cached_notificador_info(evo_url, evo_key, evo_inst) -> str` consistente en Tasks 1-4. Columnas 30/31 consistentes con AD/AE.
- Nota: `_evo_chat_cached` firma `(evo_url, evo_key, evo_inst, evo_safe)` — confirmada en código existente (línea ~555). Si en Task 1 compila, la firma es correcta.