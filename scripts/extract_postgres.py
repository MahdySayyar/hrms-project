"""فقط بخش‌های لازم PostgreSQL از بستهٔ رسمی استخراج می‌شوند."""
import zipfile
from pathlib import Path

root = Path(__file__).resolve().parent.parent
archive = root / ".runtime/downloads/postgresql-17.6-1-windows-x64-binaries.zip"
destination = root / ".runtime/postgresql"
with zipfile.ZipFile(archive) as package:
    for entry in package.infolist():
        name = entry.filename.replace("\\", "/")
        if not name.startswith(("pgsql/bin/", "pgsql/lib/", "pgsql/share/")) or entry.is_dir():
            continue
        target = (destination / name.removeprefix("pgsql/")).resolve()
        if not target.is_relative_to(destination.resolve()):
            raise RuntimeError("Unexpected path in PostgreSQL archive.")
        target.parent.mkdir(parents=True, exist_ok=True)
        with package.open(entry) as source, target.open("wb") as output:
            import shutil
            shutil.copyfileobj(source, output)
print("PostgreSQL runtime extracted to .runtime/postgresql.")
