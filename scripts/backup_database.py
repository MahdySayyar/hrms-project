"""پشتیبان PostgreSQL با pg_dump؛ رمز به خط فرمان یا خروجی فرستاده نمی‌شود."""
import os
import subprocess
import sys
from pathlib import Path
from dotenv import dotenv_values
from sqlalchemy.engine import make_url

root = Path(__file__).resolve().parent.parent
settings = dotenv_values(root / ".env")
url = make_url(settings["DATABASE_URL"])
output = root / "artifacts/backups" / (sys.argv[1] if len(sys.argv) > 1 else "before-full-modules.dump")
output.parent.mkdir(parents=True, exist_ok=True)
if output.exists():
    raise SystemExit("Backup file already exists; choose a new name.")
subprocess.run([str(root / ".runtime/postgresql/bin/pg_dump.exe"), "-h", url.host, "-p", str(url.port), "-U", url.username, "-d", url.database, "-Fc", "-f", str(output)], env={**os.environ, "PGPASSWORD": url.password}, check=True)
print("Database backup saved:", output.name)
