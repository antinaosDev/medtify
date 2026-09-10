# Medtify V15 — Sistema de Notificaciones WhatsApp con Evolution API

## Descripción
Sistema de notificaciones automatizadas de WhatsApp para CESFAM Cholchol, utilizando Evolution API en lugar de Selenium/ChromeDriver.

## Arquitectura

```
┌─────────────────────────────────────────┐
│  VPS (Docker, siempre encendido)        │
│  Evolution API :8080                    │
│  PostgreSQL :5432                       │
│  Redis :6379                            │
│  Webhook Server :5001                   │
└────────────────┬────────────────────────┘
                 │ HTTP
┌────────────────┴────────────────────────┐
│  Streamlit Cloud (GRATIS)               │
│  medtify_app_v15.py                     │
│  → Usuarios abren URL en navegador      │
└─────────────────────────────────────────┘
```

## Archivos

| Archivo | Descripción |
|---------|-------------|
| `medtify_app_v15.py` | App principal (Streamlit + Evolution API) |
| `evolution_client.py` | Cliente HTTP para Evolution API |
| `launcher_v15.py` | Lanzador para .exe (opcional) |
| `requirements-v15.txt` | Dependencias Python |
| `MedtifyV15.spec` | Spec de PyInstaller (opcional) |
| `.streamlit/config.toml` | Configuración de Streamlit |

## Despliegue

### Opción A: Streamlit Cloud (Recomendado)
1. Subir a GitHub
2. Conectar en share.streamlit.io
3. Configurar secrets
4. ¡Listo!

### Opción B: .exe local
```bash
# Linux
bash build_v15.sh

# Windows
.\build_v15.ps1
```

## Secrets para Streamlit Cloud
```toml
EVOLUTION_API_URL = "http://TU_VPS_IP:8080"
EVOLUTION_API_KEY = "tu-api-key"
EVOLUTION_INSTANCE = "medtify"

[gcp_service_account]
# ... credenciales GCP
```

## Desarrollado por
Alain Antinao Sepúlveda — CESFAM Cholchol
