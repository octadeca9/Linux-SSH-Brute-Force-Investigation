# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Current state

This project is **greenfield**. Only two planning documents exist so far:

- `PRD_Linux_SSH_Brute_Force_SOC_RedLimit.md` — product + deployment requirements.
- `Blueprint_Linux_SSH_Brute_Force_SOC_RedLimit.md` — technical/development blueprint.

No application code, dataset, config, Dockerfile, or tests have been written yet.
The documents are in Indonesian; produced artifacts (code, config keys, task
instructions) follow the English conventions shown in the reference implementation below.

## Reference implementation — build by analogy

A **sibling project implements this exact architecture already**:
`../win-failed-login/` (Windows Failed Login Investigation). It is the canonical
pattern to copy. This project is the Linux/SSH analogue of it. When implementing
anything here, read the corresponding file in `../win-failed-login/` first and
adapt it — do not design from scratch.

Key differences this project must make vs. the Windows sibling:

| Aspect | win-failed-login (reference) | this project (to build) |
|---|---|---|
| Data source | Windows Security Event Log (Event IDs 4625/4624), JSON | Linux `sshd` auth log, **JSONL** (`dataset/auth_events.jsonl`) |
| Event model | `event_id`, `logon_type`, `target_user`, `source_ip` | `event_type` (`failed_password`, `invalid_user`, `accepted_password`…), `username`, `source_ip`, `message`, `event_ref` |
| Structure | 1 section · 8 tasks · 500 pts (weighted) | **2 sections · 15 tasks · 30 pts (flat 2/task)** |
| Timeline task | single window (T5 `timestamp_window`) | first/last attempt as two tasks (S1-T7/S1-T8 `timestamp_match`) + `ordered_events` (S2-T5) |

The 15 tasks (IDs S1-T1…S1-T8, S2-T1…S2-T7) and their `validator_type`s are
enumerated in the PRD §6/§14 and Blueprint §6/§8. Validator types needed:
`exact_match`, `structured_choice`, `ip_match`, `normalized_string`,
`integer_match`, `timestamp_match` (two timestamps compared individually, cf. the
reference's `timestamp_window` dict of `first`/`last`), and `ordered_events`
(new — validates a submitted sequence of `event_ref`s).

## Planned stack & commands

The reference uses **FastAPI + uvicorn + Jinja2 + pyyaml**, Python 3.12, pytest.
Mirror it. Once code exists, these are the expected commands (copy from
`../win-failed-login/`):

```bash
# Local run (docker-compose.override.yml publishes 127.0.0.1:8080)
cp .env.example .env
docker compose up --build

# Tests
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
pytest                              # unit + API tests
pytest tests/test_task_validation.py                       # one file
pytest tests/test_task_validation.py::test_name            # one test

# Dataset vs ground-truth consistency (must pass before publish)
python scripts/validate-dataset.py

# End-to-end: build, wait for /health, assert no answer-key leak, submit a task
./scripts/local-smoke-test.sh
```

## Architecture (the pattern to replicate)

Single FastAPI app (`app/main.py`) serving a web log viewer + server-side validator:

- `GET /` — log viewer UI (Jinja2 template).
- `GET /health`, `GET /readyz` — liveness + readiness (readyz reports whether
  ground truth loaded, booleans/counts only, **never answer content**).
- `GET /api/meta` — challenge metadata + **public** task definitions (no answers).
- `GET /api/events` — participant-visible dataset (no answer key).
- `POST /api/tasks/{id}/submit` — server-side validation, enforces per-task
  `max_attempts`, awards points once per task.
- `GET /api/session`, `POST /api/session/reset` — in-memory progress/score.

Module layout to reproduce under `app/`:
- `config.py` — env-var config (`DATASET_PATH`, `TASKS_ENABLED`, ground-truth sources).
- `services/loaders.py` — `lru_cache`'d loaders for dataset/challenge/tasks, plus
  `load_ground_truth()` and `public_tasks()` (strips answers before sending to browser).
- `services/validator.py` — one `_v_*` function per validator type, dispatched by
  `validator_type`; returns `ValidationResult(correct, message)`; incorrect
  messages must never reveal the expected value.
- `services/session.py` — thread-safe in-memory scoring; max_score is **derived
  by summing task points**, not hard-coded.

Config split:
- `config/challenge.yaml` + `config/tasks.yaml` — **public**, shipped in image.
- `config/ground_truth.yaml` — **server-side only**, the answer key.

## Critical invariants (security — these are the point of the design)

1. **The answer key (`ground_truth.yaml`) must never reach the participant image,
   the browser, or any API response.** The Dockerfile copies `challenge.yaml`,
   `tasks.yaml`, and `dataset/` — but *not* `ground_truth.yaml` (exclude via
   `.dockerignore`). In dev it is mounted read-only at `/run/secrets/`; in prod it
   lives in the trusted validator. The validator loads it via three fallbacks:
   `GROUND_TRUTH_B64` → `GROUND_TRUTH_YAML` → file at `GROUND_TRUTH_PATH`.
2. `scripts/local-smoke-test.sh` must assert `/api/meta` leaks no answer values —
   keep this check current with the Linux dataset's actual answers.
3. **All scoring is server-side.** The browser can never set its own score; points
   are awarded once per unique correct task.
4. Dataset uses synthetic data only — documentation IP ranges (`192.0.2.0/24`,
   `198.51.100.0/24`, `203.0.113.0/24`), ISO 8601 UTC timestamps, unique `event_ref`.
5. Container hardening (in compose, carry into prod): non-root, `read_only`,
   `cap_drop: ALL`, `no-new-privileges`, `pids_limit`, `mem_limit`, `cpus`,
   `internal: true` network (no egress), no privileged/host-net/Docker-socket.

## Viewer-only mode

`TASKS_ENABLED=false` serves only the log-viewer dashboard: no task panel, no
scoring, submission/session endpoints 404, and ground truth is never loaded.
Preserve this mode — it is used when an external SOC platform owns scoring.

## Target repo structure

See PRD §11 / Blueprint §9 for the intended tree (`app/`, `dataset/`, `config/`,
`tests/`, `scripts/`, `docs/`). It matches `../win-failed-login/` one-to-one.
