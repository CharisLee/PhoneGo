"""The plan of a multi-app task, on disk, with its milestones ticked off.

A plan lived in memory for the length of one call: if the run was interrupted
after two of its three subtasks, the next attempt replanned from scratch and
re-did them, paying again for every screen it had already read.

``plan.json`` sits next to the run checkpoint and records each subtask with a
status. A resumed run loads it, skips what is done, and starts at the first
pending one -- which is what makes "continue" mean something on a task that
spans several apps.
"""
from __future__ import annotations

import json
import os
import time

from .atomic import write_json

PLAN_FILE = "plan.json"

PENDING = "pending"
DONE = "done"
FAILED = "failed"


def _path(directory: str) -> str:
    return os.path.join(directory, PLAN_FILE)


def save(directory: str, task: str, subtasks) -> dict:
    """Write the plan; each subtask keeps its goal, its app and its status."""
    if not directory:
        return {}
    plan = {
        "task": task,
        "created": time.time(),
        "subtasks": [
            {
                "goal": str(s.get("subtask", "")).strip(),
                "app": str(s.get("app", "")).strip(),
                "status": PENDING,
                "result": "",
            }
            for s in subtasks
            if str(s.get("subtask", "")).strip()
        ],
    }
    try:
        os.makedirs(directory, exist_ok=True)
        write_json(_path(directory), plan)
    except OSError as exc:
        print(f"[plan] could not save: {exc}")
        return {}
    return plan


def load(directory: str) -> dict:
    if not directory:
        return {}
    try:
        with open(_path(directory), encoding="utf-8") as handle:
            plan = json.load(handle)
    except (OSError, ValueError):
        return {}
    return plan if isinstance(plan, dict) else {}


def mark(directory: str, index: int, status: str, result: str = "") -> None:
    """Tick one subtask off, and write the file again."""
    plan = load(directory)
    items = plan.get("subtasks") or []
    if not (0 <= index < len(items)):
        return
    items[index]["status"] = status
    if result:
        items[index]["result"] = result[:1500]
    plan["updated"] = time.time()
    try:
        write_json(_path(directory), plan)
    except OSError as exc:
        print(f"[plan] could not update: {exc}")


def resume_point(plan: dict) -> int:
    """Index of the first subtask that is not done, or -1 when all are."""
    for index, item in enumerate(plan.get("subtasks") or []):
        if item.get("status") != DONE:
            return index
    return -1


def carry_of(plan: dict, upto: int = -1) -> str:
    """What the finished subtasks found, in order, for the next prompt."""
    parts = []
    for item in (plan.get("subtasks") or [])[:upto if upto >= 0 else None]:
        if item.get("status") == DONE and item.get("result"):
            parts.append(str(item["result"]).strip())
    return "；".join(parts)[-600:]


def summary(plan: dict) -> str:
    items = plan.get("subtasks") or []
    if not items:
        return ""
    done = sum(1 for item in items if item.get("status") == DONE)
    labels = ", ".join(
        f"{item.get('app') or '?'}:{'✓' if item.get('status') == DONE else '…'}"
        for item in items
    )
    return f"计划 {done}/{len(items)} 完成（{labels}）"
