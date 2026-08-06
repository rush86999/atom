# Firecracker Host Setup — Mini-App MicroVM Runtime

Mini apps execute **only** in Firecracker microVMs. Docker is a build-time
host tool for rootfs construction and is **never** the mini-app runtime. This
guide is for the operator who provisions the host; the API never auto-builds.

## 1. Host requirements

- **Linux** with hardware virtualization: `/dev/kvm` present and usable.
- The **firecracker** binary on `PATH` (download from the [Firecracker
  releases](https://github.com/firecracker-microvm/firecracker/releases)).
- A **`vmlinux`** kernel image (download a generic x86_64/arm64 kernel).
- A base **ext4 rootfs template** (built with `--base` below).
- **e2fsprogs** (`mkfs.ext4`) and **docker** for rootfs construction.

## 2. Environment

| Var | Meaning | Default |
|---|---|---|
| `FIRECRACKER_KERNEL_IMAGE` | path to `vmlinux` | (none — required) |
| `FIRECRACKER_ROOTFS_TEMPLATE` | base ext4 rootfs (no-deps apps) | `./data/firecracker/miniapp-base.ext4` |
| `MINIAPP_ROOTFS_DIR` | per-app rootfs images | `./data/mini_app_rootfs/` |
| `ATOM_MINIAAP_RUNTIME` | must be `firecracker` | `firecracker` |
| `ATOM_MINIAAP_GUEST_PORT` | guest vsock port | `5050` |
| `ATOM_SANDBOX_VM_MEM_MB` | VM memory (MiB) | `256` |
| `ATOM_SANDBOX_VM_VCPUS` | VM vCPUs | `1` |
| `ATOM_SANDBOX_VM_BOOT_TIMEOUT_SECONDS` | boot timeout | `5` |

## 3. Build the base template (once)

```bash
scripts/build_miniapp_rootfs.sh --base
# → data/firecracker/miniapp-base.ext4 (Python 3.11 + vsock guest agent)
```

## 4. Build a per-app rootfs (after authoring an app with dependencies)

```bash
scripts/build_miniapp_rootfs.sh <app_id>
# → data/mini_app_rootfs/miniapp-<app_id>.ext4
```

`publish` fails closed unless this rootfs exists. A dependency change clears
`runtime_image`, forcing a rebuild before the next publish.

## 5. How a run works

1. The runner writes a Firecracker `config.json`:
   - `boot-source`: `kernel_image_path` + `boot_args`
     `console=ttyS0 reboot=k panic=1 pci=off init=/opt/atom-guest/agent.py miniapp_port=5050`.
   - `drives`: the app rootfs, `is_root_device=true`, `is_read_only=true`.
   - `vsock`: `{guest_cid: 3, uds_path: <run_dir>/vsock.sock}`.
2. The guest agent (PID 1) connects vsock to host CID 2, receives
   `{code, inputs}` (a single JSON line), executes with `inputs` as globals,
   and replies `{stdout, stderr, exit_code}`.
3. The host parses the `__MINIAPP_STATE__:` envelope, executes host-mediated
   `storage_ops`, upserts `CanvasState`, and kills the VM.

## 6. Security hardening

- **Read-only rootfs** — the guest cannot mutate its own filesystem.
- **No network** — no tap devices; egress is not configured for mini apps.
- **No host mounts** — all storage is host-mediated via `MiniAppStorage`.
- **Seccomp** — Firecracker applies default-deny seccomp filters.
- **Non-root user** — the guest agent runs as `app`, not root.

## 7. Real-boot smoke procedure (Linux/KVM host)

```bash
# 1. Build the base template
scripts/build_miniapp_rootfs.sh --base

# 2. Scaffold + author an app (declares e.g. pandas) via POST /api/mini-apps/scaffold

# 3. Dev-run (dry) — resolves deps + verifies rootfs, no commit
POST /api/mini-apps/{id}/dev-run

# 4. Build the per-app rootfs
scripts/build_miniapp_rootfs.sh <app_id>

# 5. Publish → Install → open canvas_id in the viewer
POST /api/mini-apps/{id}/publish
POST /api/mini-apps/{id}/install   # returns canvas_id

# 6. Upload an asset, run logic; state persists with version increments;
#    the UI updates via the WS canvas:update broadcast; a VM boots per run.
```

## 8. CI

All Firecracker execution is mocked in CI (subprocess + vsock/UDS + fs) — no
real VM/KVM is needed for `pytest tests/test_mini_apps.py
tests/test_mini_app_runtime.py`.
