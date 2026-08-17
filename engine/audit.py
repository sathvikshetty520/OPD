"""
Append-only audit log for triage decisions.

Local-first: writes to a local JSONL file so it works with no network
(low-connectivity requirement). A sync process (not implemented here)
would tail this file and push to the central server when connected.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

DEFAULT_LOG_PATH = Path(__file__).parent.parent / "data" / "audit_log.jsonl"


class AuditLog:
    def __init__(self, path: Path = DEFAULT_LOG_PATH):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, record: dict[str, Any]) -> None:
        with open(self.path, "a") as f:
            f.write(json.dumps(record) + "\n")

    def append_override(self, case_id: str, staff_id: str, new_tier: str, reason: str, timestamp: str) -> None:
        self.append({
            "type": "staff_override",
            "case_id": case_id,
            "staff_id": staff_id,
            "new_tier": new_tier,
            "reason": reason,
            "timestamp": timestamp,
        })

    def read_all(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        with open(self.path) as f:
            return [json.loads(line) for line in f if line.strip()]
