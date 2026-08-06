#!/usr/bin/env bash
# build_miniapp_rootfs.sh — operator-run mini-app rootfs builder.
#
# Docker is a BUILD-TIME host tool ONLY — it constructs the ext4 rootfs image.
# It is NEVER the mini-app runtime (mini apps boot in Firecracker microVMs).
#
# Usage:
#   scripts/build_miniapp_rootfs.sh --base            # build the base template
#   scripts/build_miniapp_rootfs.sh <app_id>          # build a per-app rootfs
#
# For <app_id>: reads the app's manifest from the DB (via a tiny Python probe),
# writes a Dockerfile (FROM base_image, pip install -r requirements, COPY the
# guest agent, non-root user), then docker build → docker create → docker export
# → mkfs.ext4 -d → $MINIAPP_ROOTFS_DIR/miniapp-<app_id>.ext4.
#
# For --base: builds data/firecracker/miniapp-base.ext4 with just Python 3.11 +
# the guest agent (used when a mini app declares no dependencies).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"

MINIAPP_ROOTFS_DIR="${MINIAPP_ROOTFS_DIR:-data/mini_app_rootfs}"
FIRECRACKER_DATA_DIR="${FIRECRACKER_DATA_DIR:-data/firecracker}"
BASE_IMAGE="${MINIAPP_BASE_IMAGE:-python:3.11-slim}"
GUEST_AGENT="core/sandbox_runtime/firecracker_guest/agent.py"

mkdir -p "$MINIAPP_ROOTFS_DIR" "$FIRECRACKER_DATA_DIR"

build_rootfs() {
  local dockerfile_dir="$1"   # dir containing Dockerfile
  local out_path="$2"         # target .ext4 path
  local container_name="miniapp-build-$(date +%s)"

  docker build -t "atom-miniapp-rootfs:latest" "$dockerfile_dir" >&2
  docker create --name "$container_name" "atom-miniapp-rootfs:latest" >/dev/null
  docker export "$container_name" > "$out_path.tar"
  docker rm "$container_name" >/dev/null
  docker image rm "atom-miniapp-rootfs:latest" >/dev/null 2>&1 || true

  rm -f "$out_path"
  mkfs.ext4 -d "$out_path.tar" -F "$out_path" >/dev/null
  rm -f "$out_path.tar"
  echo "Built rootfs → $out_path"
}

if [[ "${1:-}" == "--base" ]]; then
  BUILD_DIR="$(mktemp -d)"
  cp "$GUEST_AGENT" "$BUILD_DIR/agent.py"
  cat > "$BUILD_DIR/Dockerfile" <<EOF
FROM $BASE_IMAGE
RUN useradd -m app
COPY agent.py /opt/atom-guest/agent.py
USER app
CMD ["/usr/bin/python3", "/opt/atom-guest/agent.py"]
EOF
  build_rootfs "$BUILD_DIR" "$FIRECRACKER_DATA_DIR/miniapp-base.ext4"
  rm -rf "$BUILD_DIR"
  echo "Base template ready. Set FIRECRACKER_ROOTFS_TEMPLATE=$FIRECRACKER_DATA_DIR/miniapp-base.ext4"
  exit 0
fi

APP_ID="${1:?usage: build_miniapp_rootfs.sh <app_id> | --base}"
MANIFEST="$(PYTHONPATH="$REPO_ROOT" python - "$APP_ID" <<'PY'
import json, sys
from core.database import get_db_session
from core.models import MiniApp
app_id = sys.argv[1]
with get_db_session() as db:
    app = db.query(MiniApp).filter(MiniApp.id == app_id).first()
    if app is None:
        sys.exit("MiniApp not found: " + app_id)
    print(json.dumps(app.manifest or {}))
PY
)"
DEPS="$(echo "$MANIFEST" | python -c 'import json,sys; print("\n".join(json.load(sys.stdin).get("dependencies") or []))')"
BASE_IMAGE_FROM_MANIFEST="$(echo "$MANIFEST" | python -c 'import json,sys; print(json.load(sys.stdin).get("base_image") or "python:3.11-slim")')"

BUILD_DIR="$(mktemp -d)"
{
  echo "FROM ${BASE_IMAGE_FROM_MANIFEST}"
  echo "RUN useradd -m app"
  if [[ -n "$DEPS" ]]; then
    echo "COPY requirements.txt /tmp/requirements.txt"
    echo "RUN pip install --no-cache-dir -r /tmp/requirements.txt"
  fi
  echo "COPY agent.py /opt/atom-guest/agent.py"
  echo "USER app"
  echo 'CMD ["/usr/bin/python3", "/opt/atom-guest/agent.py"]'
} > "$BUILD_DIR/Dockerfile"
if [[ -n "$DEPS" ]]; then
  echo "$DEPS" > "$BUILD_DIR/requirements.txt"
fi
cp "$GUEST_AGENT" "$BUILD_DIR/agent.py" 2>/dev/null || true

build_rootfs "$BUILD_DIR" "$MINIAPP_ROOTFS_DIR/miniapp-$APP_ID.ext4"
rm -rf "$BUILD_DIR"
echo "Per-app rootfs ready → $MINIAPP_ROOTFS_DIR/miniapp-$APP_ID.ext4"
echo "Now publish the app (publish verifies this rootfs exists)."
