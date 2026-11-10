# Folder contents

- [__init__.py](__init__.py) — Package marker.
- [__main__.py](__main__.py) — python -m research_pipeline entry point.
- [cli.py](cli.py) — Start/pause/resume/inspect, primary rollover, human direction, ownership recovery and cumulative accounting.
- [checkpoint.py](checkpoint.py) — Read-only namespace helper for pause/rollover readiness and acknowledgement.
- [workspace.py](workspace.py) — Intake, guarded Markdown publication, checkpoints, fingerprints and navigation.
- [isolation.py](isolation.py) — Bubblewrap/systemd launch, resource probe and descendant cleanup.
- [codex.py](codex.py) — Controlled Codex arguments, scientific prompt, private auth and bounded events.
