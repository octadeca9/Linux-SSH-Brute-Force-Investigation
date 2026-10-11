# Linux SSH Brute Force Investigation — SOC Analyst Lab

SOC Analyst (Easy) challenge for **hack.redlimit.id**. Participants analyse a
synthetic Linux `sshd` authentication log (`/var/log/auth.log`), identify a
brute-force pattern against an account, determine whether it succeeded, build a
timeline, and submit a triage verdict.

- **2 sections · 15 tasks · 30 points (2 pts each) · ~20–30 min**
- No SSH server, no brute-force tool, no full SIEM. Offline JSONL dataset + web
  log viewer.
- Server-side validation; ground truth never reaches the browser or the
  participant image.

Built from `PRD_Linux_SSH_Brute_Force_SOC_RedLimit.md` and
`Blueprint_Linux_SSH_Brute_Force_SOC_RedLimit.md`.

## Quick start (local)

```bash
cp .env.example .env            # optional
docker compose up --build       # override publishes 127.0.0.1:8080
```

Open <http://127.0.0.1:8080>. The `docker-compose.override.yml` maps the port on
loopback for local testing only — production access goes through the platform
gateway, not a published port.

### Modes

| `TASKS_ENABLED` | What you get |
|---|---|
| `true` (default) | Full lab: log viewer + task panel + server-side scoring. |
| `false` | **Viewer-only**: just the SSH auth-log dashboard — no task panel, no scoring, submission/session endpoints return 404, and no ground truth is required. Use when answers/scoring are handled by an external SOC platform. |

### Run tests

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
pytest                               # unit + API tests
python scripts/validate-dataset.py   # dataset vs ground-truth consistency
```

### End-to-end smoke test

```bash
./scripts/local-smoke-test.sh
```

## The 15 tasks

**Section 1 — SSH Authentication Log Fundamentals** (8 tasks)

| ID | Title | Validator |
|----|-------|-----------|
| S1-T1 | Identify the Log Source | exact_match |
| S1-T2 | Find Failed Login Events | structured_choice |
| S1-T3 | Identify the Source IP | ip_match |
| S1-T4 | Find the Target Username | normalized_string |
| S1-T5 | Detect Invalid User Attempts | integer_match |
| S1-T6 | Count Failed Password Attempts | integer_match |
| S1-T7 | Identify the First Attempt | timestamp_match |
| S1-T8 | Identify the Last Attempt | timestamp_match |

**Section 2 — SSH Brute Force Investigation and Triage** (7 tasks)

| ID | Title | Validator |
|----|-------|-----------|
| S2-T1 | Identify the Top Attacking IP | ip_match |
| S2-T2 | Determine the Attack Pattern | structured_choice |
| S2-T3 | Check for Successful Authentication | structured_choice + evidence |
| S2-T4 | Identify the Successful Login Account | normalized_string |
| S2-T5 | Build the Incident Timeline | ordered_events |
| S2-T6 | Assign Triage Priority | structured_choice |
| S2-T7 | Submit the SOC Analyst Verdict | structured_choice |

Each task is worth 2 points (max 30). Scoring is server-side; the total is
derived from `config/tasks.yaml`, not hard-coded.

## Architecture (dev baseline)

```
Browser ── HTTP ──> FastAPI app (app/main.py)
                      ├─ GET  /                 log viewer UI
                      ├─ GET  /api/meta         challenge + public tasks (no answers)
                      ├─ GET  /api/events       participant-visible dataset (JSONL)
                      ├─ POST /api/tasks/{id}/submit   server-side validation
                      ├─ GET  /api/session      progress + score
                      └─ POST /api/session/reset
                   validator (app/services/validator.py)
                      └─ reads config/ground_truth.yaml  (mounted read-only,
                         NOT baked into the image)
```

In production the validator/scoring runs as a trusted service and a spawner
creates one isolated container per session. See `docs/`.

## Layout

```
app/        FastAPI application (main, config, services, templates, static)
config/     challenge.yaml, tasks.yaml (public) + ground_truth.yaml (server-side)
dataset/    auth_events.jsonl (participant-visible, no answers)
tests/      pytest suite (dataset, validator, scoring/API, session isolation)
scripts/    validate-dataset.py, local-smoke-test.sh
docs/       deployment, api-contract, security, troubleshooting
```

> Development baseline + reference implementation. Align the API contract,
> gateway, and spawner with the real hack.redlimit.id platform before
> production. See `docs/security.md` for the trust-boundary notes.
