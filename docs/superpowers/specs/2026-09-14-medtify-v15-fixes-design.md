# Medtify V15 — Fix verificación (DETALLE_CONFIRMA) + Eliminar IA/Groq/PDF

> **Fecha:** 14-sep-2026 · **Estado:** Aprobado por usuario · **Alcance:** `medtify_app_v15.py`, `medtify_app_v15_chat.py`, `evolution_client.py`, `requirements*.txt`, docs Obsidian

## 1. Objetivo

1. **Bug:** al verificar respuestas, ante un error de lectura el detalle de otro chat (contacto test +56981775411) se escribía en la columna 28 (`DETALLE_CONFIRMA`). Requisito del usuario: **no auto-rellenar** la columna ante errores; el detalle solo se escribe cuando se leyó un mensaje real del paciente.
2. **Eliminación:** quitar todas las opciones de reporte IA, el reporte PDF (FPDF) y la sección IA (Groq).

## 2. Diagnóstico

### Causa raíz del bug (confirmada por código)

`evolution_client.py::get_last_incoming_message` (líneas 347–421) filtra mensajes **solo con el `where` del lado del servidor** (`{"key": {"remoteJidAlt": jid_sw}}` / `{"key": {"remoteJid": jid_sw}}`). Evolution API v2 aplica ese filtro de forma **poco fiable**. El bucle (390–414) devuelve el primer mensaje válido **sin re-verificar** que `key.remoteJid`/`remoteJidAlt` corresponda al paciente. Si el filtro del servidor se ignora, devuelve el mensaje entrante más reciente de cualquier chat (ej. el contacto test `56981775411`), se clasifica y en `medtify_app_v15.py` se escribe en col 28 (var. `detalle`).

El estado `AMBIGUO` (3867–3871) y los estados con detalle (3850, 3861) escriben col 28 con lo que devuelva el clasificador. La rama `except` (3877–3879) no escribe — bien —, pero la contaminación llega antes, por `verificar_respuesta` devolviendo un mensaje ajeno como si fuera del paciente.

### Confirmación adicional

- `get_messages` (457–543) tiene el mismo patrón de filtrado por servidor (usado en la bandeja de chats) — se endurece también para consistencia.
- `format_phone` vs `make_jid` pueden divergir en normalización; se unifica usando `make_jid`.

## 3. Solución propuesta (aprobada — opción 1 del usuario)

- **`evolution_client.py`:** en `get_last_incoming_message` y `get_messages`, verificar **del lado cliente** que cada mensaje devuelto pertenezca al chat del paciente (`key.remoteJid` o `key.remoteJidAlt` continga el JID construido). Los mensajes que no coincidan se ignoran. Ante error o sin mensaje del paciente → mismo comportamiento actual (PENDIENTE, no escribe col 28).
- **`medtify_app_v15.py` / `_chat.py`:** sin cambios en la lógica de escritura de columnas (ya no escribe en `except`; PENDIENTE no escribe). El arreglo de raíz está en el cliente. Se revisa/ajusta el comentario para reflejar la nueva garantía.

**Comportamiento resultante (opción 1, aprobada):** ante error de lectura o mensaje ajeno → no se toca col 28, queda el valor previo, estado `PENDIENTE`.

## 4. Eliminación IA / PDF / Groq

Bloques a borrar en ambos archivos v15 (idénticos, 4.561 líneas):

| Ítem | Líneas | Detalle |
|---|---|---|
| Import `groq` | 9 | `from groq import Groq # Importamos la librería de IA` |
| Imports PDF | 13–14 | `import tempfile` + `from fpdf import FPDF` (solo usados por PDF) |
| Config IA | 362–410 (parcial) | Quitar lectura de `ESTADO_IA`, `LIMITE_GRATIS`, `LIMITE_PRO`, `USOS_IA`, `PROMPT`, `GROQ_API_KEY`, `uso_ia_actual`; mantener licencia `activo` |
| `registrar_consumo_ia` | 459–471 | Función completa |
| `generar_analisis_clinico` | 1025–1190 | Función completa + comentarios |
| `PDFReport` | 1379–1458 | Clase completa + comentario |
| `generate_pdf_report` | 1460–1578 | Función completa |
| Variables globales | 1746–1762 | Quitar `GROQ_API_KEY`, `AI_MODEL`, `ai_usage`, `ultimo_reporte_ia`; mantener `DYNAMIC_CREDS`, `URL_SHEET`, `ROW_INDEX_ADMIN`, `CUSTOM_TEMPLATES`, logos |
| CSS reporte IA | 1858–1874 | `.report-container` / `.report-header` |
| Sidebar uso IA | 1911–1923 | Medidor créditos IA |
| Tabs | 2500–2502 | 10 tabs → 9; quitar "🧠 IA Analista" (index 8) |
| Bloque PDF Dashboard | 2372–2417 | Botón "Exportar Reporte Ejecutivo (PDF)" + toda la lógica |
| Tab IA Analista | 2811–2878 | `with tab8:` completo |
| requirements | ambos archivos | Quitar `groq` y `fpdf` (líneas 13–14) |

**Post-eliminación:** sin referencias a `groq`, `Groq`, `FPDF`, `PDFReport`, `generate_pdf_report`, `generar_analisis_clinico`, `registrar_consumo_ia`, `AI_MODEL`, `GROQ_API_KEY`, `ultimo_reporte_ia`, `tempfile`, `ai_usage`. Verificar con `grep` y `py_compile`.

## 5. Documentación

- `Medtify V15 - Documentación Completa.md`: quitar IA/Groq del resumen y stack; añadir fila al registro de cambios (14-sep-2026).
- `Medtify V15 - Bitácora Incidentes y Soluciones.md`: incidente 14-sep-2026 — bug de col 28 por filtro servidor + remoción de IA/PDF.

## 6. Verificación

- `python3 -m py_compile` sobre los 3 .py modificados (v15, v15_chat, evolution_client).
- `grep -rn` de símbolos eliminados → sin referencias.
- Revisar que ambos v15 queden idénticos (`diff`).

## 7. Fuera de alcance

- Archivos legacy con IA (`medtify_app.py`, `medtify_app copy.py`, `medtify_app_base.py`, `medtify_app_rotacion.py`, launchers, build_*.sh): no se tocan (v14/binarios no desplegados). Documentado como decisión.
- Duplicación del bloque de envío masivo (3259–3513 vs 3514–3713): no se corrige en esta iteración (no relacionado).