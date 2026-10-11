#!/usr/bin/env python3
"""Validate the dataset against schema rules and verify that every ground-truth
answer is recomputable from the dataset. Run before publishing a dataset_version.

Exit code 0 on success, 1 on any inconsistency.
"""
import ipaddress
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.loaders import load_challenge, load_dataset, load_ground_truth, load_tasks

REQUIRED = {"timestamp", "host", "program", "event_type", "username", "message", "event_ref"}
ALLOWED_TYPES = {
    "failed_password", "invalid_user", "accepted_password", "accepted_publickey",
    "connection_closed", "session_opened", "session_closed",
}
DOC_NETS = [ipaddress.ip_network(n) for n in ("192.0.2.0/24", "198.51.100.0/24", "203.0.113.0/24")]

errors: list[str] = []


def check(cond: bool, msg: str) -> None:
    if not cond:
        errors.append(msg)


def parse(ts: str) -> datetime:
    return datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone(timezone.utc)


def main() -> int:
    ds = load_dataset()
    events = ds["events"]
    gt = load_ground_truth()
    challenge = load_challenge()

    # --- schema --------------------------------------------------------------
    refs = Counter()
    for e in events:
        rid = e.get("event_ref", "<no-ref>")
        check(REQUIRED <= set(e), f"{rid}: missing required field(s)")
        check(e.get("event_type") in ALLOWED_TYPES, f"{rid}: bad event_type {e.get('event_type')}")
        check(str(e.get("timestamp", "")).endswith("Z"), f"{rid}: timestamp not UTC 'Z'")
        try:
            parse(e["timestamp"])
        except Exception:
            check(False, f"{rid}: unparseable timestamp")
        refs[rid] += 1
        ip = e.get("source_ip")
        if ip:
            try:
                addr = ipaddress.ip_address(ip)
                check(any(addr in n for n in DOC_NETS), f"{rid}: {ip} outside documentation ranges")
            except ValueError:
                check(False, f"{rid}: invalid source_ip {ip}")
    for rid, n in refs.items():
        check(n == 1, f"duplicate event_ref {rid} ({n}x)")

    # --- version consistency -------------------------------------------------
    check(challenge["dataset_version"] == gt["dataset_version"],
          "dataset_version mismatch between challenge.yaml and ground_truth.yaml")
    task_ids = {t["id"] for t in load_tasks()}
    check(task_ids == set(gt["tasks"]), "task ids differ between tasks.yaml and ground_truth.yaml")

    # --- recompute ground truth ---------------------------------------------
    T = gt["tasks"]

    check(sum(1 for e in events if e["event_type"] == "invalid_user") == T["S1-T5"]["expected"],
          "S1-T5 invalid_user count does not match dataset")

    failed = [e for e in events if e["event_type"] == "failed_password"]
    top_user = Counter(e["username"] for e in failed).most_common(1)[0][0]
    check(top_user == T["S1-T4"]["expected"], "S1-T4 target username is not the most-failed account")

    lo, hi = parse("2026-10-11T02:10:00Z"), parse("2026-10-11T02:20:00Z")
    window = [e for e in failed if e["username"] == "admin"
              and e.get("source_ip") == "203.0.113.77" and lo <= parse(e["timestamp"]) <= hi]
    check(len(window) == T["S1-T6"]["expected"], "S1-T6 failed-count window does not match dataset")

    burst = sorted((e for e in failed if e["username"] == "admin"
                    and e.get("source_ip") == "203.0.113.77"), key=lambda e: e["timestamp"])
    check(parse(burst[0]["timestamp"]) == parse(T["S1-T7"]["expected"]), "S1-T7 first timestamp mismatch")
    check(parse(burst[-1]["timestamp"]) == parse(T["S1-T8"]["expected"]), "S1-T8 last timestamp mismatch")

    attack_counts = Counter(e["source_ip"] for e in events
                            if e["event_type"] in ("failed_password", "invalid_user") and e.get("source_ip"))
    check(attack_counts.most_common(1)[0][0] == T["S2-T1"]["expected"], "S2-T1 top attacking IP mismatch")

    by_ref = {e["event_ref"]: e for e in events}
    success_ref = T["S2-T3"]["evidence_accepted"][0]
    check(success_ref in by_ref, f"S2-T3 evidence {success_ref} not in dataset")
    if success_ref in by_ref:
        s = by_ref[success_ref]
        check(s["event_type"].startswith("accepted_"), "S2-T3 evidence is not a successful login")
        check(s["username"] == T["S2-T4"]["expected"], "S2-T4 account != success event account")

    order = T["S2-T5"]["expected_order"]
    check(all(r in by_ref for r in order), "S2-T5 references missing from dataset")
    if all(r in by_ref for r in order):
        times = [parse(by_ref[r]["timestamp"]) for r in order]
        check(times == sorted(times), "S2-T5 expected_order is not chronological")

    # --- answer key must not be shippable via the dataset --------------------
    import json
    blob = json.dumps(ds)
    for leak in ("expected", "expected_choice", "expected_order"):
        check(leak not in blob, f"dataset envelope appears to contain '{leak}'")

    if errors:
        print(f"FAIL: {len(errors)} dataset/ground-truth problem(s):")
        for e in errors:
            print(f"  - {e}")
        return 1
    print(f"OK: {len(events)} events, {len(T)} tasks — dataset consistent with ground truth.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
