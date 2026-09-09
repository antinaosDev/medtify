#!/bin/sh
# Wrapper for Prisma query engine
# Unsets LD_PRELOAD to prevent Termux glibc preload from breaking musl binary
ENGINE=/data/data/com.termux/files/home/evolution-api/node_modules/.prisma/client/query-engine-linux-musl-arm64-openssl-3.0.x
unset LD_PRELOAD
exec "$ENGINE" "$@"
