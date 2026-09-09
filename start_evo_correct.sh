#!/system/bin/sh
export HOME=/data/data/com.termux/files/home
export PREFIX=/data/data/com.termux/files/usr
export TMPDIR=$PREFIX/tmp
export PATH=$PREFIX/bin:$PATH
unset LD_PRELOAD

# Fix Prisma - use the correct ARM64 musl binary
export PRISMA_QUERY_ENGINE_BINARY=$HOME/evolution-api/node_modules/.prisma/client/query-engine-linux-musl-arm64-openssl-3.0.x
export LD_LIBRARY_PATH=$HOME/libgcc-only:$PREFIX/lib

cd $HOME/evolution-api || exit 1

rm -f $HOME/evo2_run.log
nohup node ./node_modules/tsx/dist/cli.mjs ./src/main.ts >> $HOME/evo2_run.log 2>&1 </dev/null &
echo PID=$!
sleep 25
echo "=== log tail ==="
tail -40 $HOME/evo2_run.log
echo "=== port ==="
ss -tln 2>/dev/null | grep -w 8080 || netstat -tln 2>/dev/null | grep -w 8080 || echo "no 8080 listening"
