"""In-memory session + scoring state for the development baseline.

In production the platform backend is the source of truth for score/progress;
this module provides equivalent server-side scoring for the standalone lab so
the browser can never set its own score.
"""
from __future__ import annotations

import threading
from dataclasses import dataclass, field

from app.services.loaders import load_tasks


@dataclass
class TaskState:
    attempts: int = 0
    solved: bool = False
    points_awarded: int = 0


@dataclass
class SessionState:
    session_id: str
    tasks: dict[str, TaskState] = field(default_factory=dict)

    def reset(self) -> None:
        self.tasks = {}


class SessionStore:
    def __init__(self) -> None:
        self._lock = threading.RLock()  # reentrant: reset() calls status()
        self._sessions: dict[str, SessionState] = {}
        self._points = {t["id"]: t["points"] for t in load_tasks()}
        self._total_tasks = len(self._points)
        self._max_score = sum(self._points.values())

    def _get(self, session_id: str) -> SessionState:
        s = self._sessions.get(session_id)
        if s is None:
            s = SessionState(session_id=session_id)
            self._sessions[session_id] = s
        return s

    def task_points(self, task_id: str) -> int:
        return self._points.get(task_id, 0)

    def record_attempt(self, session_id: str, task_id: str, correct: bool) -> dict:
        """Register one attempt. Points are awarded once per task.

        Returns the submission outcome plus fresh progress/score.
        """
        with self._lock:
            session = self._get(session_id)
            ts = session.tasks.setdefault(task_id, TaskState())

            already_solved = ts.solved
            ts.attempts += 1

            if correct and not already_solved:
                ts.solved = True
                ts.points_awarded = self._points.get(task_id, 0)

            return {
                "correct": correct,
                "task_id": task_id,
                "already_solved": already_solved,
                "points_awarded": ts.points_awarded if ts.solved else 0,
                "attempts": ts.attempts,
                **self._progress(session),
            }

    def attempts_used(self, session_id: str, task_id: str) -> int:
        with self._lock:
            return self._get(session_id).tasks.get(task_id, TaskState()).attempts

    def _progress(self, session: SessionState) -> dict:
        completed = sum(1 for t in session.tasks.values() if t.solved)
        score = sum(t.points_awarded for t in session.tasks.values() if t.solved)
        return {
            "progress": {"completed": completed, "total": self._total_tasks},
            "score": score,
            "max_score": self._max_score,
            "status": "completed" if completed == self._total_tasks else "running",
        }

    def status(self, session_id: str) -> dict:
        with self._lock:
            session = self._get(session_id)
            out = {"session_id": session_id}
            out.update(self._progress(session))
            out["tasks"] = {
                tid: {"solved": st.solved, "attempts": st.attempts}
                for tid, st in session.tasks.items()
            }
            return out

    def reset(self, session_id: str) -> dict:
        with self._lock:
            self._get(session_id).reset()
            return self.status(session_id)


store = SessionStore()
