"""Build stable traceability links and readable matrices from current specifications and evidence."""
import argparse
import ast
import json
import re
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parent.parent


def read(path):
    return yaml.safe_load((ROOT / path).read_text(encoding="utf-8"))


def write(path, text, refresh):
    p = ROOT / path
    if p.exists() and not refresh:
        raise FileExistsError(f"{path} exists; use --refresh for derived traceability.")
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text.rstrip() + "\n", encoding="utf-8")


def test_id(name):
    match = re.match(r"test_tc_(\d{2})_([uU]?\d{2})_", name)
    if match:
        return "TC-" + match[1] + "-" + match[2].upper()
    match = re.match(r"test_tc_m(\d{2})_", name)
    return "TC-M-" + match[1] if match else None


def build(refresh):
    req = read("specs/requirements.yaml")
    cases = read("specs/test-cases.yaml")
    models = read("specs/model-catalog.yaml")
    api = read("specs/http-contracts.yaml")
    use_cases = [read(path.relative_to(ROOT).as_posix()) for path in sorted((ROOT / "specs").glob("UC-*.yaml"))]
    tests = {}
    for file in sorted((ROOT / "tests").glob("test_*.py")):
        for node in ast.parse(file.read_text(encoding="utf-8")).body:
            if isinstance(node, ast.ClassDef):
                for method in node.body:
                    if isinstance(method, ast.FunctionDef):
                        ident = test_id(method.name)
                        if ident:
                            tests[ident] = file.relative_to(ROOT).as_posix() + "#" + node.name + "." + method.name
    registry = {}
    def register(ident, target, kind):
        if ident in registry:
            raise RuntimeError("Duplicate registry id " + ident)
        registry[ident] = {"id": ident, "target": target, "kind": kind}
    for ident, target in {
        "CH-01": "docs/01-project-charter/charter.md",
        "DOCS-01": "docs/README.md",
        "REGISTRY-01": "specs/artifact-registry.yaml",
        "SRC-01": "docs/02-requirements/sources.md",
        "REQ-CAT-01": "docs/02-requirements/requirements.md",
        "FS-CAT-01": "specs/functional-specifications.yaml",
        "UC-CAT-01": "docs/03-specifications/use-cases.md",
        "MODEL-CAT-01": "specs/model-catalog.yaml",
        "ARCH-SPEC-01": "specs/architecture.yaml",
        "QA-01": "docs/05-architecture/quality-scenarios.md",
        "EXP-CAT-01": "docs/05-architecture/progressive-experiments.md",
        "DESIGN-CAT-01": "docs/06-design/design.md",
        "API-CAT-01": "docs/06-design/api-design.md",
        "HTTP-CAT-01": "specs/http-contracts.yaml",
        "DB-01": "docs/06-design/database-schema.json",
        "ROUTE-CAT-01": "docs/06-design/route-inventory.json",
        "EXPORT-SOURCE-01": "docs/06-design/export-source.json",
        "AI-CAT-01": "docs/07-ai-transformation/README.md",
        "AI-REVIEW-01": "docs/07-ai-transformation/ai-review.md",
        "TEST-STRATEGY-01": "docs/08-testing/strategy.md",
        "TEST-CAT-01": "specs/test-cases.yaml",
        "TEST-REPORT-01": "docs/08-testing/report.md",
        "TR-CAT-01": "specs/traceability.yaml",
        "CR-01": "docs/10-final-report/changes/CR-01.md",
        "CR-02": "docs/10-final-report/changes/CR-02.md",
        "REPORT-01": "docs/10-final-report/report.md",
        "MILESTONE-CAT-01": "docs/10-final-report/milestones.md",
        "RUBRIC-01": "docs/10-final-report/rubric.md",
        "CONTRIB-01": "docs/10-final-report/contributions.md",
        "DEMO-01": "docs/10-final-report/presentation-and-demo.md",
        "OPEN-01": "docs/10-final-report/remaining-work.md",
        "REF-S02": "docs/references/project-framework/README.md",
        "SLIDE-REVIEW-01": "docs/project-framework-slide-review.md",
    }.items():
        register(ident, target, "document")
    for ident in ("SRC-U01", "SRC-U02", "SRC-U03", "SRC-C01", "SRC-H01"):
        register(ident, "docs/02-requirements/sources.md", "source")
    register("SRC-S01", "https://sadscalabilitylab.space-z.ai/", "source")
    register("SRC-S02", "https://sadprojectdocs.space-z.ai/", "source")
    for category in ("functional_requirements", "business_rules", "nonfunctional_requirements"):
        for r in req[category]:
            register(r["id"], "specs/requirements.yaml", category)
    for r in read("specs/functional-specifications.yaml")["specifications"]:
        register(r["id"], "specs/functional-specifications.yaml", "functional_specification")
    for n in range(1, 13):
        target = f"specs/UC-{n:02}.yaml"
        register(f"UC-{n:02}", target if (ROOT / target).is_file() else "docs/03-specifications/use-cases.md", "use_case")
    for m in models["models"]:
        register(m["id"], m["path"], "model")
    for n, name in enumerate(("baseline", "postgresql", "session", "request-workflow"), 1):
        register(f"ADR-{n:02}", f"docs/05-architecture/ADRs/ADR-{n:02}-{name}.md", "architecture_decision")
    for path in sorted((ROOT / "docs/05-architecture/ADRs").glob("ADR-*.md")):
        ident = "-".join(path.stem.split("-")[:2])
        if ident not in registry:
            register(ident, path.relative_to(ROOT).as_posix(), "architecture_decision")
    for n in range(1, 5):
        register(f"D-{n:02}", f"docs/06-design/design.md#d-{n:02}", "design")
    for r in api["contracts"]:
        register(r["id"], "specs/http-contracts.yaml", "api_contract")
    for ident, target in tests.items():
        register(ident, target, "automated_test")
    register("TC-REG-01", "scripts/run_isolated_smoke.py", "regression_suite")
    register("TC-HIST-01", "scripts/smoke_check.py", "historical_stage1_suite")
    register("TC-PERF-01", "scripts/run_load_lab.py", "small_load_experiment")
    for n in range(1, 3):
        register(f"TRF-{n:02}", f"docs/07-ai-transformation/transformation-records/TRF-{n:02}.yaml", "ai_transformation")
    # Exact assertion indices in the existing recorded suite; associations are not exhaustive acceptance coverage.
    reg_indices = {
        1: [1, 82, 88, 91, 97], 3: list(range(83, 95)), 4: [25, 74], 5: [66],
        7: [19, 75], 8: [2, 20, 21, 23, 28], 9: [3, 22, 23], 10: list(range(24, 30)),
        11: list(range(30, 40)), 12: [40, 44, 48], 13: list(range(41, 50)),
        14: [9, 51, 53, 55], 15: [10, 50], 16: list(range(52, 59)),
        17: list(range(59, 68)), 18: [68, 69], 19: [70, 71, 72], 20: [73],
        21: list(range(74, 79)), 22: [78, 92, 94], 23: [79, 93], 24: [42, 95, 96], 25: [16, 80, 81, 87, 89, 90],
    }
    traces = []
    for index, fr in enumerate(req["functional_requirements"], 1):
        ucs = {fr["use_case"]}
        ucs.update(u["id"] for u in use_cases if fr["id"] in u["requirements"])
        model_ids = {"DM-01", "UCM-01"}
        design_ids = set()
        for uc in ucs:
            number = int(uc.split("-")[1])
            if number <= 3:
                model_ids.update(f"{prefix}-{number:02}" for prefix in ("SEQ", "ACT", "ST"))
                design_ids.add(f"D-{number:02}")
            else:
                design_ids.add("D-04")
        test_ids = list(fr["core_tests"])
        if index in reg_indices:
            test_ids.append("TC-REG-01")
        if index in (4, 5, 6, 7):
            test_ids.append("TC-HIST-01")
        trace = {"id": f"TR-{index:02}", "requirement": fr["id"], "specification": f"FS-{index:02}",
            "sources": fr["source"], "business_rules": fr["business_rules"], "use_cases": sorted(ucs),
            "models": sorted(model_ids), "design": sorted(design_ids), "api": [f"API-{int(uc.split('-')[1]):02}" for uc in sorted(ucs)],
            "code": fr["code"], "tests": sorted(set(test_ids)), "regression_assertion_indices": reg_indices.get(index, []),
            "verification": "core_test_samples_and_broad_regression" if fr["core_tests"] else "extended_partial_or_historical_evidence",
            "human_review": "pending", "coverage_limit": "Links identify actual evidence; they do not certify all positive/negative/boundary paths"}
        traces.append(trace)
        register(trace["id"], "specs/traceability.yaml", "traceability_record")
    nonfunctional = []
    for n, r in enumerate(req["nonfunctional_requirements"], 1):
        trace = {"id": f"TR-NFR-{n:02}", "requirement": r["id"], "status": r["status"],
                 "tests": r.get("tests", []), "evidence": r.get("evidence", []),
                 "architecture": ["ARCH-01", "QA-01", "EXP-CAT-01"]}
        nonfunctional.append(trace)
        register(trace["id"], "specs/traceability.yaml", "traceability_record")
    write("specs/artifact-registry.yaml", yaml.safe_dump({"id": "REGISTRY-01", "version": 1,
        "review_status": "pending_human_review", "entries": list(registry.values())}, allow_unicode=True, sort_keys=False), refresh)
    write("specs/traceability.yaml", yaml.safe_dump({"id": "TR-CAT-01", "version": 1,
        "traceability": traces, "nonfunctional_traceability": nonfunctional,
        "test_code_symbols": tests}, allow_unicode=True, sort_keys=False), refresh)
    matrix = ["# TR-CAT-01 — ماتریس نیازمندی تا آزمون", "",
        "از specificationهای جاری ساخته شده؛ review انسانی باز است. [دادهٔ ماشین‌خوان](../../specs/traceability.yaml) و [شناسه‌ها](../../specs/artifact-registry.yaml).", "",
        "هر ردیف منبع، FR/BR، specification، UC، مدل، طرح، API، code symbol و evidence را وصل می‌کند. لینک به suite عمومی یا سابقهٔ تاریخی، پوشش کامل acceptance همان FR را اثبات نمی‌کند.", "",
        "| TR / FR | Spec / UC | Model / Design | API / Code | Test |", "|---|---|---|---|---|"]
    for t in traces:
        links = "<br>".join(f"[{s.split('#')[-1]}](../../{s})" for s in t["code"])
        matrix.append(f"| {t['id']} / {t['requirement']} | {t['specification']} / {', '.join(t['use_cases'])} | {', '.join(t['models'])} / {', '.join(t['design'])} | {', '.join(t['api'])}<br>{links} | {', '.join(t['tests'])} |")
    matrix += ["", "TC-REG-01 = 98 assertion رگرسیون فعلی؛ index دقیق مرتبط در YAML. TC-HIST-01 = 45 بررسی قدیمی Stage 1؛ اجرای تازه نیست. TC-PERF-01 = بار native سبک. TC-01..03 = آزمون‌های Core با نتیجهٔ نهایی؛ TC-02-U و TC-M قواعد و مرز معماری.", "",
        "## نیازمندی غیرعملکردی", "", "| NFR | وضعیت واقعی | تست / شاهد |", "|---|---|---|"]
    for t in nonfunctional:
        evidence = ", ".join(f"[{Path(e).name}](../../{e})" for e in t["evidence"]) or "شاهد پذیرش موجود نیست"
        matrix.append(f"| {t['requirement']} | {t['status']} | {', '.join(t['tests'])}<br>{evidence} |")
    matrix += ["", "سازگاری semantic و کامل بودن قراردادها نیازمند review انسانی است. بررسی خودکار تنها وجود/شناسه/پیوند/symbol و دادهٔ schema را کنترل می‌کند؛ نمرهٔ Consistency از تعداد linkها تولید نمی‌شود."]
    write("docs/09-traceability/matrix.md", "\n".join(matrix), refresh)
    print(f"Generated {len(traces)} FR traces, {len(nonfunctional)} NFR traces and {len(registry)} stable artifact identifiers.")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--refresh", action="store_true")
    build(p.parse_args().refresh)
