"""Add a Redis-only secret while preserving all existing deployment secrets."""
import secrets
from pathlib import Path

from init_docker_secrets import initialize


def initialize_shared():
    initialize()
    path = Path(__file__).resolve().parent.parent / ".runtime/docker-hrms-secrets/redis_password"
    created = False
    if not path.exists():
        with path.open("x", encoding="utf-8") as output:
            output.write(secrets.token_urlsafe(32) + "\n")
        created = True
    print(f"Redis secret ready; newly created={created}. No values exported.")


if __name__ == "__main__":
    initialize_shared()
