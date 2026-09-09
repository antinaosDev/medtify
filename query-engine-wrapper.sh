#!/bin/sh
# Wrapper for Prisma query engine using proot with musl libs
# Uses ~/prisma-root/ which has musl libs and the engine binary

PREFIX=/data/data/com.termux/files/usr
ROOT=/data/data/com.termux/files/home/prisma-root
PROOT=$PREFIX/bin/proot

exec $PROOT \
  -r "$ROOT" \
  -b /dev:/dev \
  -w /tmp \
  /query-engine "$@"
