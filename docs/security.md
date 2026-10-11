# Security notes

## Trust boundaries

- The browser and the participant container are **untrusted**.
- The participant-visible dataset (`dataset/auth_events.jsonl`) may live in the
  participant container. The **answer key must not**.
- Ground truth, scoring rules, and expected values live only in the trusted
  validator / server-side store.
- The spawner may manage Docker; the challenge container must never reach the
  Docker daemon.
- Access is via an authenticated gateway that validates session ownership — no
  participant container port is published to the internet.

## Answer-key handling (the core invariant)

`config/ground_truth.yaml` is excluded from the image by `.dockerignore` and is
not among the `COPY` lines in the `Dockerfile`. It is supplied at runtime via,
in order of precedence: `GROUND_TRUTH_B64` → `GROUND_TRUTH_YAML` →
`GROUND_TRUTH_PATH` (read-only mount). It is loaded only inside
`app/services/validator.py` / `loaders.load_ground_truth()` and is never placed
in any HTTP response. `/api/meta` and `/api/events` carry public data only;
`scripts/local-smoke-test.sh` and `tests/test_scoring.py` assert no leak.

## Server-side scoring

The browser can never set its own score. Points are derived from
`config/tasks.yaml` (summed, not hard-coded) and awarded once per unique correct
task. Incorrect answers never reveal the expected value; malformed answers still
consume an attempt (bounded probing) but return `422` without a leak.

## Container hardening (dev compose → carry into prod spawner)

non-root (uid 10001) · `read_only` rootfs + tmpfs `/tmp` · `cap_drop: ALL` ·
`no-new-privileges` · `pids_limit=100` · `mem_limit=256m` · `cpus=0.5` ·
`internal: true` network (egress default-deny) · no privileged / host-net /
Docker-socket. Pin the image by digest at publish time.

## Checklist

- [ ] Unique container per session.
- [ ] Participant dataset contains no answer key.
- [ ] Ground truth separate from the image; never logged, never in responses.
- [ ] Non-root; capabilities dropped; `no-new-privileges`.
- [ ] No privileged mode / host network / Docker socket.
- [ ] CPU/memory/PID/TTL limits applied.
- [ ] Egress default-deny; access via authenticated gateway.
- [ ] Submission rate/attempt limits.
- [ ] Reset/expiry revokes access and removes the container; orphan cleanup.
- [ ] Image + dependencies pinned and scanned.
- [ ] Tokens and answer keys never written to logs.
