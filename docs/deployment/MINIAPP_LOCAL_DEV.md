# Mini Apps — Local Development Without Firecracker (macOS / desktop)

Mini apps execute **only** in Firecracker microVMs in production (see
[FIRECRACKER_HOST_SETUP.md](./FIRECRACKER_HOST_SETUP.md)). Firecracker needs
Linux KVM, so it can never run on a MacBook — which used to mean every
`mini_app_dev_run` / `mini_app_run` / `mini_app_run_tests` call failed closed
and the authoring harness could not execute anything locally.

`ATOM_MINIAAP_RUNTIME=docker-dev` enables a **DEV-ONLY** execution mode that
makes the harness work on a local machine: the same guest agent, the same
JSON-line protocol, and the same result contract as a microVM boot, with a
Docker container swapped for the microVM and pipes swapped for vsock.

## 1. Enable it

```bash
# Docker Desktop must be running (docker info succeeds)
export ATOM_MINIAAP_RUNTIME=docker-dev
scripts/restart_backend.sh   # the API server does not auto-reload
```

Nothing else is provisioned — no kernel, no ext4 rootfs, no `mkfs.ext4`
(macOS has no e2fsprogs). Dev images are built automatically on first run.

The selector **fails closed** in production: `ENVIRONMENT=production`
refuses `docker-dev` outright, and the default (`firecracker`) is unchanged.

## 2. What runs where

| | Firecracker (prod) | docker-dev (local) |
|---|---|---|
| Isolation | dedicated kernel per run (microVM) | container inside Docker Desktop's Linux VM |
| Guest agent | `firecracker_guest/agent.py` as PID 1 over vsock | the **same file** (`--stdio` branch) over stdin/stdout |
| Protocol | JSON lines: exec / callback / final (shared `guest_protocol.py`) | identical |
| Network | none (no tap device) | `--network none` |
| Filesystem | read-only rootfs drive | `--read-only` + tmpfs `/tmp` (10 MB) |
| Resources | mem / vCPU caps | `--memory` / `--cpus` (same `ATOM_SANDBOX_VM_*` knobs) |
| User | non-root `app` | non-root `app`, `--cap-drop ALL`, no-new-privileges |
| Credentials | never reach the guest (host-mediated callbacks) | identical |
| Result | `state_envelope` + `callback` audit in `metadata` | identical |

Isolation honesty: Docker on macOS shields the **Mac host** via Docker
Desktop's VM boundary, but containers share the guest kernel with each other
— weaker than a dedicated kernel per run. That is the accepted local-dev
posture (the generic `ATOM_SANDBOX_RUNTIME=docker` tier makes the same
trade); production keeps microVM isolation and refuses this mode.

## 3. Dev images

Built on demand from the same recipe `scripts/build_miniapp_rootfs.sh` uses
(`python:3.11-slim` + guest agent [+ pip deps from the manifest]), tagged by
dependency-set hash so repeat dev-runs reuse the cache and a dependency
change rebuilds:

```
atom-miniapp-dev:base            # no dependencies
atom-miniapp-dev:deps-<sha1_12>  # with dependencies (content-addressed)
```

`prepare_runtime` skips the ext4-rootfs gate under docker-dev (the
dependency security scan still gates — vulnerabilities matter in dev too),
and `mini_app_status` reports `"runtime": {"mode": "docker-dev", ...}` plus
`rootfs.required: false` so the authoring UI knows the rootfs is optional.

## 4. Verify

```bash
cd backend
python3.11 -m pytest tests/test_miniapp_dev_runtime.py -q
# 24 hermetic tests (agent stdio protocol, factory guards, run argv) run
# everywhere; 5 Docker-backed integration tests auto-skip without a daemon.

python3.11 -m pytest tests/integration/journeys/test_miniapp_dev_docker_journey.py -q
# Full authoring → mini_app_dev_run HTTP journey against a real container.
```

## 5. Troubleshooting

- **"docker-dev runtime unavailable: the Docker daemon is not reachable"** —
  start Docker Desktop and wait for `docker info` to succeed.
- **Docker Desktop "unable to start" (disk folder permission denied)** —
  Docker Desktop's *Settings → Resources → Disk image location* may point at
  an unmounted external volume; repoint it (or mount the volume) and restart
  Docker Desktop.
- **First run is slow** — the base/deps image is being built (pip install).
  Subsequent runs with the same dependency set reuse the image.
- **Stale dep images** — tags are content-addressed; `docker image prune`
  reclaims old ones.

## 6. Safety rails (recap)

- Refused outright when `ENVIRONMENT=production` (`mini_app_runtime`).
- Not a fallback anywhere by default: `ATOM_MINIAAP_RUNTIME` must be set to
  `docker-dev` explicitly; the default remains `firecracker`.
- Every result is stamped `metadata["backend"] == "docker-dev"` so audit
  logs never confuse a dev run with a microVM run.
- Integration tokens stay host-side: the container calls
  `fetch_integration` over the callback channel; the host resolves
  credentials and returns only the payload.
