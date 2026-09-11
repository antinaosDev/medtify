#!/bin/sh
# ============================================================
# sync_v15.sh — Sincroniza la copia desplegada con el fuente
#
# El desarrollo se hace en medtify_app_v15_chat.py (fuente).
# Streamlit Cloud despliega medtify_app_v15.py (copia espejo).
# Este script copia el fuente a la copia desplegada y sube
# AMBOS a GitHub para que Streamlit se redeploye solo.
#
# Uso:
#   ./sync_v15.sh            → copia + push a GitHub
#   ./sync_v15.sh --no-push  → solo copia local (sin subir)
# ============================================================

cd "$(dirname "$0")"

echo "=== Sync Medtify V15 ==="
echo "Copiando medtify_app_v15_chat.py -> medtify_app_v15.py"

cp medtify_app_v15_chat.py medtify_app_v15.py
echo "  ✅ Copia lista"

# Verificar sintaxis de ambos
if command -v python >/dev/null 2>&1; then
    python -m py_compile medtify_app_v15.py medtify_app_v15_chat.py && echo "  ✅ Sintaxis OK"
else
    echo "  ⚠️ python no encontrado, se omite verificación de sintaxis"
fi

if [ "$1" = "--no-push" ]; then
    echo "Modo local: no se pushea a GitHub."
    exit 0
fi

echo "Subiendo a GitHub..."
git add medtify_app_v15.py medtify_app_v15_chat.py
git commit -m "Sync v15.py (desplegado) con v15_chat.py (fuente)"

# Rebase por si GitHub avanzó (igual que hace start_auto.sh)
git pull --rebase origin main 2>/dev/null || true

git push origin main
echo "  ✅ Push a GitHub enviado"
echo "  ⏳ Streamlit Cloud se redeployará en 1-2 minutos"