#!/bin/sh
# Wrapper for Prisma query engine using proot with musl libs
# Creates a persistent root at ~/prisma-root/ so it survives restarts

PREFIX=/data/data/com.termux/files/usr
HOME_DIR=/data/data/com.termux/files/home
MUSL_DIR=$HOME_DIR/prisma-engines/musl
ENGINE=$HOME_DIR/evolution-api/node_modules/.prisma/client/query-engine-linux-musl-arm64-openssl-3.0.x
PROOT=$PREFIX/bin/proot
ROOT=$HOME_DIR/prisma-root

# Create persistent root if it doesn't exist
if [ ! -d "$ROOT/lib" ]; then
    mkdir -p "$ROOT/lib" "$ROOT/tmp"
    ln -sf "$MUSL_DIR/ld-musl-aarch64.so.1" "$ROOT/lib/ld-musl-aarch64.so.1"
    ln -sf "$MUSL_DIR/libc.musl-aarch64.so.1" "$ROOT/lib/libc.musl-aarch64.so.1"
    ln -sf "$MUSL_DIR/libgcc_s.so.1" "$ROOT/lib/libgcc_s.so.1"
    ln -sf "$MUSL_DIR/libcrypto.so.3" "$ROOT/lib/libcrypto.so.3" 2>/dev/null
    ln -sf "$MUSL_DIR/libssl.so.3" "$ROOT/lib/libssl.so.3" 2>/dev/null
fi

# Copy engine binary into root (needed because proot resolves it)
cp "$ENGINE" "$ROOT/query-engine" 2>/dev/null

exec $PROOT \
  -r "$ROOT" \
  -b /dev:/dev \
  -w /tmp \
  /query-engine "$@"
