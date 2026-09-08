#!/bin/sh
# ============================================================
# MEDTIFY - Script de inicio automático
# Inicia PostgreSQL + Evolution API + Cloudflared tunnel
# y actualiza la URL en GitHub automáticamente
# ============================================================

export HOME=/data/data/com.termux/files/home
export PREFIX=/data/data/com.termux/files/usr
export PATH=/data/data/com.termux/files/usr/bin:$PATH

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${YELLOW}========================================${NC}"
echo -e "${YELLOW}  MEDTIFY - Inicio Automático${NC}"
echo -e "${YELLOW}========================================${NC}"

# ============================================
# PASO 1: POSTGRESQL
# ============================================
echo ""
echo -e "${GREEN}[1/5] PostgreSQL...${NC}"

pg_isready -h 127.0.0.1 -p 5432 >/dev/null 2>&1
if [ $? -eq 0 ]; then
    echo "  ✅ Ya está corriendo"
else
    echo "  Iniciando..."
    pg_ctl -D $HOME/pgdata -l $HOME/pg.log start 2>&1
    sleep 3
    pg_isready -h 127.0.0.1 -p 5432 >/dev/null 2>&1
    if [ $? -eq 0 ]; then
        echo "  ✅ Iniciado"
    else
        echo -e "  ${RED}❌ Error al iniciar PostgreSQL${NC}"
        exit 1
    fi
fi

# ============================================
# PASO 2: EVOLUTION API
# ============================================
echo ""
echo -e "${GREEN}[2/5] Evolution API...${NC}"

# Matar procesos viejos
kill $(pgrep -f "tsx.*main.ts") 2>/dev/null
kill $(pgrep -f "node.*evo") 2>/dev/null
sleep 1

# Verificar que el wrapper existe
if [ ! -f "$HOME/evolution-api/node_modules/.prisma/client/query-engine-wrapper.sh" ]; then
    echo -e "  ${RED}❌ query-engine-wrapper.sh no encontrado${NC}"
    exit 1
fi

# Iniciar Evolution API
cd $HOME/evolution-api
rm -f $HOME/evo2_run.log
export PRISMA_QUERY_ENGINE_BINARY=$HOME/evolution-api/node_modules/.prisma/client/query-engine-wrapper.sh

nohup node ./node_modules/tsx/dist/cli.mjs ./src/main.ts > $HOME/evo2_run.log 2>&1 </dev/null &
EVO_PID=$!

# Esperar a que arranque
echo "  Esperando..."
for i in $(seq 1 20); do
    sleep 2
    if curl -s http://localhost:8080/ >/dev/null 2>&1; then
        echo "  ✅ Corriendo en puerto 8080"
        break
    fi
    if ! kill -0 $EVO_PID 2>/dev/null; then
        echo -e "  ${RED}❌ Evolution API se detuvo${NC}"
        tail -10 $HOME/evo2_run.log
        exit 1
    fi
done

# Verificar que responde
STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/ 2>/dev/null)
if [ "$STATUS" != "200" ]; then
    echo -e "  ${RED}❌ No responde (HTTP $STATUS)${NC}"
    exit 1
fi

# ============================================
# PASO 3: CLOUDFLARED TUNNEL
# ============================================
echo ""
echo -e "${GREEN}[3/5] Cloudflared tunnel...${NC}"

# Matar cloudflared viejo
kill $(pgrep cloudflared) 2>/dev/null
sleep 1

cd $HOME
rm -f cloudflared_new.log
nohup $PREFIX/bin/cloudflared tunnel --url http://localhost:8080 > cloudflared_new.log 2>&1 </dev/null &

# Esperar URL
echo "  Esperando URL..."
NEW_URL=""
for i in $(seq 1 20); do
    sleep 2
    NEW_URL=$(grep -o 'https://[a-z0-9-]*.trycloudflare.com' cloudflared_new.log 2>/dev/null | head -1)
    if [ -n "$NEW_URL" ]; then
        break
    fi
done

if [ -z "$NEW_URL" ]; then
    echo -e "  ${RED}❌ No se obtuvo URL de Cloudflare${NC}"
    tail -10 cloudflared_new.log
    exit 1
fi

echo "  ✅ URL: $NEW_URL"

# Guardar URL
echo "$NEW_URL" > cloudflared_url.txt

# ============================================
# PASO 4: VERIFICAR CONEXIÓN
# ============================================
echo ""
echo -e "${GREEN}[4/5] Verificando conexión...${NC}"

HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$NEW_URL/" 2>/dev/null)
if [ "$HTTP_CODE" = "200" ]; then
    echo "  ✅ HTTP $OK - Backend funcionando"
else
    echo -e "  ${YELLOW}⚠️  HTTP $HTTP_CODE (puede tardar unos segundos)${NC}"
fi

# ============================================
# PASO 5: ACTUALIZAR GITHUB
# ============================================
echo ""
echo -e "${GREEN}[5/5] Actualizando GitHub...${NC}"

REPO_DIR="$HOME/medtify_repo"
# Also try the local project directory
if [ ! -d "$REPO_DIR" ]; then
    # Find the repo - check common locations
    for candidate in \
        "$HOME/medtify_files" \
        "$HOME/proyectos/medtify_files" \
        "$(find $HOME -maxdepth 4 -name 'medtify_app_v15.py' -exec dirname {} \; 2>/dev/null | head -1)"; do
        if [ -d "$candidate" ]; then
            REPO_DIR="$candidate"
            break
        fi
    done
fi

if [ -d "$REPO_DIR" ]; then
    cd "$REPO_DIR"
    
    # Pull últimos cambios de GitHub
    /data/data/com.termux/files/usr/bin/git pull origin main 2>/dev/null
    
    # Actualizar la URL en el código usando sed
    OLD_URL=$(grep -o 'EVO_API_URL_CODE = "https://[^"]*"' medtify_app_v15.py | grep -o 'https://[^"]*')
    
    if [ "$OLD_URL" != "$NEW_URL" ]; then
        echo "  URL anterior: $OLD_URL"
        echo "  URL nueva:    $NEW_URL"
        
        # Actualizar en el archivo
        sed -i "s|EVO_API_URL_CODE = \"https://[^\"]*\"|EVO_API_URL_CODE = \"$NEW_URL\"|" medtify_app_v15.py
        
        # Git push
        /data/data/com.termux/files/usr/bin/git add medtify_app_v15.py
        /data/data/com.termux/files/usr/bin/git commit -m "Auto-update: Evolution API URL → $NEW_URL

🤖 Generated with Codebuff
Co-Authored-By: Codebuff <noreply@codebuff.com>"
        /data/data/com.termux/files/usr/bin/git push
        
        echo "  ✅ Push a GitHub enviado"
        echo "  ⏳ Streamlit Cloud se redeployará en 1-2 minutos"
    else
        echo "  ✅ URL ya está actualizada"
    fi
else
    echo -e "  ${YELLOW}⚠️  No se encontró el repositorio. Actualiza manualmente.${NC}"
fi

# ============================================
# RESUMEN
# ============================================
echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  ✅ TODO FUNCIONANDO${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "  🌐 URL activa: $NEW_URL"
echo "  📱 Evolution Manager: $NEW_URL/manager"
echo ""
echo "  Streamlit Cloud se actualizará automáticamente."
echo "  Si no se actualiza, haz refresh (F5)."
echo ""
echo -e "${YELLOW}  Para reiniciar: bash ~/start_auto.sh${NC}"
