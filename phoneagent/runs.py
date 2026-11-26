"""A checkpoint of the run in progress, so an interrupted task can continue.

The phone kills things: a service restart, an out-of-memory kill, a user swiping
the app away, a captcha hand-over that outlives the process. Until now every one
of those meant starting the task again from zero -- the agent kept its state in
memory only.

This is the smallest thing that fixes that: one file describing what the run was
doing (the instruction, the subsay findings, the last steps, how many rounds it
had used), written atomically after every few rounds and before anything that
blocks on a person. On the next start the app can offer to continue, and the
agent receives what it had already found instead of an empty page.
"""
from __future__ import annotations

import os
import time

from .atomic import write_json

#: How many steps the checkpoint keeps. Enough to remind the model where it was,
#: short enough that the resumed prompt is not a transcript.
KEEP_STEPS = 40

RUNNING = "running"
WAITING = "waiting"      # blocked on the user (captcha, question)
DONE = "done"
FAILED = "failed"


def _path(directory: str) -> str:
    # An empty directory must mean "no checkpoint", not "a file in the process's
    # working directory": os.path.join("", name) returns a bare relative name,
    # and save() wrote it there while load() read it back.
    if not directory:
        return ""
    return os.path.join(directory, "last-run.json")


def save(directory: str, data: dict, path: str = "") -> None:
    """Write the checkpoint; a failure here must never break the task."""
    target = path or _path(directory)
    if not target:
        return
    try:
        os.makedirs(os.path.dirname(target) or ".", exist_ok=True)
        write_json(target, data)
    except OSError as exc:
        print(f"[runs] could not save the checkpoint: {exc}")


def load(directory: str, path: str = "") -> dict:
    import json

    target = path or _path(directory)
    try:
        with open(target, encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def clear(directory: str, path: str = "") -> None:
    target = path or _path(directory)
    try:
        os.remove(target)
    except OSError:
        pass


def checkpoint(*, task: str, status: str, rounds: int = 0, findings=(),
               steps=(), carry: str = "", question: str = "",
               answer: str = "", started: float = 0.0,
               package: str = "", screen_sig: str = "",
               last_action: str = "") -> dict:
    """The record written at each checkpoint."""
    return {
        "task": task,
        "status": status,
        "rounds": int(rounds),
        "started": started or time.time(),
        "updated": time.time(),
        "carry": carry[:2000],
        "findings": [str(f)[:600] for f in list(findings)[-12:]],
        "steps": [str(s)[:120] for s in list(steps)[-KEEP_STEPS:]],
        "question": question[:600],
        "answer": answer[:2000],
        # where it stopped: the app, a hash of the screen, and what it had just
        # done. A resumed run compares the screen against this before deciding
        # whether to carry on or to re-orient.
        "package": package,
        "screen_sig": screen_sig,
        "last_action": last_action[:200],
    }


def resumable(data: dict) -> bool:
    """True when this checkpoint is worth offering back to the user."""
    return bool(data) and data.get("status") in (RUNNING, WAITING) and bool(data.get("task"))


def summary(data: dict) -> str:
    """One line for the chat: what was interrupted and how far it got."""
    if not data:
        return ""
    minutes = max(0, int((time.time() - float(data.get("started") or time.time())) // 60))
    where = data.get("status") == WAITING and "在等你处理" or "中途被打断"
    return (f"上次的任务「{str(data.get('task', ''))[:40]}」{where}"
            f"（已走 {int(data.get('rounds') or 0)} 步，{minutes} 分钟前开始）")
