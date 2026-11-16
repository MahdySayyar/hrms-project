"""Start the isolated Docker baseline; private secrets are read only at runtime."""
import os
import sys
from pathlib import Path
from urllib.parse import quote


def read_secret(name):
    path = os.environ.get(name + "_FILE")
    if not path:
        raise RuntimeError(f"Configure the {name}_FILE runtime secret.")
    value = Path(path).read_text(encoding="utf-8").strip()
    if len(value) < 12:
        raise RuntimeError(f"The {name} runtime secret is too short.")
    return value


def configure():
    password = read_secret("DB_PASSWORD")
    user = quote(os.environ.get("DB_USER", "hrms_docker"), safe="")
    database = quote(os.environ.get("DB_NAME", "hrms_docker"), safe="")
    host = os.environ.get("DB_HOST", "db")
    port = int(os.environ.get("DB_PORT", "5432"))
    os.environ["DATABASE_URL"] = f"postgresql+psycopg://{user}:{quote(password, safe='')}@{host}:{port}/{database}"
    os.environ["ADMIN_PASSWORD"] = read_secret("ADMIN_PASSWORD")


def main():
    configure()
    from app.seed import seed
    seed()
    os.environ.pop("ADMIN_PASSWORD", None)
    os.execv(sys.executable, [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"])


if __name__ == "__main__":
    main()
