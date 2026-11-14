# Folder contents

- [__init__.py](__init__.py) — Registry of drivers by backend name.
- [base.py](base.py) — Shared transport: confined CLI process, JSON lines, logging, events.
- [codex.py](codex.py) — Codex app-server driver (JSON-RPC, `turn/steer` for live messages).
- [claude.py](claude.py) — Claude Code driver (stream-json input and output).
