"""Copy and restore a synthetic archive inside an owned clean Compose lab."""
import json
import re
import subprocess
import time


def verify_restore(compose, source, environment, raw):
    if not re.fullmatch(r"hrms-restore-[a-z0-9-]+", environment.get("COMPOSE_PROJECT_NAME", "")):
        raise ValueError("Restore requires an owned disposable Compose project.")

    def call(*args):
        result = subprocess.run([*compose, *args], cwd=source, env=environment,
            capture_output=True, text=True, timeout=120)
        if result.returncode != 0:
            raise RuntimeError(f"Disposable restore failed during {args[0]}.")
        return result.stdout.strip()

    def db(*args):
        return call("exec", "-T", "db", *args)

    def sql(database, query):
        return db("psql", "-XAtw", "-U", "hrms_docker", "-d", database, "-v", "ON_ERROR_STOP=1", "-c", query)

    source_db, target_db = "hrms_docker", "hrms_recovery_demo"
    tables = ("admins", "employees", "hr_requests", "audit_log")

    def snapshot(database):
        return {table: json.loads(sql(database,
            f"SELECT json_build_array(count(*), md5(string_agg(to_jsonb(t)::text, chr(10) ORDER BY id))) FROM {table} AS t"))
            for table in tables}

    expected = snapshot(source_db)
    if not all(item[0] > 0 for item in expected.values()):
        raise RuntimeError("Required synthetic records were not created before the dump.")
    start = time.monotonic()
    db("pg_dump", "-w", "-U", "hrms_docker", "-d", source_db, "-Fc", "-f", "/tmp/hrms-source.dump")
    archive = raw / "synthetic-recovery.dump"
    archive_relative = "../" + archive.name
    call("cp", "db:/tmp/hrms-source.dump", archive_relative)
    backup_ms = round((time.monotonic() - start) * 1000)
    db("createdb", "-w", "-U", "hrms_docker", "--template=template0", target_db)
    blank = sql(target_db, "SELECT count(*) FROM pg_tables WHERE schemaname = 'public'") == "0"
    if not blank:
        raise RuntimeError("The isolated recovery database was not empty.")
    call("cp", archive_relative, "db:/tmp/hrms-recovery.dump")
    start = time.monotonic()
    db("pg_restore", "-w", "-U", "hrms_docker", "-d", target_db, "--single-transaction", "--exit-on-error",
        "/tmp/hrms-recovery.dump")
    restore_ms = round((time.monotonic() - start) * 1000)
    recovered = snapshot(target_db)
    approved = sql(target_db, "SELECT EXISTS (SELECT 1 FROM hr_requests r JOIN audit_log a ON a.record_id=r.id "
        "AND a.entity='hr_requests' AND a.action='review' AND a.actor_id=r.reviewed_by "
        "JOIN admins u ON u.id=r.reviewed_by WHERE r.kind='leave' AND r.status='approved' AND u.is_active)") == "t"
    checks = {"archive_nonempty": archive.stat().st_size > 0, "empty_restore_target": blank,
              **{f"restored_{table}_match": expected[table] == recovered[table] for table in tables},
              "restored_approved_leave_links_to_reviewer_and_audit": approved}
    return {"checks": checks, "synthetic_only": True, "archive_bytes": archive.stat().st_size,
            "backup_and_copy_ms": backup_ms, "pg_restore_ms": restore_ms,
            "recovered_counts": {table: result[0] for table, result in recovered.items()}}
