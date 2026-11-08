"""ADR-04 / NFR-M-01: preserve the declared internal dependency boundaries."""
import ast
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class ArchitectureBoundaries(unittest.TestCase):
    def imports(self, path):
        tree = ast.parse((ROOT / path).read_text(encoding="utf-8"))
        return [node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)] + [alias.name for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names]

    def test_tc_m01_domain_has_no_web_or_storage_dependency(self):
        for module in self.imports("app/request_workflow/domain.py"):
            self.assertFalse(any(x in module for x in ("fastapi", "sqlalchemy", "database", "hr_models", "repository", "service")), module)

    def test_tc_m02_service_has_no_http_or_direct_sql(self):
        for module in self.imports("app/request_workflow/service.py"):
            self.assertFalse(any(x in module for x in ("fastapi", "sqlalchemy", "database", "hr_models", "access", "security")), module)
        tree = ast.parse((ROOT / "app/modules.py").read_text(encoding="utf-8"))
        route = next(x for x in tree.body if isinstance(x, ast.FunctionDef) and x.name == "review_request")
        names = {x.id for x in ast.walk(route) if isinstance(x, ast.Name)}
        self.assertFalse(names.intersection({"select", "HrRequest", "AuditLog"}))
