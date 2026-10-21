"""Scripted stand-in for the ``claude`` CLI, used by the adapter unit tests.

Behaviour is chosen by the FAKE_CLAUDE_SCENARIO environment variable. If
FAKE_CLAUDE_RECORD is set, argv and stdin are written there as JSON.
"""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time

SESSION = "fake-session-0001"


def emit(obj: object) -> None:
    sys.stdout.write(json.dumps(obj) + "\n")
    sys.stdout.flush()


def init() -> None:
    emit({"type": "system", "subtype": "init", "session_id": SESSION, "cwd": os.getcwd()})


def result(text: str = "done", subtype: str = "success", is_error: bool = False) -> None:
    emit(
        {
            "type": "result",
            "subtype": subtype,
            "is_error": is_error,
            "result": text,
            "session_id": SESSION,
            "num_turns": 2,
            "total_cost_usd": 0.0123,
            "permission_denials": [],
        }
    )


def main() -> int:
    prompt = sys.stdin.read()
    record = os.environ.get("FAKE_CLAUDE_RECORD")
    if record:
        with open(record, "w") as fh:
            json.dump({"argv": sys.argv[1:], "stdin": prompt, "cwd": os.getcwd()}, fh)

    scenario = os.environ.get("FAKE_CLAUDE_SCENARIO", "success")

    if scenario == "success":
        init()
        emit({"type": "assistant", "message": {"content": [{"type": "text", "text": "ok"}]}})
        result(f"echo:{prompt}")
        return 0
    if scenario == "error_result":
        init()
        result("budget exceeded", subtype="error_max_budget_usd", is_error=True)
        return 0
    if scenario == "nonzero":
        init()
        sys.stderr.write("something went wrong\nfatal: boom\n")
        return 3
    if scenario == "no_result":
        init()
        return 0
    if scenario == "malformed":
        init()
        sys.stdout.write("this is not json\n[1, 2, 3]\n\n")
        sys.stdout.flush()
        result()
        return 0
    if scenario == "hang":
        init()
        time.sleep(60)
        return 0
    if scenario == "hang_ignore_term":
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
        init()
        time.sleep(60)
        return 0
    if scenario == "grandchild":
        child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
        with open(os.environ["FAKE_CLAUDE_PIDFILE"], "w") as fh:
            fh.write(str(child.pid))
        init()
        time.sleep(60)
        return 0
    if scenario == "leftover_child":
        # A background process inherits stdout and outlives the CLI.
        subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
        init()
        result()
        return 0
    if scenario == "flood":
        init()
        for i in range(50):
            emit({"type": "assistant", "n": i})
        result()
        return 0
    if scenario == "big_event":
        init()
        emit({"type": "assistant", "blob": "x" * 200_000})
        result()
        return 0
    if scenario == "huge_line":
        init()
        sys.stdout.write("y" * 300_000 + "\n")
        sys.stdout.flush()
        result()
        return 0
    if scenario == "big_result":
        init()
        result("r" * 50_000)
        return 0
    if scenario == "stderr_flood":
        sys.stderr.write("e" * 500_000 + "TAIL")
        sys.stderr.flush()
        init()
        result()
        return 0

    if scenario == "structured":
        init()
        emit(
            {
                "type": "result",
                "subtype": "success",
                "is_error": False,
                "result": '{"answer": 42}',
                "structured_output": {"answer": 42},
                "session_id": SESSION,
            }
        )
        return 0

    sys.stderr.write(f"unknown scenario {scenario}\n")
    return 99


if __name__ == "__main__":
    sys.exit(main())
