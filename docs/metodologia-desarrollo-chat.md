# Metodología de Desarrollo - Chat con Pacientes (Medtify)

## Flujo de Trabajo: Local → Validación → Push a Producción

### Principio Fundamental
**Nunca tocar la app principal (`medtify_app_v15.py`) hasta que la versión de prueba local (`medtify_app_v15_chat.py`) funcione 100% en entorno real (túnel Cloudflare + Evolution API + Google Sheets).**

### Pasos del Flujo

```
1. COPIA DE TRABAJO
   ├── medtify_app_v15.py (producción, intocable, push a GitHub/Streamlit Cloud)
   └── medtify_app_v15_chat.py (copia local, modificable, puerto 8502)

2. DESARROLLO ITERATIVO EN LOCAL
   ├── Editar medtify_app_v15_chat.py
   ├── Tests unitarios (pytest/unittest)
   ├── Verificación E2E real (script /tmp/verify_bandeja.py contra túnel real)
   └── Test manual en navegador (localhost:8502)

3. CHECKPOINT DE CALIDAD (antes de replicar)
   ├── 42/42 tests OK
   ├── Reviewer PASS (sin XSS, PII, JID consistente)
   ├── E2E: bandeja poblada, mensajes cargan, envío funciona
   └── UI validada visualmente

4. REPLICACIÓN CONTROLADA A PRODUCCIÓN
   ├── Diff medtify_app_v15_chat.py vs medtify_app_v15.py
   ├── Aplicar SOLO los cambios del módulo Chat (VISTA 6 + helpers)
   ├── Tests de regresión en producción
   └── Push a GitHub → Streamlit Cloud auto-deploy

5. ROLLBACK SEGURO
   ├── medtify_app_v15.py restaurado a HEAD si algo falla
   └── medtify_app_v15_chat.py mantiene historial de experimentos
```

---

## Estado Actual (2026-09-10)

### ✅ COMPLETADO - Fixes Críticos

| Problema | Solución | Verificación |
|----------|----------|--------------|
| **Doble slash en `_url()`** → 404 en `list_chats` | `path.lstrip('/')` en `_url()` | Tests `TestUrlJoin` + E2E 111 chats |
| **JID inconsistente** (bandeja vs `get_messages`) | `make_jid()` de `chat_helpers` en ambos | Reviewer PASS |
| **XSS en burbujas** (`unsafe_allow_html` sin escape) | `html.escape(body)` + `import html` | Reviewer PASS |
| **PII en logs** (teléfonos + `r.text[:200]`) | Logs solo con `http={code}` | Reviewer PASS |
| **Formato lista plana API 2.x** | Manejo `isinstance(data, list)` + `messages.records` | Tests + E2E |
| **Fallback `remoteJidAlt`** | Intento 1: `remoteJidAlt`, Intento 2: `remoteJid` | Código + tests |
| **Sort defensivo por timestamp** | `records.sort(key=lambda m: m.get("messageTimestamp",0) or 0, reverse=True)` | Código |
| **Preview imagen en bandeja** | `imageMessage.caption` → `"[Imagen]"` | Código |
| **Input persiste tras envío** → doble envío | `del st.session_state["chat_msg_input"]` antes de `st.rerun()` | Código |

### ✅ COMPLETADO - Optimización Rendimiento (En Progreso)

| Cuello de Botella | Fix Aplicado | Estado |
|-------------------|--------------|--------|
| `get_data_fresh()` **2× por rerun** (Sheets completo) | `@st.cache_data(ttl=90)` wrapper `_cached_get_data_fresh` | Editado |
| Sidebar **4 HTTP calls/rerun** (probe WhatsApp) | `_cached_connection_snapshot(ttl=30)` + UI desde snapshot | Editado |
| Chat tab **create_instance() cada rerun** | `@st.cache_resource _evo_chat_client` (1× por proceso) | Editado |
| `list_chats()` cada rerun | `_cached_list_chats(ttl=30)` | Editado |
| `get_messages()` cada render | `_cached_get_messages(ttl=20)` + clear al enviar | Editado |
| Log envío **3 aperturas Sheets** | 1 sola `connect_sheet` + 1 `open_by_url` + 1 `append_row` | Editado |
| `send_message` delay artificial 1.2-3s | Parámetro `delay_ms=0` para envío médico instantáneo | `evolution_client.py` ✓ |

### 🎨 PENDIENTE - Rediseño UI ("Se ve horrible")

**Objetivo**: Chat visual tipo WhatsApp/Web moderno, responsive, sin CSS externo (solo `st.html` + clases Streamlit).

| Componente | Cambio Planeado |
|------------|-----------------|
| **Cabecera conversación** | Card con avatar (iniciales), nombre, RUT/ROL tags |
| **Bandeja (izquierda)** | Botones como cards: avatar colorido, nombre bold, etiqueta, último msg, badge no-leídos |
| **Burbujas (derecha)** | Clases `.ch-bubble .ch-me` (verde, derecha) / `.ch-them` (blanco, izquierda), timestamp gris, max-width 78% |
| **Input + Enviar** | `st-key-chat_msg_input` rounded 18px, botón enviar filled, mismo radio |
| **CSS** | Inyectado 1× con `st.html` al entrar a la vista, usando selectores `[class*="st-key-bandeja_"]`, `.st-key-chat_msg_input`, `.st-key-chat_send_btn` |

---

## Archivos Clave

```
medtify_files/
├── medtify_app_v15.py              # PRODUCCIÓN (git HEAD, no tocar)
├── medtify_app_v15_chat.py         # DESARROLLO LOCAL (puerto 8502)
├── evolution_client.py             # Cliente Evolution API (compartido)
├── chat_helpers.py                 # Helpers puros (make_jid, normalizar, index)
├── tests/
│   └── test_evolution_client_chat.py  # 42 tests pasando
└── docs/
    ├── superpowers/specs/2026-09-10-chat-pacientes-design.md
    ├── superpowers/plans/2026-09-10-chat-pacientes.md
    └── metodologia-desarrollo-chat.md  # ESTE ARCHIVO
```

---

## Comandos de Verificación Rápida

```bash
cd /home/alainas/Proyectos/PROYECTOS\ PROGRAMACIÓN/salud/medtify_files

# 1. Sintaxis
./venv/bin/python -c "import ast; ast.parse(open('evolution_client.py').read()); print('evo OK')"
./venv/bin/python -c "import ast; ast.parse(open('medtify_app_v15_chat.py').read()); print('app OK')"

# 2. Tests (42 OK)
./venv/bin/python -m unittest discover -s tests -v 2>&1 | tail -5

# 3. Levantar app chat (8502)
fuser -k 8502/tcp 2>/dev/null; sleep 2
nohup ./venv/bin/streamlit run medtify_app_v15_chat.py --server.port 8502 --server.headless true > /tmp/medtify_chat.log 2>&1 &
sleep 8
curl -s -o /dev/null -w "HTTP %{http_code}\n" http://localhost:8502

# 4. E2E real
./venv/bin/python /tmp/verify_bandeja.py 2>&1 | grep -E "Chats|Matched|Bandeja"
```

---

## Próximos Pasos Inmediatos

1. **Terminar edición de `medtify_app_v15_chat.py`** (bloques: sidebar probe, chat init, mensaje render, send handler, CSS)
2. **Verificar sintaxis + tests + E2E + UI manual**
3. **Si todo OK**: replicar cambios a `medtify_app_v15.py` (solo VISTA 6 + helpers cacheados)
4. **Push a GitHub** → Streamlit Cloud deploy
5. **Validar en producción** con cuenta real

---

## Lecciones Aprendidas / Reglas de Oro

1. **Causa raíz ≠ síntoma**: Bandeja vacía → no era "sin chats" sino `_url()` con `//chat/...` (404 silenciado)
2. **JID canónico único**: Siempre `make_jid()` / `normalizar_telefono_chat()` — nunca normalización ad-hoc
3. **Cachear agresivamente en Streamlit**: `@st.cache_data(ttl=...)` + `show_spinner=False` en todo I/O externo
4. **SSR = Single Source of Render**: UI de estado (sidebar, chat) debe leer de snapshot/cache, no llamar API en render
5. **Logs sin PII**: `print(f"http={r.status_code}")` nunca `r.text[:200]` ni JIDs
6. **XSS por defecto**: Todo input de usuario → `html.escape()` antes de `unsafe_allow_html=True`
7. **Delay artificial en WhatsApp**: `delay_ms=0` para respuestas médicas; random solo para bots automatizados
8. **Documentar ANTES de replicar**: Este archivo evita re-descubrir lo ya resuelto