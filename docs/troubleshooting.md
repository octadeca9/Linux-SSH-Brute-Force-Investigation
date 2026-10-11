# Troubleshooting

### `/readyz` returns 503 `ground_truth_loaded: false`
No answer-key source resolved. In compose, confirm the mount
`./config/ground_truth.yaml:/run/secrets/ground_truth.yaml:ro` exists and
`GROUND_TRUTH_PATH` points at it. For env-only platforms set `GROUND_TRUTH_B64`
(generate with `base64 < config/ground_truth.yaml | tr -d '\n'`). The
`sources_present` block in the `/readyz` body shows what the process sees.

### Submitting a task returns 404
Either the task id is unknown, or the app is in viewer-only mode
(`TASKS_ENABLED=false`) — in that mode all task/session endpoints return 404 by
design. Check `GET /api/meta` → `tasks_enabled`.

### Submitting returns 503 "validator not configured"
`TASKS_ENABLED=true` but ground truth failed to load at submit time. Same fix as
the `/readyz` case above. The attempt is **not** consumed.

### 422 on a timestamp task
Timestamps must be timezone-aware ISO 8601. Use the trailing `Z`
(`2026-10-11T02:10:05Z`) or an explicit offset (`...+00:00`). A naive value like
`2026-10-11 02:10:05` is rejected.

### 429 attempt limit reached
Each task allows `max_attempts` (default 10) per session. Use
`POST /api/session/reset` (dev) to clear progress and attempt counters.

### Local browser can't reach the port
The base network is `internal: true`. The browser mapping comes from
`docker-compose.override.yml` (loopback `127.0.0.1:8080`). Ensure Compose picked
up the override (default behaviour) and nothing else occupies port 8080.

### `scripts/validate-dataset.py` fails
The dataset drifted from the ground truth. The error lists each mismatch (e.g.
"S1-T6 failed-count window does not match dataset"). Fix either the dataset or
the ground truth so recomputed values agree, and bump `dataset_version` /
`challenge_version` together if the content changed.
