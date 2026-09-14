# Mejora Sección 📡 Estado de Conexión — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Mostrar avatar y batería en la sección Estado de Conexión del panel.

**Architecture:** Cambio quirúrgico en 3 capas: `evolution_client.py` (parsear batería), `_cached_connection_snapshot()` (propagar campos), y el render del panel (mostrar avatar + batería).

**Tech Stack:** Python, Streamlit, Evolution API.

## Global Constraints

- Ambos v15 deben quedar idénticos (único diff: túnel EVO_API_URL_CODE).
- Parseo de batería tolerante: datos ausentes → se omite visualmente, nunca rompe.
- No tocar botones de gestión, flujo QR, ni lógica de envíos.
- Push autorizado por el usuario al terminar.

---

### Task 1: Parsear batería en `evolution_client.py`

**Files:**
- Modify: `evolution_client.py:115-146` (`check_qr_status`)

- [ ] **Step 1: Añadir parseo de batería al dict de retorno**

En el `return` de la rama de estado (líneas ~138-143), reemplazar:

```python
                return {
                    "connected": state == "open",
                    "state": state,
                    "qrcode": state == "close",
                    "raw": data
                }
```

Por:

```python
                # Batería (formato puede variar entre versiones de Evolution)
                _raw_batt = (data.get("instance") or data.get("state") or {}).get("battery") or {}
                if isinstance(_raw_batt, dict):
                    _batt_lvl = _raw_batt.get("battery", _raw_batt.get("level", 0))
                    _batt_plug = bool(_raw_batt.get("plugged", False))
                else:
                    _batt_lvl = 0
                    _batt_plug = False
                return {
                    "connected": state == "open",
                    "state": state,
                    "qrcode": state == "close",
                    "battery_level": _batt_lvl,
                    "battery_plugged": _batt_plug,
                    "raw": data,
                }
```

- [ ] **Step 2: Compilar**

```bash
python3 -m py_compile evolution_client.py && echo "COMPILE OK"
```

- [ ] **Step 3: Commit**

```bash
git add evolution_client.py
git commit -m "feat(evo): extraer batería en check_qr_status"
```

---

### Task 2: Propagar campos en snapshot

**Files:**
- Modify: `medtify_app_v15.py:569-591`
- Modify: `medtify_app_v15_chat.py` (idéntico)

- [ ] **Step 1: Añadir profile_pic y battery al dict de retorno**

En `_cached_connection_snapshot`, dentro del `return` con `"ok": True` (~línea 581), añadir:

```python
            "profile_pic": det.get("profile_pic", ""),
            "battery_level": qr.get("battery_level", 0),
            "battery_plugged": qr.get("battery_plugged", False),
```

- [ ] **Step 2: Aplicar lo mismo en ambos archivos**

Aplicar el cambio idéntico en `medtify_app_v15.py` y `medtify_app_v15_chat.py`.

- [ ] **Step 3: Compilar y diff**

```bash
python3 -m py_compile medtify_app_v15.py && python3 -m py_compile medtify_app_v15_chat.py && echo "COMPILE OK"
diff <(grep -v "EVO_API_URL_CODE" medtify_app_v15.py) <(grep -v "EVO_API_URL_CODE" medtify_app_v15_chat.py)
```
Expected: `COMPILE OK` + diff vacío.

- [ ] **Step 4: Commit**

```bash
git add medtify_app_v15.py medtify_app_v15_chat.py
git commit -m "feat(conexion): propagar avatar y batería en snapshot"
```

---

### Task 3: Render avatar + batería en el panel

**Files:**
- Modify: `medtify_app_v15.py:1799-1822`
- Modify: `medtify_app_v15_chat.py` (idéntico)

- [ ] **Step 1: Mostrar avatar junto al estado**

En la rama conectada, tras `st.success("✅ WhatsApp Conectado")` (y antes de `col1, col2`), añadir:

```python
            _pic = snap.get("profile_pic", "")
            if _pic:
                col_pic, col_st = st.columns([1, 3])
                with col_pic:
                    st.image(_pic, width=70)
                with col_st:
                    st.success("✅ WhatsApp Conectado")
            else:
                st.success("✅ WhatsApp Conectado")
```

- [ ] **Step 2: Añadir tarjeta de batería tras las estadísticas**

Tras el bloque de `with stats_col3:` cerrar, añadir:

```python
            _batt = int(snap.get("battery_level", 0) or 0)
            if _batt:
                _plug = "🔌 cargando" if snap.get("battery_plugged") else "sin cargar"
                st.markdown(f"**🔋 Batería:** {_batt}% · {_plug}")
```

- [ ] **Step 3: Aplicar en ambos archivos y verificar**

```bash
python3 -m py_compile medtify_app_v15.py && python3 -m py_compile medtify_app_v15_chat.py && echo "COMPILE OK"
diff <(grep -v "EVO_API_URL_CODE" medtify_app_v15.py) <(grep -v "EVO_API_URL_CODE" medtify_app_v15_chat.py)
grep -n "profile_pic\|battery_level\|battery_plugged" medtify_app_v15.py
```

- [ ] **Step 4: Commit**

```bash
git add medtify_app_v15.py medtify_app_v15_chat.py
git commit -m "feat(conexion): mostrar avatar y batería en estado de conexión"
```

---

### Task 4: Verificación + push (autorizado)

- [ ] **Step 1: Verificación final**

```bash
python3 -m py_compile evolution_client.py medtify_app_v15.py medtify_app_v15_chat.py && echo "COMPILE OK"
diff <(grep -v "EVO_API_URL_CODE" medtify_app_v15.py) <(grep -v "EVO_API_URL_CODE" medtify_app_v15_chat.py)
git status --short
git log --oneline -8
```

- [ ] **Step 2: Push autorizado**

```bash
git push origin main
```

- [ ] **Step 3: Confirmar sync**

```bash
git status -sb
```

## Self-Review

- **Spec coverage:** parseo batería (T1), propagación snapshot (T2), render avatar/batería (T3), criterios (T4). Cubierto.
- **Placeholder scan:** sin TBD; pasos concretos.
- **Type consistency:** `battery_level` (int) y `battery_plugged` (bool) consistentes entre T1/T2/T3; `profile_pic` (str) de `get_instance_details` confirmado existente en el cliente.