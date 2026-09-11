#!/bin/sh
# ============================================================
# update_url.sh — Actualiza manualmente el URL del backend
#
# Uso DESDE TU PC (no en Termux):
#   ./update_url.sh https://nuevo-tunel.trycloudflare.com
#
# Qué hace:
#   1. Actualiza EVO_API_URL_CODE en AMBOS archivos:
#      - medtify_app_v15.py        (lo que despliega Streamlit Cloud)
#      - medtify_app_v15_chat.py   (tu fuente local)
#      Así quedan SIEMPRE sincronizados.
#   2. Verifica sintaxis.
#   3. Pushea a GitHub → Streamlit Cloud se redeploya solo.
#      Tu versión local se actualiza al hacer git pull (o ya queda
#      actualizada en el mismo commit).
#
# Ejemplos:
#   ./update_url.sh https://avoid-purchase-former-welfare.trycloudflare.com
#   ./update_url.sh --check    → solo muestra la URL actual de ambos
# ============================================================

cd "$(dirname "$0")"

# Modo check: solo mostrar URL actual
if [ "$1" = "--check" ]; then
    echo "=== URL actual del backend ==="
    for f in medtify_app_v15.py medtify_app_v15_chat.py; do
        URL_ACTUAL=$(grep -o 'EVO_API_URL_CODE = "https://[^"]*"' "$f" 2>/dev/null | grep -o 'https://[^"]*')
        echo "  $f: ${URL_ACTUAL:-sin URL}"
    done
    exit 0
fi

NEW_URL="$1"
if [ -z "$NEW_URL" ]; then
    echo "❌ Uso: ./update_url.sh https://URL_DEL_TUNEL"
    echo "   Para ver la URL actual: ./update_url.sh --check"
    exit 1
fi

# Validar formato URL
case "$NEW_URL" in
    https://*|http://*) ;;
    *) echo "❌ La URL debe empezar con http(s)://"; exit 1 ;;
esac

echo "=== Actualizar URL backend ==="
echo "  Nueva URL: $NEW_URL"

# Actualizar en AMBOS archivos si no la tienen ya
ARCHIVOS_APP="medtify_app_v15.py medtify_app_v15_chat.py"
ARCHIVOS_A_ACTUALIZAR=$(grep -L "EVO_API_URL_CODE = \"$NEW_URL\"" $ARCHIVOS_APP 2>/dev/null || true)

if [ -z "$ARCHIVOS_A_ACTUALIZAR" ]; then
    echo "  ✅ Ambos archivos ya tienen esta URL. Nada que actualizar."
    exit 0
fi

for f in $ARCHIVOS_A_ACTUALIZAR; do
    OLD_URL_CODE=$(grep -o 'EVO_API_URL_CODE = "https://[^"]*"' "$f" | grep -o 'https://[^"]*')
    echo "  URL anterior ($f): ${OLD_URL_CODE:-sin URL}"
    sed -i "s|EVO_API_URL_CODE = \"https://[^\"]*\"|EVO_API_URL_CODE = \"$NEW_URL\"|" "$f"
    echo "  ✅ $f actualizado"
done

# Verificar sintaxis (si python está disponible)
if command -v python >/dev/null 2>&1; then
    python -m py_compile medtify_app_v15.py medtify_app_v15_chat.py && echo "  ✅ Sintaxis OK"
else
    echo "  ⚠️ python no encontrado, se omite verificación de sintaxis"
fi

echo "Subiendo a GitHub..."
git add medtify_app_v15.py medtify_app_v15_chat.py
git commit -m "Manual-update: Evolution API URL → $NEW_URL"
git pull --rebase origin main 2>/dev/null || true
git push origin main
echo "  ✅ Push a GitHub enviado"
echo "  ⏳ Streamlit Cloud se redeployará en 1-2 minutos"
echo "  📌 Tu versión local también quedó actualizada (mismo commit)"