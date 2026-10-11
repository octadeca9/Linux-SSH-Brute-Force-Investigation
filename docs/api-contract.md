# API contract

This standalone lab exposes the endpoints below. In production these map onto
the official `hack.redlimit.id` platform API (session creation, ownership,
leaderboard) — the platform owns auth and is the source of truth for score.

## Lab endpoints (this app)

| Method | Path | Notes |
|---|---|---|
| GET | `/health` | Liveness. |
| GET | `/readyz` | Readiness + config diagnostics (no answer content). |
| GET | `/` | Log viewer UI. |
| GET | `/api/meta` | Challenge metadata + public tasks (no answers). |
| GET | `/api/events` | Participant-visible dataset (no answers). |
| GET | `/api/session` | Progress/score for the session. 404 in viewer-only mode. |
| POST | `/api/session/reset` | Clear progress. 404 in viewer-only mode. |
| POST | `/api/tasks/{id}/submit` | Server-side validation. 404 in viewer-only mode. |

Session binding in the dev baseline uses the `X-Session-Id` header (default
`SESSION_ID`). In production the gateway injects an authenticated,
ownership-checked session reference instead.

### Submit request

```json
{ "answer": "sample-answer" }
```

`answer` may be:
- a scalar (string/int) — e.g. `"/var/log/auth.log"`, `"10"`;
- a structured choice object — `{"choice": "yes", "evidence": "EVT-0019"}`;
- an ordered list — `{"order": ["EVT-0009", "EVT-0018", "EVT-0019"]}`.

### Submit response

```json
{
  "correct": true,
  "task_id": "S1-T1",
  "already_solved": false,
  "points_awarded": 2,
  "attempts": 1,
  "attempts_remaining": 9,
  "message": "Correct.",
  "progress": { "completed": 1, "total": 15 },
  "score": 2,
  "max_score": 30,
  "status": "running"
}
```

Status codes: `200` scored (correct or not), `422` malformed answer (consumes an
attempt, no leak), `429` attempt limit reached, `404` unknown task / viewer-only
mode, `503` validator not configured.

## Platform API mapping (proposed)

| Lab function | Platform endpoint (example) |
|---|---|
| Create session | `POST /api/challenges/{slug}/sessions` (idempotency key) |
| Read status | `GET /api/challenge-sessions/{session_id}` |
| Submit task | `POST /api/challenge-sessions/{session_id}/tasks/{task_id}/submit` |
| Reset | `POST /api/challenge-sessions/{session_id}/reset` |

Rules: auth + ownership required (session id is not ownership); TLS, rate limit,
schema validation, idempotency; score computed server-side; ground truth never
sent to the frontend; environment tokens short-lived and revocable.
