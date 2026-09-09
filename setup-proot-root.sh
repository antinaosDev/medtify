#!/bin/sh
# Creates a minimal proot root with only musl libraries
# so Prisma query engine can run on Android/Termux

PREFIX=/data/data/com.termux/files/usr
MUSL_DIR=/data/data/com.termux/files/home/prisma-engines/musl
ROOT_DIR=/data/data/com.termux/files/home/prisma-root

echo "Creating proot root at $ROOT_DIR..."

# Create directory structure
mkdir -p "$ROOT_DIR/lib"
mkdir -p "$ROOT_DIR/tmp"

# Copy musl libraries
cp "$MUSL_DIR/ld-musl-aarch64.so.1" "$ROOT_DIR/lib/"
cp "$MUSL_DIR/libc.musl-aarch64.so.1" "$ROOT_DIR/lib/"
cp "$MUSL_DIR/libgcc_s.so.1" "$ROOT_DIR/lib/"

# Copy openssl libs if they exist
ls "$MUSL_DIR"/libcrypto.so.* "$ROOT_DIR/lib/" 2>/dev/null
ls "$MUSL_DIR"/libssl.so.* "$ROOT_DIR/lib/" 2>/dev/null

echo "✅ Proot root created with musl libraries"
ls -la "$ROOT_DIR/lib/"
