"""Create local configuration without overwriting existing settings or printing secrets."""

import os
import secrets
from pathlib import Path

root = Path(__file__).resolve().parents[1]
runtime = root / "runtime"
runtime.mkdir(exist_ok=True)
path = runtime / "local.env"
if not path.exists():
    path.write_text(
        "DATABASE_URL=postgresql://noticeboard:local-noticeboard@127.0.0.1:55439/noticeboard\nOPENSEARCH_URL=http://127.0.0.1:19239\nNOTICEBOARD_OPS_TOKEN="
        + secrets.token_urlsafe(32)
        + "\n"
    )
    path.chmod(0o600)
compose = root / ".env"
if not compose.exists():
    compose.write_text(f"AIRFLOW_UID={os.getuid()}\n")
    compose.chmod(0o600)
print("Local configuration is ready. Existing settings were preserved.")
