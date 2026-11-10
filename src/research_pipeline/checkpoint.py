"""Namespace-local cooperative checkpoint helper; grants no operational authority."""
import json
import os
from pathlib import Path
import sys
import time
import uuid


def main():
    control = Path("/run/research-control")
    request_path = control / "request.json"
    if not request_path.exists():
        print("No checkpoint requested.")
        return 0
    request = json.loads(request_path.read_text())
    if "--check" in sys.argv:
        reason = request.get("reason", "checkpoint").upper()
        print(f"{reason} REQUESTED: save progress and handoff, then invoke this helper without --check.")
        return 0
    response = Path("/run/research-checkpoint")
    ready = {**request, "readiness_nonce": uuid.uuid4().hex}
    temporary = response / f".ready-{ready['readiness_nonce']}"
    temporary.write_text(json.dumps(ready) + "\n")
    os.replace(temporary, response / "ready.json")
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        try:
            ack = json.loads((control / "ack.json").read_text())
        except (OSError, ValueError):
            ack = {}
        if all(ack.get(k) == v for k, v in ready.items()):
            if ack.get("accepted"):
                print("Checkpoint prepared. Finish immediately; do no further scientific work.")
                return 0
            print("Checkpoint rejected: " + ack.get("error", "invalid handoff"))
            return 1
        time.sleep(.1)
    print("No checkpoint acknowledgement before saving grace expired.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
