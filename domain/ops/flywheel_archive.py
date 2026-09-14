"""Archive simulate / evaluate payloads into reports/flywheel/ (S-FLY)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
FLYWHEEL_DIR = ROOT / "reports" / "flywheel"


def archive_flywheel(kind: str, payload: dict[str, Any]) -> dict[str, str]:
    """Write timestamped + latest JSON under reports/flywheel/."""
    FLYWHEEL_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in kind) or "run"
    stamped = FLYWHEEL_DIR / f"{safe}_{ts}.json"
    latest = FLYWHEEL_DIR / f"{safe}_latest.json"
    body = {
        "archived_at": datetime.now(timezone.utc).isoformat(),
        "kind": kind,
        "payload": payload,
    }
    text = json.dumps(body, ensure_ascii=False, indent=2)
    stamped.write_text(text, encoding="utf-8")
    latest.write_text(text, encoding="utf-8")
    return {"stamped": str(stamped), "latest": str(latest)}
