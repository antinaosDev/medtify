#!/bin/sh
# ============================================================
# MEDTIFY - Script de inicio automático (a prueba de errores)
# Inicia PostgreSQL + Evolution API + Cloudflared tunnel
# y actualiza la URL en GitHub automáticamente
#
# REGLA CLAVE: NUNCA mata el cloudflared viejo hasta que
# el nuevo URL esté confirmado funcionando desde internet.
# ============================================================

export HOME=/data/data/com.termux/files/home
export PREFIX=/data/data/com.termux/files/usr
export PATH=$PREFIX/bin:$PATH

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

# Matar procesos viejos de Evolution API (NO cloudflared)
kill $(pgrep -f "tsx.*main.ts") 2>/dev/null
kill $(pgrep -f "node.*evo") 2>/dev/null
sleep 1

# Asegurar que Prisma client esté generado correctamente
cd $HOME/evolution-api
if [ ! -f "$HOME/evolution-api/node_modules/.prisma/client/query-engine-linux-musl-arm64-openssl-3.0.x" ] || \
   [ ! -f "$HOME/evolution-api/node_modules/.prisma/client/query-engine-wrapper.sh" ]; then
    echo "  Regenerando Prisma client..."
    npx prisma generate --schema=prisma/postgresql-schema.prisma 2>&1 | tail -3
fi

# Asegurar que el binario esté patcheado con musl
PATCH=$PREFIX/bin/patchelf
ENGINE=$HOME/evolution-api/node_modules/.prisma/client/query-engine-linux-musl-arm64-openssl-3.0.x
MUSL=$HOME/prisma-engines/musl

if [ -f "$PATCH" ] && [ -f "$ENGINE" ] && [ -f "$MUSL/ld-musl-aarch64.so.1" ]; then
    # Verificar si necesita patch (el interpreter debe ser musl, no glibc)
    INTERP=$(readelf -l $ENGINE 2>/dev/null | grep "interpreter" | awk '{print $NF}' | tr -d '[]')
    if [ "$INTERP" != "$MUSL/ld-musl-aarch64.so.1" ]; then
        echo "  Patcheando binario Prisma con musl..."
        cp $ENGINE ${ENGINE}.bak 2>/dev/null
        $PATCH --set-interpreter $MUSL/ld-musl-aarch64.so.1 $ENGINE 2>/dev/null
        $PATCH --set-rpath $MUSL $ENGINE 2>/dev/null
        echo "  ✅ Binario parcheado"
    fi
fi

# Verificar que el wrapper existe
if [ ! -f "$HOME/evolution-api/node_modules/.prisma/client/query-engine-wrapper.sh" ]; then
    echo -e "  ${RED}❌ query-engine-wrapper.sh no encontrado${NC}"
    exit 1
fi
chmod +x $HOME/evolution-api/node_modules/.prisma/client/query-engine-wrapper.sh

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
# PASO 3: CLOUDFLARED TUNNEL (A PRUEBA DE ERRORES)
# ============================================
echo ""
echo -e "${GREEN}[3/5] Cloudflared tunnel...${NC}"

# LEER URL ACTUAL (la que está funcionando ahora)
OLD_URL=$(cat $HOME/cloudflared_url.txt 2>/dev/null)

# VERIFICAR SI LA URL ACTUAL SIGUE FUNCIONANDO
if [ -n "$OLD_URL" ]; then
    OLD_STATUS=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 "$OLD_URL/" 2>/dev/null)
    if [ "$OLD_STATUS" = "200" ]; then
        echo "  ✅ URL actual sigue funcionando: $OLD_URL"
        echo "  No es necesario crear un nuevo túnel."
        NEW_URL="$OLD_URL"
    else
        echo "  ⚠️  URL actual no responde ($OLD_STATUS). Creando nuevo túnel..."
        NEW_URL=""
    fi
else
    echo "  No hay URL guardada. Creando túnel..."
    NEW_URL=""
fi

# SOLO crear nuevo túnel si la URL actual no funciona
if [ -z "$NEW_URL" ]; then
    # NO matar el viejo aún - mantenerlo por si acaso
    # Iniciar cloudflared nuevo en background
    cd $HOME
    rm -f cloudflared_new.log
    nohup $PREFIX/bin/cloudflared tunnel --url http://localhost:8080 > cloudflared_new.log 2>&1 </dev/null &
    NEW_CF_PID=$!

    # Esperar URL del nuevo túnel
    echo "  Esperando nueva URL..."
    NEW_URL=""
    for i in $(seq 1 30); do
        sleep 2
        NEW_URL=$(grep -o 'https://[a-z0-9-]*.trycloudflare.com' cloudflared_new.log 2>/dev/null | head -1)
        if [ -n "$NEW_URL" ]; then
            break
        fi
    done

    if [ -z "$NEW_URL" ]; then
        echo -e "  ${RED}❌ No se obtuvo URL de Cloudflare${NC}"
        # Matar el nuevo que no funcionó
        kill $NEW_CF_PID 2>/dev/null
        # Si hay URL vieja, intentar usarla como fallback
        if [ -n "$OLD_URL" ]; then
            echo -e "  ${YELLOW}⚠️  Usando URL anterior como fallback: $OLD_URL${NC}"
            NEW_URL="$OLD_URL"
        else
            tail -10 cloudflared_new.log
            exit 1
        fi
    fi

    # Verificar que la nueva URL funciona desde internet
    echo "  Verificando nueva URL..."
    URL_OK=0
    for i in $(seq 1 15); do
        sleep 3
        HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 "$NEW_URL/" 2>/dev/null)
        if [ "$HTTP_CODE" = "200" ]; then
            echo "  ✅ Nueva URL confirmada: $NEW_URL"
            URL_OK=1
            break
        fi
        echo "  Intento $i/15 - HTTP $HTTP_CODE..."
    done

    if [ "$URL_OK" = "0" ]; then
        echo -e "  ${YELLOW}⚠️  Nueva URL no responde aún desde internet${NC}"
        # Matar el cloudflared nuevo que no sirve
        kill $NEW_CF_PID 2>/dev/null

        # Si la URL vieja existía, restaurarla
        if [ -n "$OLD_URL" ]; then
            echo -e "  ${YELLOW}⚠️  Restaurando URL anterior: $OLD_URL${NC}"
            NEW_URL="$OLD_URL"
            # Verificar que la URL vieja sigue funcionando
            OLD_CHECK=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 "$OLD_URL/" 2>/dev/null)
            if [ "$OLD_CHECK" = "200" ]; then
                echo "  ✅ URL anterior sigue activa"
            else
                echo -e "  ${RED}❌ URL anterior también caída. Espera unos minutos y vuelve a intentar.${NC}"
            fi
        else
            echo -e "  ${RED}❌ No hay URL disponible. Intenta de nuevo en 1 minuto.${NC}"
            exit 1
        fi
    else
        # La nueva URL funciona - Matar el cloudflared viejo
        if [ -n "$OLD_URL" ] && [ "$OLD_URL" != "$NEW_URL" ]; then
            echo "  Cerrando túnel anterior..."
            # Matar solo los cloudflared viejos (no el nuevo)
            for pid in $(pgrep cloudflared); do
                if [ "$pid" != "$NEW_CF_PID" ]; then
                    kill $pid 2>/dev/null
                fi
            done
        fi
    fi
fi

# Guardar URL
echo "$NEW_URL" > $HOME/cloudflared_url.txt
echo "  ✅ URL: $NEW_URL"

# ============================================
# PASO 4: VERIFICAR CONEXIÓN
# ============================================
echo ""
echo -e "${GREEN}[4/5] Verificando conexión...${NC}"

HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 15 "$NEW_URL/" 2>/dev/null)
if [ "$HTTP_CODE" = "200" ]; then
    echo "  ✅ HTTP 200 - Backend funcionando"
else
    echo -e "  ${YELLOW}⚠️  HTTP $HTTP_CODE (puede tardar unos segundos en propagarse)${NC}"
fi

# ============================================
# PASO 5: ACTUALIZAR GITHUB
# ============================================
echo ""
echo -e "${GREEN}[5/5] Actualizando GitHub...${NC}"

REPO_DIR="$HOME/medtify_repo"
if [ ! -d "$REPO_DIR" ]; then
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
    OLD_URL_CODE=$(grep -o 'EVO_API_URL_CODE = "https://[^"]*"' medtify_app_v15.py | grep -o 'https://[^"]*')
    
    if [ "$OLD_URL_CODE" != "$NEW_URL" ]; then
        echo "  URL anterior: $OLD_URL_CODE"
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
