# Deployment

## Local development (Docker Compose baseline)

```bash
cp .env.example .env            # optional
docker compose up --build       # override publishes 127.0.0.1:8080
```

Open <http://127.0.0.1:8080>. `docker-compose.override.yml` maps the port on
loopback for local testing only. The base service sits on an `internal: true`
network with no host route — production access goes through the platform
gateway, never a published port.

The answer key (`config/ground_truth.yaml`) is **not** baked into the image. In
development it is bind-mounted read-only at `/run/secrets/ground_truth.yaml`
(see `docker-compose.yml`).

## Running without containers

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 127.0.0.1 --port 8080
```

## Platform-scored deploy (hack.redlimit.id / ngelinx)

When the **platform** owns scoring, deploy this app in viewer-only mode — it
serves just the SSH log dashboard and leaves answers to the platform:

- Set `TASKS_ENABLED=false`. Submission/session endpoints return 404 and the
  answer key is never loaded, so **no `GROUND_TRUTH_*` variable is required**.
- `PORT` is injected by the platform; the image honors it (default 8080).
- That is the only configuration needed. Verify with `GET /readyz` →
  `{"ready":true,"mode":"viewer-only"}`.

The answer key (`config/ground_truth.yaml`) still exists as the authoritative
source for the platform's own validator — it is just not consumed by this app.
CI reflects this: without a `GROUND_TRUTH_B64` secret, scoring/validation tests
auto-skip (marker `requires_ground_truth`) and the dataset-consistency check is
skipped, so CI stays green with no secret.

## Runtime (Docker Spawn, per participant)

Production runs one isolated container per session, spawned from a pinned,
immutable image (by digest). The spawner must:

- Apply resource limits: `cpus=0.5`, `mem_limit=256m`, `pids_limit=100`, TTL 45 min.
- Run hardened: non-root, `read_only` rootfs + tmpfs, `cap_drop: ALL`,
  `no-new-privileges`, egress default-deny, **no** Docker socket / host network /
  privileged mode.
- Label containers (`redlimit.challenge`, `redlimit.session_id`,
  `redlimit.expires_at`, `redlimit.managed_by`) — never embed email/token/secret.
- Provide ground truth at runtime via `GROUND_TRUTH_B64` / `GROUND_TRUTH_YAML`,
  or keep scoring in a separate trusted validator and run the lab in
  `TASKS_ENABLED=false` viewer-only mode.
- Stop + remove containers on reset/expiry; run a cleanup worker for orphans.

## Health & readiness

- `GET /health` — liveness (always 200 when the process is up).
- `GET /readyz` — readiness; 503 until ground truth loads (or `viewer-only` when
  `TASKS_ENABLED=false`). Returns booleans/counts only, never answer content.
