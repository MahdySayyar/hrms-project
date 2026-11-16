"""Read-only architecture inventory: aggregate counts and allowlisted settings, never HR rows/secrets."""
import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import httpx
from sqlalchemy import func, inspect, select, text

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def audit(output):
    from fastapi.routing import APIRoute
    from app.database import Admin, Base, Employee, engine
    from app.main import app
    from app.security import COOKIE_SECURE, SESSION_SECONDS

    target = (ROOT / output).resolve()
    target.relative_to(ROOT)
    if target.exists():
        raise FileExistsError("Choose a new evidence name; existing evidence is preserved.")
    inspector = inspect(engine)
    schema = inspector.default_schema_name
    tables = []
    with engine.begin() as connection:
        connection.execute(text("SET TRANSACTION READ ONLY"))
        for name, table in sorted(Base.metadata.tables.items()):
            qualified = engine.dialect.identifier_preparer.quote_schema(schema) + "." + engine.dialect.identifier_preparer.quote(name)
            tables.append({"table": name, "rows": connection.scalar(select(func.count()).select_from(table)),
                "total_bytes_including_indexes": connection.scalar(text("SELECT pg_total_relation_size(CAST(:name AS regclass))"), {"name": qualified}),
                "indexes": [{"name": index["name"], "columns": index["column_names"], "unique": index["unique"]}
                            for index in inspector.get_indexes(name, schema=schema)]})
        active_accounts = connection.scalar(select(func.count()).select_from(Admin).where(Admin.is_active.is_(True)))
        seeded_employees = connection.scalar(select(func.count()).select_from(Employee).where(Employee.seed_key.is_not(None)))
        settings = {key: connection.scalar(text("SHOW " + key)) for key in
                    ("server_version", "max_connections", "shared_buffers", "work_mem")}
    availability = []
    for port in (8000, 8001):
        try:
            response = httpx.get(f"http://127.0.0.1:{port}/health", timeout=2, trust_env=False)
            availability.append({"port": port, "http_status": response.status_code})
        except httpx.HTTPError as exc:
            availability.append({"port": port, "probe_error_type": type(exc).__name__})
    source_files = []
    for folder, suffixes in (("app", {".py"}), ("templates", {".html"}), ("static", {".js", ".css"}),
                            ("scripts", {".py", ".ps1", ".mjs", ".cjs"}), ("tests", {".py"}),
                            ("specs", {".yaml"}), ("models", {".mmd"}), ("deployments", {".py", ".yaml", ".md"})):
        for path in sorted((ROOT / folder).rglob("*")):
            if path.is_file() and path.suffix in suffixes and "__pycache__" not in path.parts:
                source_files.append({"path": path.relative_to(ROOT).as_posix(), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
    payload = {"id": "ARCHITECTURE-AUDIT-20261117", "recorded_at": datetime.now(timezone.utc).isoformat(),
        "origin": "Current code/configuration and read-only aggregate PostgreSQL queries; no account/employee records or secrets exported",
        "database": {"schema": schema, "tables": tables, "settings": settings,
                     "active_account_count": active_accounts, "employee_rows_with_seed_marker": seeded_employees},
        "web_configuration": {"session_storage": "process-local dictionary", "session_seconds": SESSION_SECONDS,
                              "cookie_secure": COOKIE_SECURE, "configured_pool_size": engine.pool.size()},
        "health_probes": availability,
        "routes": [{"method": method, "path": route.path, "symbol": route.endpoint.__module__ + "." + route.endpoint.__qualname__}
                   for route in app.routes if isinstance(route, APIRoute) for method in sorted(route.methods)],
        "source_files": source_files,
        "limitations": ["Employee count is not the number of active web users", "Non-seed rows are not assumed to be real production data",
                        "No measured production RPS, latency distribution, service window, RPO or RTO is available",
                        "Health probes describe this moment after starting the native database, not historical uptime",
                        "Table byte totals are PostgreSQL allocation including indexes; they are not exported HR records"]}
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"tables": len(tables), "rows": {t["table"]: t["rows"] for t in tables},
                      "active_accounts": active_accounts, "health": availability}, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True)
    audit(parser.parse_args().output)
