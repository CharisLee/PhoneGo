"""A scratch workspace for one task, so what it learned survives the run.

A harness keeps its work in files: that is what makes a long task resumable, a
conclusion checkable, and a context compressible. This agent had nothing of the
kind -- everything it found lived in a five-step window and died with the run.

The directory is per phone, not per task: the point is that a later task (or the
same one, after a restart) can read what an earlier one wrote down. Files are
plain text so the model can read them with the same tools it writes them with.
"""
from __future__ import annotations

import os
import time

#: One file, appended to. One file per task would leave hundreds of them behind
#: on a phone nobody ever cleans, and the model reads the tail anyway.
NOTES = "notes.md"
#: The last finished task's answer, kept so "what did I ask yesterday" has an
#: answer that does not depend on the chat still being on screen.
LAST_RESULT = "last-result.md"

#: How much of the notes the prompt shows by default. The whole file is readable
#: with the tool; this is the part that rides along in the context.
TAIL_CHARS = 1800
#: Past this the file is rotated to notes.old.md. A chatty model writing a note
#: per round would otherwise fill the phone's storage one task at a time.
MAX_BYTES = 96 * 1024


def _path(directory: str, name: str) -> str:
    return os.path.join(directory, name)


def ensure(directory: str) -> str:
    if directory:
        try:
            os.makedirs(directory, exist_ok=True)
        except OSError:
            return ""
    return directory


def append(directory: str, title: str, text: str) -> bool:
    """Add one note; returns False when there is nowhere to write."""
    if not directory:
        return False
    ensure(directory)
    stamp = time.strftime("%m-%d %H:%M")
    head = f"\n## {title.strip() or 'note'} — {stamp}\n"
    _rotate_if_big(directory)
    try:
        with open(_path(directory, NOTES), "a", encoding="utf-8") as handle:
            handle.write(head)
            handle.write(text.strip() + "\n")
        return True
    except OSError as exc:
        print(f"[workspace] could not write a note: {exc}")
        return False


def _rotate_if_big(directory: str) -> None:
    target = _path(directory, NOTES)
    try:
        if os.path.getsize(target) < MAX_BYTES:
            return
        os.replace(target, _path(directory, "notes.old.md"))
        print("[workspace] notes rotated to notes.old.md")
    except OSError:
        pass


def read(directory: str, name: str = NOTES, limit: int = 0) -> str:
    """The notes, or the last ``limit`` characters of them."""
    if not directory:
        return ""
    try:
        with open(_path(directory, name), encoding="utf-8") as handle:
            data = handle.read()
    except OSError:
        return ""
    return data[-limit:] if limit and len(data) > limit else data


def tail(directory: str, chars: int = TAIL_CHARS) -> str:
    return read(directory, NOTES, chars).strip()


def save_result(directory: str, task: str, answer: str) -> None:
    """Keep the last answer next to the notes: it is the run's artefact."""
    if not directory:
        return
    ensure(directory)
    try:
        with open(_path(directory, LAST_RESULT), "w", encoding="utf-8") as handle:
            handle.write(f"# {task.strip()[:200]}\n\n{time.strftime('%Y-%m-%d %H:%M')}\n\n")
            handle.write(answer.strip() + "\n")
    except OSError as exc:
        print(f"[workspace] could not save the result: {exc}")
