"""Check structured engineering artifacts, source links and evidence; does not certify human reviews."""
import argparse
import ast
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import unquote

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


class StrictLoader(yaml.SafeLoader):
    pass


StrictLoader.yaml_implicit_resolvers = {
    key: [(tag, regex) for tag, regex in values if tag != "tag:yaml.org,2002:bool"]
    for key, values in yaml.SafeLoader.yaml_implicit_resolvers.items()
}
StrictLoader.add_implicit_resolver("tag:yaml.org,2002:bool",
    re.compile(r"^(?:true|false|True|False|TRUE|FALSE)$"), list("tTfF"))


def unique_mapping(loader, node, deep=False):
    pairs = loader.construct_pairs(node, deep=deep)
    output = {}
    for key, value in pairs:
        if key in output:
            raise yaml.constructor.ConstructorError("mapping", node.start_mark, f"Duplicate YAML key: {key!r}", node.start_mark)
        output[key] = value
    return output


StrictLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, unique_mapping)


def load(path):
    return yaml.load((ROOT / path).read_text(encoding="utf-8"), Loader=StrictLoader)


def check_engineering():
    checks = []
    def check(name, success, detail=None):
        checks.append({"check": name, "passed": bool(success), **({"detail": detail} if detail else {})})
    yaml_paths = list((ROOT / "specs").rglob("*.yaml")) + list((ROOT / "docs").rglob("*.yaml"))
    yaml_paths += list((ROOT / ".github").rglob("*.yml"))
    for path in sorted(yaml_paths):
        try:
            yaml.load(path.read_text(encoding="utf-8"), Loader=StrictLoader)
            check("YAML " + path.relative_to(ROOT).as_posix(), True)
        except yaml.YAMLError as exc:
            check("YAML " + path.relative_to(ROOT).as_posix(), False, str(exc))
    if not all(x["passed"] for x in checks):
        return checks
    req = load("specs/requirements.yaml")
    registry = load("specs/artifact-registry.yaml")
    entries = registry["entries"]
    identifiers = {entry["id"]: entry for entry in entries}
    check("Registry identifiers unique", len(identifiers) == len(entries))
    fr_ids = {r["id"] for r in req["functional_requirements"]}
    br_ids = {r["id"] for r in req["business_rules"]}
    nfr_ids = {r["id"] for r in req["nonfunctional_requirements"]}
    check("FR-01..25 complete", fr_ids == {f"FR-{n:02}" for n in range(1, 26)})
    check("22 unique BR and 11 unique NFR", len(br_ids) == 22 and len(nfr_ids) == 11)
    trees = {}
    def code_symbol(target):
        file, _, symbol = target.partition("#")
        p = ROOT / file
        if not p.is_file():
            return False
        if not symbol:
            return True
        if p.suffix != ".py":
            return True
        tree = trees.setdefault(file, ast.parse(p.read_text(encoding="utf-8")))
        nodes = tree.body
        for part in symbol.split("."):
            found = None
            for node in nodes:
                if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == part:
                    found = node
                    break
                if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == part for t in node.targets):
                    found = node
                    break
            if found is None:
                return False
            nodes = getattr(found, "body", [])
        return True
    def target_exists(target, origin=ROOT / "README.md"):
        if re.match(r"^(https?://|mailto:|codex://|plugin://)", target):
            return True
        target = unquote(target)
        file, _, anchor = target.partition("#")
        file = re.sub(r":\d+$", "", file)
        if re.match(r"^[A-Za-z]:[/\\]", file):
            normalized = file.replace("\\", "/")
            original_root = "C:/Users/mahdy/Desktop/MP/"
            p = ROOT / normalized[len(original_root):] if normalized.startswith(original_root) else Path(file)
        else:
            p = (origin.parent / file).resolve() if file else origin
        if not p.is_file() and not p.is_dir():
            return False
        if anchor and p.suffix == ".py":
            try:
                return code_symbol(p.relative_to(ROOT).as_posix() + "#" + anchor)
            except ValueError:
                return True
        if anchor and p.suffix == ".md" and anchor.startswith("d-"):
            return f'id="{anchor}"' in p.read_text(encoding="utf-8")
        return True
    for entry in entries:
        check("Artifact target " + entry["id"], target_exists(entry["target"], ROOT / "_registry_root.md"))
    for fr in req["functional_requirements"]:
        check("FR links " + fr["id"], fr["use_case"] in identifiers and all(x in identifiers for x in fr["business_rules"] + fr["source"] + fr["core_tests"]))
        for symbol in fr["code"]:
            check("Code " + symbol, code_symbol(symbol))
    for br in req["business_rules"]:
        check("BR links " + br["id"], all(x in identifiers for x in br["requirements"] + br["source"]))
        for symbol in br["code"]:
            check("Code " + symbol, code_symbol(symbol))
    for n in range(1, 4):
        uc = load(f"specs/UC-{n:02}.yaml")
        necessary = ("id", "version", "goal", "trigger", "preconditions", "input", "main_flow", "alternatives", "success", "failure", "traceability")
        check("Full use case " + uc["id"], all(key in uc and uc[key] is not None for key in necessary))
        refs = uc["requirements"] + uc["business_rules"] + uc["traceability"]["models"] + uc["traceability"]["tests"]
        refs += [uc["traceability"]["design"], uc["traceability"]["api"]]
        check("UC references " + uc["id"], all(x in identifiers for x in refs))
        for symbol in uc["traceability"]["code"]:
            check("UC code " + symbol, code_symbol(symbol))
    for category in ("app", "scripts", "tests"):
        for path in sorted((ROOT / category).rglob("*.py")):
            try:
                compile(path.read_text(encoding="utf-8"), str(path), "exec")
                check("Python syntax " + path.relative_to(ROOT).as_posix(), True)
            except SyntaxError as exc:
                check("Python syntax " + path.relative_to(ROOT).as_posix(), False, str(exc))
    current_markdown = [ROOT / "README.md", ROOT / "AGENTS.md"]
    current_markdown += [p for p in (ROOT / "docs").rglob("*.md")
                         if not set(p.relative_to(ROOT / "docs").parts).intersection({"history", "prompts"})]
    markdown_pattern = re.compile(r"!?\[[^\]\n]*\]\((?:<([^>]+)>|([^\s)]+))\)")
    for path in current_markdown:
        for m in markdown_pattern.finditer(path.read_text(encoding="utf-8")):
            target = m[1] or m[2]
            check("Markdown link " + path.relative_to(ROOT).as_posix() + " -> " + target, target_exists(target, path))
    trace = load("specs/traceability.yaml")
    rows = trace["traceability"]
    check("25 one-to-one FR trace rows", len(rows) == 25 and {r["requirement"] for r in rows} == fr_ids)
    for row in rows:
        linked = row["sources"] + row["business_rules"] + row["use_cases"] + row["models"] + row["design"] + row["api"] + row["tests"] + [row["requirement"], row["specification"]]
        check("Trace links " + row["id"], all(x in identifiers for x in linked) and bool(row["code"]) and bool(row["tests"]))
        for symbol in row["code"]:
            check("Trace code " + symbol, code_symbol(symbol))
    for row in trace["nonfunctional_traceability"]:
        check("NFR trace " + row["requirement"], row["requirement"] in nfr_ids and all(x in identifiers for x in row["tests"] + row["architecture"]))
    for ident, symbol in trace["test_code_symbols"].items():
        check("Test code " + ident, code_symbol(symbol))
    from app.main import app
    from app.database import Base, engine
    generated = json.loads((ROOT / "docs/06-design/openapi-generated.json").read_text(encoding="utf-8"))
    check("OpenAPI matches current FastAPI routes", generated == app.openapi())
    browser = load("docs/06-design/openapi-browser.yaml")
    check("Browser OpenAPI paths match generated", set(browser["paths"]) == set(generated["paths"]))
    check("Session cookie scheme", browser["components"]["securitySchemes"]["SessionCookie"]["name"] == "hrms_session")
    for route, methods in browser["paths"].items():
        if "post" in methods:
            props = methods["post"]["requestBody"]["content"]["application/x-www-form-urlencoded"]["schema"]["properties"]
            check("CSRF form contract " + route, "csrf_token" in props)
    for contract in load("specs/http-contracts.yaml")["contracts"]:
        for op in contract["operations"]:
            check("API operation " + contract["id"] + " " + op["path"], op["path"] in generated["paths"] and op["method"].lower() in generated["paths"][op["path"]])
    database = json.loads((ROOT / "docs/06-design/database-schema.json").read_text(encoding="utf-8"))
    table_names = {t["name"] for t in database["tables"]}
    model = load("specs/model-catalog.yaml")
    check("Domain covers 21 reflected tables", database["table_count"] == 21 and set(model["domain_mapping"].values()) == table_names == set(Base.metadata.tables))
    conceptual_names = set(re.findall(r"\bclass\s+(\w+)\s*\{", (ROOT / "models/domain.mmd").read_text(encoding="utf-8")))
    check("Conceptual domain entities match mapping", conceptual_names == set(model["domain_mapping"]))
    for table in database["tables"]:
        expected = Base.metadata.tables[table["name"]]
        actual = {c["name"]: c for c in table["columns"]}
        good = set(actual) == set(expected.columns.keys())
        good = good and all(actual[c.name]["nullable"] == c.nullable and actual[c.name]["type"] == str(c.type.compile(dialect=engine.dialect)) for c in expected.columns)
        check("Reflected columns match ORM " + table["name"], good)
    ddl = (ROOT / "docs/06-design/database-schema.sql").read_text(encoding="utf-8")
    check("DDL contains all 21 tables", set(re.findall(r"CREATE TABLE (\w+)", ddl)) == table_names)
    source = json.loads((ROOT / "docs/06-design/export-source.json").read_text(encoding="utf-8"))
    for item in source["files"]:
        digest = hashlib.sha256((ROOT / item["path"]).read_text(encoding="utf-8").encode("utf-8")).hexdigest()
        check("Export source current " + item["path"], digest == item["sha256"])
    readings = json.loads((ROOT / "docs/references/project-framework/slide-readings.json").read_text(encoding="utf-8"))
    applications = load("specs/slide-application.yaml")["applications"]
    check("All 93 slide readings and applications", len(readings) == len(applications) == 93 and {r["number"] for r in readings} == {r["number"] for r in applications} == set(range(1, 94)))
    for record in applications:
        check("Slide application references " + str(record["number"]), all(x in identifiers for x in record["artifacts"]))
    assets_path = ROOT / "docs/references/project-framework/diagram-sources.json"
    assets = json.loads(assets_path.read_text(encoding="utf-8"))["assets"]
    check("All 23 original lecture diagrams", len(assets) == 23)
    for asset in assets:
        check("Original diagram hash " + asset["name"], hashlib.sha256((assets_path.parent / asset["path"]).read_bytes()).hexdigest() == asset["sha256"])
    results = json.loads((ROOT / "docs/08-testing/evidence/all-tests-final.json").read_text(encoding="utf-8"))
    check("29 recorded tests all passed", results["tests_run"] == 29 and results["all_passed"] and len(results["checks"]) == 29 and all(x["status"] == "passed" for x in results["checks"]))
    expected_tests = {symbol.replace("/", ".").replace(".py#", ".") for symbol in trace["test_code_symbols"].values()}
    check("All test symbols present in final evidence", expected_tests == {x["test"] for x in results["checks"]})
    before = json.loads((ROOT / "docs/08-testing/evidence/core-before.json").read_text(encoding="utf-8"))
    failures = [r for r in before["checks"] if r["status"] != "passed"]
    check("Before failure is the documented conflict", before["tests_run"] == 17 and not before["all_passed"] and len(failures) == 1 and "test_tc_02_05_" in failures[0]["test"])
    regression = json.loads((ROOT / "docs/08-testing/evidence/full-smoke-after.json").read_text(encoding="utf-8"))
    check("98 actual regression assertions", len(regression["checks"]) == 98 and regression["all_passed"] and all(x["passed"] for x in regression["checks"]))
    coverage = json.loads((ROOT / "docs/08-testing/evidence/coverage-request-workflow.json").read_text(encoding="utf-8"))
    check("Request package coverage >=80%", coverage["totals"]["percent_covered"] >= 80 and all(k.replace("\\", "/").startswith("app/request_workflow/") for k in coverage["files"]))
    performance = json.loads((ROOT / "docs/08-testing/evidence/native-load.json").read_text(encoding="utf-8"))
    check("Small load does not certify 500-user NFR", performance["users_requested"] == 10 and performance["metrics"]["peak_authenticated_users"] == 10 and performance["nfr_500_users_verified"] is False)
    for n in (1, 2):
        record = load(f"docs/07-ai-transformation/transformation-records/TRF-{n:02}.yaml")
        check("TRF output hash " + record["id"], hashlib.sha256((ROOT / record["output"]).read_bytes()).hexdigest() == record["output_sha256"])
        check("TRF human review honestly pending " + record["id"], record["human_review"]["status"] == "pending" and record["human_review"]["reviewer"] is None)
    return checks


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, help="New evidence path inside this project; existing evidence is preserved")
    args = parser.parse_args()
    output = (ROOT / args.output).resolve()
    output.relative_to(ROOT)
    if output.exists():
        parser.error("Evidence path exists; choose a new name.")
    try:
        checks = check_engineering()
    except Exception as exc:
        checks = [{"check": "Engineering validation completed", "passed": False, "detail": type(exc).__name__ + ": " + str(exc)}]
    payload = {"id": "ENGINEERING-CHECK-01", "recorded_at": datetime.now(timezone.utc).isoformat(),
        "scope": "Current structured artifacts and links; historical original Markdown excluded; no human or visual acceptance",
        "all_passed": all(c["passed"] for c in checks), "checks": checks}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for c in checks:
        if not c["passed"]:
            print(json.dumps(c, ensure_ascii=True))
    print(f"{len(checks)} structural checks; failures={sum(not c['passed'] for c in checks)}; {output.relative_to(ROOT).as_posix()}")
    sys.exit(0 if payload["all_passed"] else 1)
