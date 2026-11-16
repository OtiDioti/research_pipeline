# Folder contents

- [__init__.py](__init__.py) — Registry of drivers by backend name.
- [base.py](base.py) — Shared transport: confined CLI process, JSON lines, replies to requests, the setup check, logging, events.
- [codex.py](codex.py) — Codex app-server driver (JSON-RPC, `turn/steer` for live messages) and its quota probe.
- [claude.py](claude.py) — Claude Code driver (stream-json, control requests for context and setup) and its quota probe.
