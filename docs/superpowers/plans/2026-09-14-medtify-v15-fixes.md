# Medtify V15 — Fix verificación (DETALLE_CONFIRMA) + Eliminar IA/Groq/PDF — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** (1) Que la columna 28 (`DETALLE_CONFIRMA`) nunca se auto-rellene con mensajes/errores de chats ajenos al paciente durante verificación; (2) eliminar completamento la IA (Groq) y el reporte PDF (FPDF) de la app v15.

**Architecture:** El bug de raíz vive en `evolution_client.py::get_last_incoming_message`: filtra mensajes solo vía `where` del lado servidor (poco fiable en Evolution API v2) y devuelve el primer mensaje entrante sin verificar el JID en cliente. Se añade verificación cliente-estricta del JID. La eliminación de IA/PDF borra bloques contiguos ya mapeados (ver design doc).

**Tech Stack:** Python 3, Streamlit, Evolution API v2 (HTTP), gspread, FPDF/Groq (a eliminar).

**Base commit:** `039e455` (rama `main`, repo medtify). Ambos `medtify_app_v15.py` y `medtify_app_v15_chat.py` son byte-idénticos (MD5 `043498a3e2147f6fc11b4eceb5958113`); `evolution_client.py` es compartido.

## Global Constraints

- Todo cambio en `medtify_app_v15.py` **debe duplicarse en `medtify_app_v15_chat.py`** (se mantienen idénticos; `diff` final debe estar vacío).
- Verificación obligatoria: `python3 -m py_compile` en los 3 archivos tocados **antes** de cada commit.
- Prohibido remover símbolos que aún se usen: verificación post-edición con `grep -rn`.
- No tocar archivos legacy (`medtify_app*.py`, `launcher*`, `build_*.sh`, spec) — fuera de alcance.
- No tocar el bloque duplicado de envío masivo (3259–3713) — fuera de alcance.
- Documentación Obsidian solo en: `Documentación Completa.md` y `Bitácora Incidentes y Soluciones.md`.

---

### Task 1: Endurecer `evolution_client.py::get_last_incoming_message` (fix de raíz)

**Files:**
- Modify: `evolution_client.py:347-421` (`get_last_incoming_message`)
- Test: `python3 -m py_compile evolution_client.py` + grep de JID

**Interfaces:**
- Consumes: `make_jid` (ya importado en el archivo; usado en `get_messages` línea 465)
- Produces: `get_last_incoming_message(numero) -> Optional[Dict]` — misma firma, ahora garantiza que el mensaje devuelto pertenece al chat `numero`

- [ ] **Step 1: Añadir verificación cliente del JID**

Antes del bucle (después de `candidates`), añadir: los `candidates` pueden venir mal filtrados por el servidor; el bucle debe saltar mensajes cuyo `key.remoteJid` / `key.remoteJidAlt` no coincidan con el JID del paciente.

Reemplazar en `get_last_incoming_message` el bloque:
```python
            for msg in candidates:
                key = msg.get("key", {}) or {}
                if key.get("fromMe"):
                    continue
```
por:
```python
            for msg in candidates:
                key = msg.get("key", {}) or {}
                if key.get("fromMe"):
                    continue
                # FIX (14-sep-2026): verificación cliente del JID — el servidor puede
                # ignorar el filtro where; jamás usar mensajes de otro chat del paciente.
                rj = str(key.get("remoteJid") or "")
                rja = str(key.get("remoteJidAlt") or "")
                if jid_sw not in rj and jid_sw not in rja:
                    continue
```
(Nota: `jid_sw` ya está construido en líneas 355–357.)

- [ ] **Step 2: Compilar y verificar**

Run: `python3 -m py_compile evolution_client.py`
Expected: exit 0. Luego `diff` no aplica (archivo único); revisar manual diff de la edición.

- [ ] **Step 3: Commit**

```bash
git add evolution_client.py
git commit -m "fix(verificacion): verificar JID del paciente en cliente para evitar leer chats ajenos (col 28)"
```

---

### Task 2: Endurecer `evolution_client.py::get_messages` (consistencia bandeja)

**Files:**
- Modify: `evolution_client.py:457-543` (`get_messages`)

**Interfaces:**
- Consumes: `make_jid(numero)` (ya presente línea 465)
- Produces: `get_messages(numero, limite=100) -> list` — mensajes que pertenecen al chat `numero`

- [ ] **Step 1: Añadir la misma verificación de JID** (misma comprobación `if jid_sw not in rj and jid_sw not in rja: continue` en su bucle de mensajes, tras el `if key.get("fromMe"): continue`).
- [ ] **Step 2: Compilar** — `python3 -m py_compile evolution_client.py` → exit 0.
- [ ] **Step 3: Commit**

```bash
git add evolution_client.py
git commit -m "fix(chat): verificar JID en get_messages para consistencia con verificación"
```

---

### Task 3: Eliminar imports IA/PDF de ambos archivos v15

**Files:**
- Modify: `medtify_app_v15.py:9,13-14` y `medtify_app_v15_chat.py:9,13-14`

- [ ] **Step 1: Borrar líneas en ambos archivos**

Eliminar:
- `from groq import Groq # Importamos la librería de IA` (línea 9)
- `import tempfile # NECESARIO PARA EL PDF` (línea 13)
- `from fpdf import FPDF # NECESARIO PARA EL PDF` (línea 14)

- [ ] **Step 2: Compilar ambos** — `python3 -m py_compile medtify_app_v15.py medtify_app_v15_chat.py` → exit 0.
- [ ] **Step 3: Commit**

```bash
git add medtify_app_v15.py medtify_app_v15_chat.py
git commit -m "refactor(ia): eliminar imports groq/fpdf/tempfile de la app v15"
```

---

### Task 4: Eliminar config IA de `load_app_configuration`

**Files:**
- Modify: `medtify_app_v15.py:310-457` y `medtify_app_v15_chat.py:310-457`

- [ ] **Step 1: Limpiar las asignaciones IA en el bloque 362–410**

Dentro de `load_app_configuration`, eliminar (conservando el resto):
- Línea 369: `estado_ia = ...`
- Líneas 371, 373, 376: `limite_gratis_conf`, `limite_pro_conf`, `limite`
- Línea 378: `config['licencia'] = {'activo': activo, 'plan': estado_ia, 'limite': limite}` → sustituir por `config['licencia'] = {'activo': activo}`
- Líneas 384–394: bloque `usos_raw` / `contador_calculado` / `config['uso_ia_actual']`
- Línea 398: `config['templates']['PROMPT'] = ...`
- Línea 400: `config['datos']['GROQ_API_KEY'] = ...`

- [ ] **Step 2: Actualizar dict template línea 315** — quitar `'uso_ia_actual': 0,`
- [ ] **Step 3: Compilar ambos** → exit 0.
- [ ] **Step 4: Commit**

```bash
git add medtify_app_v15.py medtify_app_v15_chat.py
git commit -m "refactor(ia): quitar config IA/Groq del cargador de configuración"
```

---

### Task 5: Eliminar funciones IA/PDF (`registrar_consumo_ia`, `generar_analisis_clinico`, `PDFReport`, `generate_pdf_report`)

**Files:**
- Modify: `medtify_app_v15.py:459-471, 1025-1190, 1379-1578` y `medtify_app_v15_chat.py:459-471, 1025-1190, 1379-1578`

- [ ] **Step 1: Borrar funciones en ambos archivos**

Borrar bloques:
- `registrar_consumo_ia` (459–471) + comentario previo si lo hay
- Comentarios 1025–1026 + `generar_analisis_clinico` (1027–1190)
- Comentario 1379 + clase `PDFReport` (1380–1458)
- `generate_pdf_report` (1460–1578)

- [ ] **Step 2: Compilar ambos** → exit 0.
- [ ] **Step 3: Commit**

```bash
git add medtify_app_v15.py medtify_app_v15_chat.py
git commit -m "refactor(ia): eliminar generar_analisis_clinico, PDFReport y generate_pdf_report"
```

---

### Task 6: Eliminar variables globales IA y CSS de reporte

**Files:**
- Modify: `medtify_app_v15.py:1746-1762, 1858-1874` y `medtify_app_v15_chat.py:1746-1762, 1858-1874`

- [ ] **Step 1: Limpiar bloque globales (1746–1762)**

Quitar: `GROQ_API_KEY` (1748), `AI_MODEL` (1752), init `ai_usage` (1758–1759), init `ultimo_reporte_ia` (1761–1762). Mantener comment global, `DYNAMIC_CREDS`, `URL_SHEET`, `ROW_INDEX_ADMIN`, `CUSTOM_TEMPLATES`, logos.

- [ ] **Step 2: Borrar CSS reporte IA (1858–1874)** — bloque `.report-container` / `.report-header`.
- [ ] **Step 3: Compilar ambos** → exit 0.
- [ ] **Step 4: Commit**

```bash
git add medtify_app_v15.py medtify_app_v15_chat.py
git commit -m "refactor(ia): quitar variables globales IA y estilos del reporte"
```

---

### Task 7: Eliminar sidebar de uso IA

**Files:**
- Modify: `medtify_app_v15.py:1911-1923` y `medtify_app_v15_chat.py:1911-1923`

- [ ] **Step 1: Borrar bloque uso IA en sidebar**

Eliminar `limite_diario = status['limite']` … hasta `st.warning("⚠️ Límite diario alcanzado")` (1911–1923). Dejar intactos `if status['activo']:` (1901) y el `else:` (1925) de cuenta suspendida.

- [ ] **Step 2: Compilar ambos** → exit 0.
- [ ] **Step 3: Commit**

```bash
git add medtify_app_v15.py medtify_app_v15_chat.py
git commit -m "refactor(ia): quitar medidor de uso IA del sidebar"
```

---

### Task 8: Eliminar bloque Exportar PDF del Dashboard

**Files:**
- Modify: `medtify_app_v15.py:2372-2417` y `medtify_app_v15_chat.py:2372-2417`

- [ ] **Step 1: Borrar bloque**

Eliminar desde `if st.button("📄 Exportar Reporte Ejecutivo (PDF)"):` (2372) hasta `st.success("✅ Reporte generado y crédito descontado exitosamente.")` (2417). Mantener comentario previo opcional (2368–2371) y el bloque de disponibilidad posterior (2419+).

- [ ] **Step 2: Compilar ambos** → exit 0.
- [ ] **Step 3: Commit**

```bash
git add medtify_app_v15.py medtify_app_v15_chat.py
git commit -m "refactor(pdf): eliminar botón y lógica de Exportar Reporte PDF del Dashboard"
```

---

### Task 9: Eliminar tab IA Analista y reducir tabs a 9

**Files:**
- Modify: `medtify_app_v15.py:2500-2502, 2811-2878` y `medtify_app_v15_chat.py:2500-2502, 2811-2878`

- [ ] **Step 1: Reducir lista de tabs (2500–2502)**

Cambiar de 10 a 9 tabs: quitar `"🧠 IA Analista"` de la lista. `tab9` (Policonsultantes) queda index 8; `tab8` deja de existir como variable.

- [ ] **Step 2: Borrar bloque `with tab8:` (2811–2878)** — Tab Analista Virtual completo.
- [ ] **Step 3: Verificar que no queden referencias a `tab8`, `ultimo_reporte_ia`, `ai_usage`** — `grep -n "tab8\|ultimo_reporte_ia\|ai_usage\|status\['limite'\]\|status\['plan'\]"` en ambos archivos → sin coincidencias.
- [ ] **Step 4: Compilar ambos** → exit 0.
- [ ] **Step 5: Commit**

```bash
git add medtify_app_v15.py medtify_app_v15_chat.py
git commit -m "refactor(ia): eliminar tab Analista Virtual y reducir tabs de 10 a 9"
```

---

### Task 10: Limpiar requirements

**Files:**
- Modify: `requirements.txt`, `requirements-v15.txt`

- [ ] **Step 1: Quitar líneas `groq` y `fpdf`** en ambos archivos (líneas 13–14).
- [ ] **Step 2: Verificar** — `grep -n "groq\|fpdf" requirements*.txt` → sin coincidencias.
- [ ] **Step 3: Commit**

```bash
git add requirements.txt requirements-v15.txt
git commit -m "chore(deps): quitar groq y fpdf de requirements"
```

---

### Task 11: Verificación global de eliminación + sync de archivos

**Files:** ninguno (verificación)

- [ ] **Step 1: Grep de símbolos eliminados**

Run: `grep -rn "groq\|Groq\|FPDF\|PDFReport\|generate_pdf_report\|generar_analisis_clinico\|registrar_consumo_ia\|AI_MODEL\|GROQ_API_KEY\|ultimo_reporte_ia\|tempfile\|ai_usage" medtify_app_v15.py medtify_app_v15_chat.py`
Expected: sin coincidencias.

- [ ] **Step 2: Confirmar identidad de archivos**

Run: `diff medtify_app_v15.py medtify_app_v15_chat.py && echo IDENTICOS`
Expected: `IDENTICOS`.

- [ ] **Step 3: Compilar definitivo**

Run: `python3 -m py_compile medtify_app_v15.py medtify_app_v15_chat.py evolution_client.py`
Expected: exit 0.

- [ ] **Step 4: Commit (si hubo ajustes)**

---

### Task 12: Documentar en Obsidian

**Files:**
- Modify: `/home/alainas/Proyectos/segundo-cerebro/02-Proyectos/Medtify-V15/Medtify V15 - Documentación Completa.md`
- Modify: `/home/alainas/Proyectos/segundo-cerebro/02-Proyectos/Medtify-V15/Medtify V15 - Bitácora Incidentes y Soluciones.md`

- [ ] **Step 1: Documentación Completa** — quitar "Genera reportes analíticos con IA (Groq)" del resumen, fila de IA/Groq del stack; añadir fila en Registro de Cambios: `14-09-2026 — Fix col 28 (verificación JID cliente) + eliminación IA/PDF/Groq`.
- [ ] **Step 2: Bitácora** — nuevo incidente 14-sep-2026: causa raíz (filtro servidor ignorado → chats ajenos a col 28), fix, y remoción de IA/PDF.

(push a GitHub: se hace al final, tras confirmación del usuario para redeploy de Streamlit)

---

## Self-Review

- **Cobertura spec:** Task 1–2 → bug col 28 (opción 1 aprobada). Task 3–10 → eliminación IA/PDF/Groq (toda la tabla del design doc). Task 11 → verificación. Task 12 → documentación. Cubre los 4 apartados del design.
- **Placeholder scan:** sin TBD/TODO; cada paso con acción concreta y comando de verificación.
- **Consistencia de tipos:** `get_last_incoming_message` y `get_messages` conservan firmas; `status['activo']` se preserva (Task 4 mantiene `config['licencia'] = {'activo': activo}`); `status['limite']`/`status['plan']` se eliminan junto a sus únicos usos (Tasks 7/8/9).