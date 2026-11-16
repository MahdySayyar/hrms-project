"""Export schema and browser contracts from the actual HRMS, without exporting records or credentials."""
import argparse
import copy
import hashlib
import importlib.metadata
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml
from sqlalchemy import MetaData, inspect, text
from sqlalchemy.schema import CreateIndex, CreateTable

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def write(path, content, refresh=False):
    target = ROOT / path
    if target.exists() and not refresh:
        raise FileExistsError(f"{path} exists; use --refresh for regenerated design artifacts.")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content.rstrip() + "\n", encoding="utf-8")


def as_json(value):
    return json.dumps(value, ensure_ascii=False, indent=2)


def html_response(description):
    return {"description": description, "content": {"text/html": {"schema": {"type": "string"}}}}


def export(refresh=False):
    from fastapi.routing import APIRoute
    from app.main import app
    from app.database import Base, engine
    from app.module_forms import MODULES
    from app.security import COOKIE_NAME
    from app import hr_models  # register all mapped tables

    contracts = yaml.safe_load((ROOT / "specs/http-contracts.yaml").read_text(encoding="utf-8"))
    catalog = yaml.safe_load((ROOT / "specs/model-catalog.yaml").read_text(encoding="utf-8"))
    inspector = inspect(engine)
    schema = inspector.default_schema_name
    actual_names = set(inspector.get_table_names(schema=schema))
    expected_names = set(Base.metadata.tables)
    if actual_names != expected_names:
        raise RuntimeError(f"Database/model table mismatch: missing={expected_names-actual_names}, extra={actual_names-expected_names}")
    if set(catalog["domain_mapping"].values()) != actual_names:
        raise RuntimeError("Conceptual domain mapping does not cover exactly the current database tables.")
    reflected = MetaData()
    reflected.reflect(bind=engine, schema=None, only=sorted(actual_names))
    tables = []
    for name in sorted(actual_names):
        orm_table = Base.metadata.tables[name]
        columns = inspector.get_columns(name, schema=schema)
        observed = {c["name"]: c for c in columns}
        if set(observed) != set(orm_table.columns.keys()):
            raise RuntimeError(f"Column mismatch in {name}")
        for column in orm_table.columns:
            actual = observed[column.name]
            if actual["nullable"] != column.nullable or str(actual["type"].compile(dialect=engine.dialect)) != str(column.type.compile(dialect=engine.dialect)):
                raise RuntimeError(f"Type/nullability mismatch at {name}.{column.name}")
        tables.append({
            "name": name,
            "columns": [{"name": c["name"], "type": str(c["type"].compile(dialect=engine.dialect)), "nullable": c["nullable"], "server_default": c.get("default")} for c in columns],
            "primary_key": inspector.get_pk_constraint(name, schema=schema),
            "foreign_keys": inspector.get_foreign_keys(name, schema=schema),
            "unique_constraints": inspector.get_unique_constraints(name, schema=schema),
            "check_constraints": inspector.get_check_constraints(name, schema=schema),
            "indexes": inspector.get_indexes(name, schema=schema),
        })
    with engine.connect() as connection:
        version = connection.scalar(text("SHOW server_version"))
    database = {"id": "DB-01", "captured_at": datetime.now(timezone.utc).isoformat(),
                "origin": "Read-only SQLAlchemy reflection of the running PostgreSQL schema; no row data",
                "postgresql_version": version, "schema": schema, "table_count": len(tables), "tables": tables}
    ddl = ["-- DB-01: reflected current PostgreSQL DDL, not a migration or a backup.",
           "-- Includes schema only; no account credentials or HR records."]
    for table in reflected.sorted_tables:
        ddl.append(str(CreateTable(table).compile(dialect=engine.dialect)).strip() + ";")
        for index in sorted(table.indexes, key=lambda x: x.name or ""):
            ddl.append(str(CreateIndex(index).compile(dialect=engine.dialect)).strip() + ";")
    api = app.openapi()
    browser_api = copy.deepcopy(api)
    browser_api.setdefault("components", {}).setdefault("securitySchemes", {})["SessionCookie"] = {
        "type": "apiKey", "in": "cookie", "name": COOKIE_NAME,
        "description": "Process-local opaque session; POST additionally requires a session-bound CSRF form token",
    }
    browser_api["info"]["description"] = "Current HRMS browser contracts: HTML/forms/cookie/redirects. Exported offline; the runtime OpenAPI endpoint is disabled."
    route_inventory = []
    public_paths = {"/login", "/health", "/instance"}
    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue
        for method in sorted(route.methods):
            route_inventory.append({"method": method, "path": route.path,
                "code": route.endpoint.__module__.replace(".", "/") + ".py#" + route.endpoint.__qualname__})
            operation = browser_api["paths"][route.path][method.lower()]
            operation["x-code-symbol"] = route_inventory[-1]["code"]
            if route.path not in public_paths:
                operation["security"] = [{"SessionCookie": []}]
                operation["responses"]["303"] = {"description": "Missing/expired/inactive session redirects to /login, or successful mutation redirect",
                    "headers": {"Location": {"schema": {"type": "string"}}}}
            if method == "GET" and route.path not in {"/health", "/instance", "/reports/employees.csv"}:
                operation["responses"]["200"] = html_response("Rendered Persian HTML page")
            if method == "POST":
                operation["responses"].pop("200", None)
                operation["responses"]["303"] = {"description": "Successful form submission or documented retry; follow Location",
                    "headers": {"Location": {"schema": {"type": "string"}}}}
                operation["responses"]["403"] = html_response("Invalid CSRF or insufficient role")
                form_schema = {"type": "object", "properties": {"csrf_token": {"type": "string"}}, "required": ["csrf_token"]}
                operation["requestBody"] = {"required": True, "content": {
                    "application/x-www-form-urlencoded": {"schema": form_schema},
                    "multipart/form-data": {"schema": copy.deepcopy(form_schema)},
                }}
                operation["x-form-inventory"] = "See route-inventory.json and specs/http-contracts.yaml for full or dynamic form fields"
    grouped = {}
    for contract in contracts["contracts"]:
        for record in contract["operations"]:
            key = record["path"], record["method"].lower()
            grouped.setdefault(key, []).append((contract["id"], record))
    for (path, method), records in grouped.items():
        operation = browser_api["paths"][path][method]
        operation["x-hrms-contracts"] = [{"id": cid, **record} for cid, record in records]
        for _, record in records:
            if record.get("fields"):
                props = {name: {key: value for key, value in settings.items() if key != "required"}
                         for name, settings in record["fields"].items()}
                schema_body = {"type": "object", "properties": props,
                               "required": [name for name, settings in record["fields"].items() if settings.get("required")]}
                operation["requestBody"] = {"required": True, "content": {
                    "application/x-www-form-urlencoded": {"schema": schema_body},
                    "multipart/form-data": {"schema": copy.deepcopy(schema_body)},
                }}
            for code in record.get("errors", []):
                operation["responses"][str(code)] = ({"description": "Unexpected persistence/server failure"} if code == 500
                                                        else html_response(f"Documented browser error {code}; see x-hrms-contracts conditions"))
    browser_api["paths"]["/health"]["get"]["responses"]["503"] = {
        "description": "PostgreSQL connection unavailable",
        "content": {"application/json": {"schema": {"type": "object", "properties": {"status": {"const": "unavailable"}}}}},
    }
    browser_api["paths"]["/reports/employees.csv"]["get"]["responses"]["200"] = {
        "description": "UTF-8 BOM employee CSV; scoped HR/admin only; writes an export audit",
        "content": {"text/csv": {"schema": {"type": "string"}}},
    }
    forms = [{"module": name, "table": config["model"].__tablename__, "admin_only": config.get("admin_only", False),
              "fields": config["fields"], "columns": config["columns"]} for name, config in MODULES.items()]
    inventory = {"id": "ROUTE-CAT-01", "route_count": len(route_inventory), "routes": route_inventory,
                 "module_forms_from_current_code": forms,
                 "notes": ["Dynamic generic /hr routes choose forms/roles by module", "Form metadata is implementation-derived; human review still pending"]}
    source_paths = list((ROOT / "app").rglob("*.py")) + list((ROOT / "tests").glob("test_*.py"))
    source_paths += list((ROOT / "specs").glob("UC-*.yaml"))
    source_paths += [ROOT / "specs" / n for n in ("architecture.yaml", "requirements.yaml", "functional-specifications.yaml", "http-contracts.yaml", "model-catalog.yaml")]
    sources = {"id": "EXPORT-SOURCE-01", "captured_at": database["captured_at"], "hash_normalization": "UTF-8 text with LF line endings",
               "files": [{"path": p.relative_to(ROOT).as_posix(), "sha256": hashlib.sha256(p.read_text(encoding="utf-8").encode("utf-8")).hexdigest()} for p in sorted(source_paths)]}
    write("docs/06-design/database-schema.json", as_json(database), refresh)
    write("docs/06-design/database-schema.sql", "\n".join(line.rstrip() for line in "\n\n".join(ddl).splitlines()), refresh)
    write("docs/06-design/openapi-generated.json", as_json(api), refresh)
    write("docs/06-design/openapi-browser.yaml", yaml.safe_dump(browser_api, allow_unicode=True, sort_keys=False), refresh)
    write("docs/06-design/route-inventory.json", as_json(inventory), refresh)
    write("docs/06-design/export-source.json", as_json(sources), refresh)
    dependency_lines = sorted({f"{d.metadata['Name']}=={d.version}" for d in importlib.metadata.distributions()
                               if d.metadata.get("Name") and re.fullmatch(r"[A-Za-z0-9_.-]+", d.metadata["Name"])}, key=str.casefold)
    write("requirements-dev-lock.txt", "# Captured installed development environment; production lock remains separate.\n" + "\n".join(dependency_lines), refresh)
    diagram = ["%% DB-01 — reflected PostgreSQL relationships", "erDiagram"]
    for table in tables:
        diagram.append(f"    {table['name']} {{")
        for column in table["columns"]:
            column_type = re.sub(r"[^A-Za-z0-9_]", "_", column["type"]).strip("_") or "value"
            marker = " PK" if column["name"] in table["primary_key"]["constrained_columns"] else ""
            diagram.append(f"        {column_type} {column['name']}{marker}")
        diagram.append("    }")
    for table in tables:
        for fk in table["foreign_keys"]:
            optional = any(next(c for c in table["columns"] if c["name"] == name)["nullable"] for name in fk["constrained_columns"])
            relation = "|o" if optional else "||"
            label = "_".join(fk["constrained_columns"])
            diagram.append(f'    {fk["referred_table"]} {relation}--o{{ {table["name"]} : "{label}"')
    write("models/data-model.mmd", "\n".join(diagram), refresh)
    table_rows = "\n".join(f"| {t['name']} | {len(t['columns'])} | {len(t['foreign_keys'])} |" for t in tables)
    database_doc = f"""# DB-01 — طراحی دادهٔ واقعی

این export از reflection فقط‌خواندنی PostgreSQL {version} در schema {schema} ساخته شده؛ هیچ سطر HR، رمز یا URL اتصال صادر نشده است. تعداد جدول‌ها {len(tables)} است و نام/ستون/نوع/nullability با مدل‌های ORM و نگاشت مفهومی تطبیق داده شد.

[DDL فعلی](database-schema.sql)، [metadata و constraints](database-schema.json)، [منبع و hash کد](export-source.json)، [نمودار ER editable](../../models/data-model.mmd).

| جدول | ستون | foreign key |
|---|---|---|
{table_rows}

قیدهای اصلی: کد کارمند یکتا؛ unit/branch مرکب؛ attendance employee/day یکتا؛ payslip employee/period یکتا؛ profile برای هر employee یکتا؛ یک active contract و یک assignment جاری با partial unique index؛ ثبت‌نام employee/training یکتا؛ score/progress و درصد/ساعت در محدوده.

قواعد request status و overlap در service/domain و transaction قفل‌دار اعمال می‌شوند و CHECK/EXCLUDE constraint جامع در DB ندارند. snapshotهای فیش JSON هستند، نه JSONB. audit به entity/record منطقی متصل است و سیستم tamper-evident نیست.

این SQL شرح schema است؛ migration یا backup نیست و روی پایگاه موجود اجرا نمی‌شود. مدیریت migration نسخه‌دار، طرح restore آزموده و effective-dated profile/report هنوز باقی‌اند. اصل HRMS همچنان یک پایگاه مشترک دارد.
"""
    write("docs/06-design/database-design.md", database_doc, refresh)
    groups = {"analysis-models": ["CTX-01", "UCM-01", "DM-01"],
              "UC-01-models": ["SEQ-01", "ACT-01", "ST-01"],
              "UC-02-models": ["SEQ-02", "ACT-02", "ST-02"],
              "UC-03-models": ["SEQ-03", "ACT-03", "ST-03"]}
    model_lookup = {m["id"]: m for m in catalog["models"]}
    fence = chr(96) * 3
    for name, ids in groups.items():
        output = [f"# {name} — مدل‌های قابل مشاهدهٔ HRMS", "",
                  "از رفتار فعلی بازسازی شده؛ تأیید انسانی ثبت نشده است. نسخهٔ editable و شناسه‌ها در [فهرست مدل‌ها](README.md).", ""]
        for ident in ids:
            model = model_lookup[ident]
            raw = (ROOT / model["path"]).read_text(encoding="utf-8")
            output += [f"## {ident} — {model['name']}", "", fence + "mermaid", raw.rstrip(), fence, ""]
        write(f"docs/04-models/{name}.md", "\n".join(output), refresh)
    print(f"Exported {len(tables)} reflected tables, {len(route_inventory)} routes and {len(forms)} module form definitions.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh", action="store_true", help="Intentionally regenerate derived design files; never touches historical test evidence.")
    export(parser.parse_args().refresh)
