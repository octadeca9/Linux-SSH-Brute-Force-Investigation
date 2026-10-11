# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A self-contained **SOC Analyst (Easy) lab** for `hack.redlimit.id`: participants
analyse a synthetic Linux `sshd` authentication log through a web log viewer and
answer 15 graded tasks across 2 sections (30 points, 2 per task). No live SSH
server and no brute-force tooling — the investigation runs entirely on an
offline JSONL dataset, and all answers are validated server-side.

Stack: **FastAPI + uvicorn + Jinja2 + pyyaml**, Python 3.12, pytest. Packaged as
a hardened Docker image; a dev `docker-compose` baseline runs a single instance.

## Commands

```bash
# Tests + consistency checks
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
pytest                                      # unit + API tests
pytest tests/test_task_validation.py        # one file
pytest tests/test_task_validation.py::test_correct_answers_pass   # one test
python scripts/validate-dataset.py          # dataset vs ground-truth consistency

# Run the app
uvicorn app.main:app --host 127.0.0.1 --port 8080     # native
docker compose up --build                             # container; override publishes 127.0.0.1:8080
./scripts/local-smoke-test.sh                         # build + end-to-end smoke test

# Answer-key handling for env-only platforms (e.g. ngelinx)
./scripts/gen-ground-truth-b64.sh           # emit GROUND_TRUTH_B64 (base64 of the key)
```

## Architecture

Single FastAPI app (`app/main.py`) = web log viewer + server-side validator.

- `GET /` — log viewer UI (`templates/index.html`, `static/app.js`).
- `GET /health`, `GET /readyz` — liveness + readiness; `readyz` reports whether
  ground truth loaded (booleans/counts only, **never answer content**).
- `GET /api/meta` — challenge metadata + **public** task defs (no answers).
- `GET /api/events` — participant-visible dataset (no answers).
- `POST /api/tasks/{id}/submit` — validates, enforces per-task `max_attempts`,
  awards points once per task.
- `GET /api/session`, `POST /api/session/reset` — in-memory progress/score.

Modules under `app/`:
- `config.py` — env-var config (`DATASET_PATH`, `TASKS_ENABLED`, ground-truth sources, `PORT`).
- `services/loaders.py` — `lru_cache`'d loaders for the JSONL dataset and
  challenge/task YAML; `load_ground_truth()`; `public_tasks()` strips answers.
- `services/validator.py` — one `_v_*` function per `validator_type`, dispatched
  by type; returns `ValidationResult(correct, message)`; incorrect messages
  never reveal the expected value. Types: `exact_match`, `normalized_string`,
  `ip_match`, `integer_match`, `timestamp_match`, `structured_choice`,
  `ordered_events`.
- `services/session.py` — thread-safe in-memory scoring; `max_score` is **derived
  by summing task points**, not hard-coded.

Config / data split:
- `config/challenge.yaml` + `config/tasks.yaml` — **public**, shipped in the image.
- `config/ground_truth.yaml` — **server-side answer key**; see invariants.
- `dataset/auth_events.jsonl` — participant-visible, one event per line, no answers.

## Critical invariants

1. **The answer key must never reach the participant image, the browser, or any
   API response.** `config/ground_truth.yaml` is gitignored and excluded from the
   image (`.dockerignore` + it is not `COPY`'d in the `Dockerfile`). At runtime
   the validator resolves it in order: `GROUND_TRUTH_B64` → `GROUND_TRUTH_YAML` →
   file at `GROUND_TRUTH_PATH` (read-only mount in dev compose). It is read only
   inside `loaders.load_ground_truth()` / `validator.py`. `scripts/local-smoke-test.sh`
   and `tests/test_scoring.py` assert no leak through `/api/meta` or `/api/events`
   — and that includes the task instructions and the challenge narrative (don't
   name an answer, e.g. the S1-T1 log path, in `config/challenge.yaml`).
2. **All scoring is server-side.** The browser can never set its own score;
   points are awarded once per unique correct task.
3. **Dataset ↔ ground truth must stay consistent.** Every answer is recomputable
   from `dataset/auth_events.jsonl`; `scripts/validate-dataset.py` (and
   `tests/test_dataset_schema.py`) re-derive counts/timestamps/timeline and fail
   on drift. After changing the dataset or answers, run the validator and bump
   `dataset_version` + `challenge_version` together.
4. Synthetic data only: documentation-range IPs (`192.0.2.0/24`,
   `198.51.100.0/24`, `203.0.113.0/24`), ISO 8601 UTC timestamps, unique `event_ref`.
5. Container hardening (dev compose → carry into prod): non-root, `read_only`
   rootfs + tmpfs, `cap_drop: ALL`, `no-new-privileges`, `pids_limit`,
   `mem_limit`, `cpus`, `internal: true` network. The `Dockerfile` CMD and
   healthcheck honor a platform-injected `$PORT` (default 8080).

## Viewer-only mode

`TASKS_ENABLED=false` serves only the log-viewer dashboard: no task panel, no
scoring, submission/session endpoints return 404, and ground truth is never
loaded. Use it when an external SOC platform owns scoring. Preserve this mode
when editing `main.py` / the template.

## Deployment

`docs/` covers deployment, the API contract, security/trust boundaries, and
troubleshooting. For env-only platforms (ngelinx), the only required variable is
`GROUND_TRUTH_B64` (from `scripts/gen-ground-truth-b64.sh`); `PORT` is injected
by the platform. Production runtime is one isolated container per session via a
spawner behind an authenticated gateway — not a published container port.
