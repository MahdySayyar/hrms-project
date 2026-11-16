"""Create new Docker-only runtime secrets without reading or exporting native .env."""
import secrets
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def initialize():
    target = ROOT / ".runtime/docker-hrms-secrets"
    target.mkdir(parents=True, exist_ok=True)
    created = 0
    for name in ("db_password", "admin_password"):
        path = target / name
        if not path.exists():
            with path.open("x", encoding="utf-8") as output:
                output.write(secrets.token_urlsafe(32) + "\n")
            created += 1
    print(f"Docker-only secret files ready; newly created={created}. No values exported.")


if __name__ == "__main__":
    initialize()
