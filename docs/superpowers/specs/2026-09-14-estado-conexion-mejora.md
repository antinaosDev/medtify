# Spec: Mejora sección 📡 Estado de Conexión

Fecha: 2026-09-14
Estado: aprobado por usuario

## Objetivo

Enriquecer la sección "📡 Estado de Conexión" del panel con: avatar de perfil, batería del teléfono (nivel y si carga) y estado de conexión crudo — manteniendo número, nombre y estadísticas existentes.

## Alcance

- **Agregar**: avatar (`profile_pic`), batería (`battery_level`, `battery_plugged`).
- **Conservar**: número, nombre, estadísticas (mensajes/contactos/chats), botones de gestión, flujo de QR/no conectado/backend caído.
- **NO agregar**: nombre de instancia, fechas, integración.
- Si batería o foto no están disponibles → se omiten silenciosamente, sin romper la sección.

## Implementación

### 1. `evolution_client.py` — `check_qr_status()`

Extraer batería del `raw` con parseo tolerante y añadir al dict de retorno:
- `battery_level` (int %, 0 si no disponible)
- `battery_plugged` (bool, False si no disponible)

### 2. `_cached_connection_snapshot()` (medtify v15, ~línea 569)

Propagar campos nuevos al dict del snapshot:
- `profile_pic` (de `get_instance_details()`, ya existe en el cliente)
- `battery_level`, `battery_plugged` (del `check_qr_status()` ya llamado)

### 3. Render (medtify v15, ~líneas 1799–1822)

Cuando conectado:
- `st.image(profile_pic, width=80)` si hay foto, junto al "✅ WhatsApp Conectado"
- Número y nombre se mantienen
- Tarjeta de batería tras las estadísticas:
  - `🔋 {nivel}%` + `(cargando)` si `plugged`, `(sin cargar)` si no
  - Se omite si `battery_level` es falsy

## Criterios de aceptación

1. Con WhatsApp conectado se muestra avatar (si hay), número, nombre, estadísticas y batería.
2. Si no hay foto → no aparece imagen, resto intacto.
3. Si no hay batería → no aparece tarjeta, resto intacto.
4. Los dos v15 quedan idénticos (salvo túnel EVO_API_URL_CODE).
5. `evolution_client.py` compila y `check_qr_status` no rompe el flujo existente (connected/qrcode).
6. `py_compile` OK en ambos v15 + evolution_client.py.