"""Namespace-local cooperative checkpoint helper; grants no operational authority."""
import argparse
import json
import os
from pathlib import Path
import sys
import time
import uuid


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    operations = parser.add_mutually_exclusive_group()
    operations.add_argument("--check", action="store_true")
    operations.add_argument("--tasks", action="store_true")
    operations.add_argument("--delegate", metavar="ASSIGNMENT")
    operations.add_argument("--verify", metavar="PACKET.md")
    operations.add_argument("--respond", metavar="VERIFIER_TASK_ID")
    operations.add_argument("--close-verification", metavar="VERIFIER_TASK_ID")
    parser.add_argument("--response", metavar="RESPONSE.md")
    parser.add_argument("--reason", metavar="CLOSURE.md")
    parser.add_argument("--parent", default="primary")
    args = parser.parse_args()
    if bool(args.respond) != bool(args.response) or bool(args.close_verification) != bool(args.reason):
        parser.error("--respond requires --response; --close-verification requires --reason")
    control = Path("/run/research-control")
    if args.tasks:
        print((control / "tasks.json").read_text())
        return 0
    if args.delegate or args.verify or args.respond or args.close_verification:
        owner = json.loads((control / "owner.json").read_text())
        if owner.get("task_id") != "primary":
            print("Only the primary can authorize collaboration requests.")
            return 1
        response = Path("/run/research-checkpoint")
        path = response / "delegation.json"
        previous = json.loads(path.read_text()) if path.exists() else None
        try:
            ack = json.loads((control / "delegation-ack.json").read_text())
        except (OSError, ValueError):
            ack = {}
        if previous and ack.get("nonce") != previous.get("nonce"):
            print("An assignment request is already outstanding.")
            return 1
        operation = ("verify" if args.verify else "respond" if args.respond else
                     "close" if args.close_verification else "delegate")
        request = {**owner, "assignment": args.delegate or args.verify, "parent_task": args.parent,
                   "operation": operation, "target": args.respond or args.close_verification,
                   "response": args.response, "reason": args.reason,
                   "nonce": uuid.uuid4().hex}
        temp = response / f".delegation-{request['nonce']}"
        temp.write_text(json.dumps(request) + "\n")
        os.replace(temp, path)
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            try:
                ack = json.loads((control / "delegation-ack.json").read_text())
            except (OSError, ValueError):
                ack = {}
            if ack.get("nonce") == request["nonce"]:
                print(json.dumps(ack))
                return 0 if ack.get("accepted") else 1
            time.sleep(.1)
        print("Assignment acknowledgement unavailable; inspect --tasks before retrying.")
        return 1
    request_path = control / "request.json"
    if not request_path.exists():
        print("No checkpoint requested.")
        return 0
    request = json.loads(request_path.read_text())
    if args.check:
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
