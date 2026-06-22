#!/usr/bin/env bash
# Persist a finished Boltz run directory from POSIX /tmp to the S3-backed /workspace mirror.
#
# /workspace is not a full POSIX filesystem, so `cp -a` / direct CLI downloads into it can fail
# on metadata ops. Stream with tar and skip timestamp/permission preservation instead.
#
# Usage: scripts/persist.sh <run-dir> [run-name]
#   scripts/persist.sh /tmp/boltz-runs/ambp-1000
set -euo pipefail

SRC="${1:?usage: persist.sh <run-dir> [run-name]}"
NAME="${2:-$(basename "$SRC")}"
DEST="/workspace/boltz-artifacts/boltz/$NAME"

if [ ! -d "$SRC" ]; then
  echo "persist.sh: source run dir not found: $SRC" >&2
  exit 1
fi

mkdir -p "$DEST"
# -m (don't restore mtimes) keeps extraction working on S3-backed mounts that reject metadata ops.
tar -C "$SRC" -cf - . | tar -C "$DEST" -xmf -
echo "$DEST"
