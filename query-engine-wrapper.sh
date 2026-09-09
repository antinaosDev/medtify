#!/bin/sh
# Wrapper for Prisma query engine
# The binary has been patched with patchelf to use musl libs directly
ENGINE=/data/data/com.termux/files/home/evolution-api/node_modules/.prisma/client/query-engine-linux-musl-arm64-openssl-3.0.x
exec "$ENGINE" "$@"
